"""Persistent $SCRATCH workspace for ROSIE.

SCRATCH is ROSIE's durable working space inside the selected workspace root.
It is NOT a service, database, or external process.  The entire store is a
directory of named JSON / JSONL pads resolved through the same workspace
containment (:func:`wrapper.tools._resolve_safe_path`) every other
filesystem tool uses.

Location:  ``<workspace_root>/$SCRATCH/``
  - JSON pad:      ``<workspace_root>/$SCRATCH/<name>.json``
  - JSONL records: ``<workspace_root>/$SCRATCH/<name>.jsonl``

Pads are plain named entries; the name is validated so it cannot escape the
scratch directory.  A name may contain alphanumerics, ``-``, ``_``, ``.`` but
no separators.  Writes are atomic within the OS: the content is first written
to ``$SCRATCH/.tmp-<pid>-<count>`` and then atomically renamed into place, so
a reader never observes a partially-written JSON document.

This module is a localized, internal API.  It is deliberately a class with a
small surface and no external dependencies.  Later consumers (RATTER, WATSON)
may use this boundary to share state between processes.
"""
from __future__ import annotations

import json
import logging
import os
import re
from itertools import count

from wrapper.tools import _resolve_safe_path, get_workspace_root

logger = logging.getLogger(__name__)

__all__ = ["ScratchStore"]

_PAD_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_tmp_counter = count()

DIR_NAME = "$SCRATCH"


class ScratchStore:
    """Persistent, boundary-constrained scratch storage for ROSIE work.

    One store is bound to a workspace root; all read/write paths resolve
    through the shared workspace containment (:func:`wrapper.tools._resolve_safe_path`),
    so an untrusted pad name cannot escape ``$SCRATCH/``.
    """

    def __init__(self, workspace_root=None) -> None:
        if workspace_root is None:
            workspace_root = get_workspace_root()
        self._root = workspace_root.resolve()
        self._scratch_dir = self._root / DIR_NAME

    def _resolve_pad_path(self, name: str, ext: str):
        """Resolve a pad name to its filename inside $SCRATCH.

        Validates the pad name, then resolves the path via safe_path so
        absolute paths, separators, and separators are rejected before
        ever touching the disk.
        """
        if not isinstance(name, str) or not _PAD_NAME_RE.match(name):
            raise ValueError(
                f"Invalid scratch pad name: {name!r}; "
                "pads must start with a letter/digit and contain only "
                "letters, digits, '.', '-' or '_'."
            )
        safe = _resolve_safe_path(
            self._root,
            f"{DIR_NAME}/{name}{ext}",
        )
        # Replacement invariant: the result must be exactly $SCRATCH/<name><ext>
        if safe.parent != self._scratch_dir.resolve():
            raise ValueError("scratch pad path escaping $SCRATCH")
        return safe

    def _ensure_scratch_exists(self) -> None:
        """Create `$SCRATCH` lazily (only when a write is requested)."""
        self._scratch_dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str, kind: str = "json"):
        """Return the on-disk Path for a pad without reading or writing.

        kind is 'json' or 'jsonl'; a nonexistent file still returns its
        canonical path location instead of raising.
        """
        if kind not in ("json", "jsonl"):
            raise ValueError("kind must be 'json' or 'jsonl'")
        return self._resolve_pad_path(name, f".{kind}")

    # -------------------- structured pads --------------------

    def exists(self, name: str, kind: str = "json") -> bool:
        """True if the named pad exists on disk in this workspace."""
        return self.path(name, kind).exists()

    def list_pads(self, kind: str | None = None) -> list[str]:
        """List pad names stored under $SCRATCH (without extension)."""
        if not self._scratch_dir.exists():
            return []
        names = set()
        exts = ("json", "jsonl") if kind is None else (kind,)
        for e in exts:
            for entry in self._scratch_dir.glob(f"*.{e}"):
                if entry.is_file():
                    names.add(entry.name[: -(len(e) + 1)])
        return sorted(names)

    def write_pad(self, name: str, payload: dict) -> None:
        """Persist a structured JSON pad (atomic replace)."""
        target = self.path(name, "json")
        serialized = json.dumps(payload, indent=2) + "\n"
        self._ensure_scratch_exists()
        tmp = self._scratch_dir / f".tmp-{os.getpid()}-{next(_tmp_counter)}"
        try:
            tmp.write_text(serialized, encoding="utf-8", newline="\n")
            os.replace(tmp, target)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    def read_pad(self, name: str) -> dict:
        """Read a structured JSON pad; returns ``{}`` when absent."""
        source = self.path(name, "json")
        if not source.exists():
            return {}
        return json.loads(source.read_text(encoding="utf-8"))

    # -------------------- append-oriented pads --------------------

    def append_pad(self, name: str, record: dict) -> None:
        """Append one JSON line to a JSONL pad."""
        target = self.path(name, "jsonl")
        serialized = json.dumps(record) + "\n"
        self._ensure_scratch_exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8", newline="\n") as f:
            f.write(serialized)

    def read_append_pad(self, name: str) -> list[dict]:
        """Read every JSONL record in a pad (empty list when absent)."""
        source = self.path(name, "jsonl")
        if not source.exists():
            return []
        out = []
        with open(source, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
