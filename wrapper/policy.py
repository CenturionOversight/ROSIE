"""Approval policy state machine for the agentic CLI wrapper.

Provides three execution modes — ``ask``, ``auto-write``, and ``yolo`` —
that control whether the user must confirm file writes and shell commands
before they are executed.

Modes:
    ask        (default) — prompt for *all* writes and shell commands.
    auto-write           — auto-approve file writes; prompt for shell commands.
    yolo                 — auto-approve everything; no prompts.
"""

from __future__ import annotations

import enum
import sys

__all__ = ["ApprovalPolicy", "ExecutionPolicy"]


class ExecutionPolicy(str, enum.Enum):
    """The three approval modes supported by the wrapper."""

    ASK = "ask"
    AUTO_WRITE = "auto-write"
    YOLO = "yolo"


class ApprovalPolicy:
    """Tracks the current execution mode and mediates interactive approvals.

    The policy can be switched live during a session: when the user selects
    ``[a]lways`` at an approval prompt the mode is raised to :attr:`YOLO`
    for the remainder of the session.
    """

    def __init__(self, mode: ExecutionPolicy = ExecutionPolicy.ASK):
        self.mode: ExecutionPolicy = mode

    @property
    def mode_name(self) -> str:
        """Human-readable name of the current mode."""
        return self.mode.value

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def is_auto_approved(self, action: str) -> bool:
        """Return ``True`` if *action* is auto-approved in the current mode.

        Args:
            action: ``"write"`` for file modifications or ``"shell"`` for
                command execution.
        """
        if self.mode == ExecutionPolicy.YOLO:
            return True
        return self.mode == ExecutionPolicy.AUTO_WRITE and action == "write"

    def request_approval(
        self,
        action: str,
        description: str,
        details: str = "",
    ) -> bool:
        """Ask the user whether *action* should proceed.

        In ``yolo`` mode or when auto-approved the result is always
        ``True`` without prompting.

        When the user types ``a`` (always) the mode is upgraded to
        :attr:`ExecutionPolicy.YOLO` for the rest of the session.

        Args:
            action: ``"write"`` or ``"shell"``.
            description: Short human-readable description of the action.
            details: Optional longer text (e.g. a diff) displayed before
                the prompt.

        Returns:
            ``True`` if the action is approved, ``False`` otherwise.
        """
        if self.is_auto_approved(action):
            prefix = "[auto-approved]" if self.mode == ExecutionPolicy.AUTO_WRITE else "[yolo]"
            print(f"{prefix} {description}")
            return True

        bar = "=" * 60
        print(f"\n{bar}")
        print(f"[APPROVAL REQUIRED] {description}")
        if details:
            print(bar)
            print(details)
            print(bar)
        print("  Choices: [y]es  [N]o  [a]lways (yolo for rest of session)")

        while True:
            try:
                choice = input(">>> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n[DENIED] (interrupted)")
                return False

            if choice in ("y", "yes"):
                return True
            if choice in ("a", "always"):
                self.mode = ExecutionPolicy.YOLO
                print("[*] Switched to YOLO mode for the rest of this session.")
                return True
            if choice in ("n", "no", ""):
                print("[DENIED]")
                return False
            print("Please enter y, n, or a.", file=sys.stderr)

    def update_from_flags(
        self, yolo: bool = False, auto_write: bool = False
    ) -> None:
        """Apply CLI flags to set the initial mode.

        ``yolo`` takes precedence over ``auto_write``.
        """
        if yolo:
            self.mode = ExecutionPolicy.YOLO
        elif auto_write:
            self.mode = ExecutionPolicy.AUTO_WRITE
