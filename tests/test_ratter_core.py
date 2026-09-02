"""Focused tests for the internal RATTER operational core.

Locks the hashing/chain/signature behavior against the reference output of
RATTER's own TypeScript implementation, and the ingest/query/integrity
semantics required by the ROSIE local PIC integration boundary.
"""
from __future__ import annotations

from wrapper.ratter_core import (
    GENESIS_CHAIN_HASH,
    RatterCore,
    canonicalize_json,
    compute_chain_hash,
    compute_payload_hash,
    generate_signature,
    get_ratter_core,
)


class TestCanonicalization:
    def test_key_order_and_whitespace(self):
        canonical = canonicalize_json({"b": 1, "a": 2})
        assert canonical == '{"a":2,"b":1}'

    def test_none_values_omitted(self):
        canonical = canonicalize_json({"a": None, "b": 1})
        assert canonical == '{"b":1}'

    def test_nested_and_list(self):
        canonical = canonicalize_json({"arr": [1, 2, True], "s": "x"})
        assert canonical == '{"arr":[1,2,true],"s":"x"}'


class TestHashing:
    """Reference vectors captured from RATTER's TypeScript implementations."""

    PAYLOAD = {"a": 5, "b": "x", "arr": [1, 2, True], "nested": {"k": "v"}}
    EXPECTED_PAYLOAD_HASH = (
        "sha256:bd64ba823fbd020eef526ae96e7e2b47467bc9331a93555cd3c6c16f230edf6b"
    )
    EXPECTED_CHAIN_HASH = (
        "sha256:95979f76d05e021d69bb7b452bf8b1d8a1941eb1b17c2aa982ec745078fce67c"
    )
    EXPECTED_SIGNATURE = "ArBwglA7aCejt6FMUK/uonzn468XPv0fDMUJE3IaGxs="

    def test_payload_hash_matches_reference(self):
        assert compute_payload_hash(self.PAYLOAD) == self.EXPECTED_PAYLOAD_HASH

    def test_chain_hash_matches_reference(self):
        chain = compute_chain_hash(GENESIS_CHAIN_HASH, self.EXPECTED_PAYLOAD_HASH, 5)
        assert chain == self.EXPECTED_CHAIN_HASH

    def test_signature_matches_reference(self):
        sig = generate_signature(f"{self.EXPECTED_PAYLOAD_HASH}:{self.EXPECTED_CHAIN_HASH}")
        assert sig == self.EXPECTED_SIGNATURE


class TestIngest:
    def test_single_event_stored_with_integrity(self):
        core = RatterCore()
        result = core.ingest_event(
            {
                "event_type": "process.started",
                "runtime_id": "rt_rosie_local",
                "instance_id": "inst_rosie_local_01",
                "session_id": "s1",
                "sequence_number": 1,
                "payload": {"a": 1},
            }
        )
        event = result["event"]
        assert result["status"] == "verified"
        assert event["integrity"]["previous_chain_hash"] == GENESIS_CHAIN_HASH
        assert event["integrity"]["payload_hash"] == compute_payload_hash({"a": 1})
        assert "signature" in event["integrity"]

    def test_sequence_auto_assigned_when_absent(self):
        core = RatterCore()
        first = core.ingest_event({"event_type": "session.started", "session_id": "s2"})
        second = core.ingest_event({"event_type": "process.started", "session_id": "s2"})
        assert first["event"]["sequence_number"] == 1
        assert second["event"]["sequence_number"] == 2

    def test_chain_links_events(self):
        core = RatterCore()
        r1 = core.ingest_event({"event_type": "session.started", "session_id": "s3"})
        r2 = core.ingest_event({"event_type": "process.started", "session_id": "s3"})
        assert r2["event"]["integrity"]["previous_chain_hash"] == (
            r1["event"]["integrity"]["chain_hash"]
        )

    def test_sequence_gap_detected(self):
        core = RatterCore()
        core.ingest_event(
            {"event_type": "session.started", "session_id": "s4", "sequence_number": 1}
        )
        gap = core.ingest_event(
            {"event_type": "command.completed", "session_id": "s4", "sequence_number": 5}
        )
        assert gap["status"] == "sequence_gap"

    def test_broken_chain_detected(self):
        core = RatterCore()
        first = core.ingest_event({"event_type": "session.started", "session_id": "s5"})
        broken = core.ingest_event(
            {
                "event_type": "process.started",
                "session_id": "s5",
                "integrity": {"previous_chain_hash": "sha256:deadbeef"},
            }
        )
        assert broken["status"] == "broken_chain"

    def test_session_created_and_counts(self):
        core = RatterCore()
        core.ingest_event({"event_type": "session.started", "session_id": "s6"})
        core.ingest_event({"event_type": "process.started", "session_id": "s6"})
        session = core.get_session("s6")
        assert session is not None
        assert session["event_count"] == 2
        assert session["status"] == "active"


class TestQueries:
    def test_timeline_sorted_by_sequence(self):
        core = RatterCore()
        for seq in (3, 1, 2, 4):
            core.ingest_event(
                {"event_type": f"e{seq}", "session_id": "t1", "sequence_number": seq}
            )
        timeline = core.get_timeline("t1")
        assert [e["sequence_number"] for e in timeline] == [1, 2, 3, 4]

    def test_integrity_verified_clean_session(self):
        core = RatterCore()
        for seq in (1, 2, 3):
            core.ingest_event(
                {"event_type": f"e{seq}", "session_id": "t2", "sequence_number": seq}
            )
        integrity = core.get_integrity("t2")
        assert integrity["is_verified"] is True
        assert integrity["sequence_gaps"] == []
        assert integrity["broken_links"] == []
        assert integrity["integrity_status"] == "verified"

    def test_integrity_gap_detected(self):
        core = RatterCore()
        core.ingest_event({"event_type": "e1", "session_id": "t3", "sequence_number": 1})
        core.ingest_event({"event_type": "e3", "session_id": "t3", "sequence_number": 3})
        integrity = core.get_integrity("t3")
        assert integrity["is_verified"] is False
        assert integrity["sequence_gaps"] == [3]


class TestSharedInstance:
    def test_singleton_identity(self):
        first = get_ratter_core()
        second = get_ratter_core()
        assert first is second


# ---------------------------------------------------------------------------
# PR #4 review fixes
# ---------------------------------------------------------------------------


class TestFix1TamperDetection:
    def test_payload_mutation_is_detected(self):
        core = RatterCore()
        core.ingest_events(
            [
                {"event_type": "session.started", "session_id": "tamper", "sequence_number": 1},
                {"event_type": "command.completed", "session_id": "tamper", "sequence_number": 2},
            ]
        )
        assert core.get_integrity("tamper")["is_verified"] is True
        # Mutate a retained payload post-ingest
        target = core.events[0]
        target["payload"]["injected"] = True
        integrity = core.get_integrity("tamper")
        assert integrity["is_verified"] is False
        assert target["event_id"] in integrity["broken_links"]

    def test_genesis_first_event_broken(self):
        # A first event classified broken_chain at ingest (e.g. caller lied
        # about previous_chain_hash) must NOT silently verify.
        core = RatterCore()
        core.ingest_event(
            {
                "event_type": "session.started",
                "session_id": "broken-first",
                "integrity": {"previous_chain_hash": "sha256:deadbeef"},
            }
        )
        assert core.get_integrity("broken-first")["is_verified"] is False


class TestFix2CanonicalJson:
    def test_unicode_and_non_finite_match_reference(self):
        # Reference vector captured against RATTER's TypeScript
        # canonicalizeJson on 2026-09-01.
        payload = {
            "text": "héllo 世界",
            "pos_inf": float("inf"),
            "neg_inf": float("-inf"),
            "nan": float("nan"),
            "nested": {"k": "v", "n": 5},
            "arr": [1, "日", True],
        }
        assert canonicalize_json(payload) == (
            '{"arr":[1,"日",true],"nan":null,"neg_inf":null,'
            '"nested":{"k":"v","n":5},"pos_inf":null,"text":"héllo 世界"}'
        )
        assert (
            compute_payload_hash(payload)
            == "sha256:476c93f8f3214c38def50e330c1545abd04807dfb5c7589f61bcacc245b9ac52"
        )
    def test_plain_integer_drops_float_suffix(self):
        # match JS: 5.0 canonicalizes as 5, not 5.0
        assert canonicalize_json({"n": 5.0}) == '{"n":5}'


class TestFix3TenantPreserved:
    def test_tenant_flows_through(self):
        core = RatterCore()
        core.ingest_event(
            {
                "event_type": "session.started",
                "session_id": "tenant-proof",
                "tenant_id": "tenant_tamper_target",
            }
        )
        core.ingest_event(
            {
                "event_type": "command.completed",
                "session_id": "tenant-proof",
                "tenant_id": "tenant_tamper_target",
                "integrity": {"previous_chain_hash": "sha256:deadbeef"},  # trigger alert
            }
        )
        core.ingest_event(
            {
                "event_type": "process.started",
                "session_id": "tenant-proof",
                "tenant_id": "tenant_tamper_target",
            }
        )
        session = core.get_session("tenant-proof")
        assert session["tenant_id"] == "tenant_tamper_target"
        for e in core.get_timeline("tenant-proof"):
            assert e["tenant_id"] == "tenant_tamper_target"
        alert = next(a for a in core.alerts if a["session_id"] == "tenant-proof")
        assert alert["tenant_id"] == "tenant_tamper_target"


class TestFix4FirstEventBrokenChain:
    def test_first_event_broken_chain_reported(self):
        core = RatterCore()
        core.ingest_event(
            {
                "event_type": "process.started",
                "session_id": "one-shot",
                "integrity": {"previous_chain_hash": "sha256:deadbeef"},
            }
        )
        report = core.get_integrity("one-shot")
        assert report["is_verified"] is False
        assert report["broken_links"]


class TestFix5BoundedRetention:
    def test_session_bound_caps(self):
        core = RatterCore(max_sessions=3, max_events=50, max_alerts=10)
        for i in range(5):
            sid = f"sess-{i}"
            core.ingest_events(
                [
                    {"event_type": "session.started", "session_id": sid, "sequence_number": 1},
                    {"event_type": "process.started", "session_id": sid, "sequence_number": 2},
                ]
            )
        # Only the newest 3 sessions remain
        assert len(core.sessions) == 3
        assert core.get_session("sess-0") is None
        assert core.get_session("sess-1") is None
        assert core.get_session("sess-4") is not None
        # Oldest events evicted with their sessions
        all_events_sessions = {e["session_id"] for e in core.events}
        assert len(all_events_sessions) == 3
        # Surviving session verifies cleanly
        assert core.get_integrity("sess-4")["is_verified"] is True

    def test_alerts_bound(self):
        core = RatterCore(max_sessions=100, max_events=1000, max_alerts=5)
        for i in range(10):
            core.ingest_event(
                {
                    "event_type": "command.completed",
                    "session_id": f"a{i}",
                    "sequence_number": 1,
                    "integrity": {"previous_chain_hash": "sha256:x"},
                }
            )
        assert len(core.alerts) <= 5


class TestFix6IncrementalIngest:
    def test_ingest_does_not_rescan_all_events(self, monkeypatch):
        # Lock down the naive rescan by instrumenting a sort over self.events
        # during ingest — it must not run.
        core = RatterCore()
        for i in range(10):
            core.ingest_event({"event_type": f"e{i}", "session_id": "inc"})

        calls = []
        real_sorted = sorted
        def probe_sort(obj, *a, **kw):
            if any(isinstance(x, dict) for x in list(obj)[:1]):
                calls.append(True)
            return real_sorted(obj, *a, **kw)
        monkeypatch.setattr("builtins.sorted", probe_sort)
        core.ingest_event({"event_type": "e10", "session_id": "inc"})
        assert not calls, "ingest performed a full events rescan"

    def test_new_events_chain_from_cached_state(self):
        core = RatterCore()
        core.ingest_event({"event_type": "e0", "session_id": "cont", "sequence_number": 1})
        core.ingest_event({"event_type": "e1", "session_id": "cont", "sequence_number": 2})
        core.ingest_event({"event_type": "e2", "session_id": "cont"})
        timeline = core.get_timeline("cont")
        assert [e["sequence_number"] for e in timeline] == [1, 2, 3]
        assert core.get_integrity("cont")["is_verified"] is True
