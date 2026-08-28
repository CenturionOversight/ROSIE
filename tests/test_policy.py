"""Tests for the ApprovalPolicy state machine (policy.py)."""
from wrapper.policy import ApprovalPolicy, ExecutionPolicy


class TestApprovalPolicyDefaults:
    def test_default_mode_is_ask(self):
        policy = ApprovalPolicy()
        assert policy.mode == ExecutionPolicy.ASK
        assert policy.mode_name == "ask"


class TestIsAutoApproved:
    def test_yolo_approves_all(self):
        policy = ApprovalPolicy(ExecutionPolicy.YOLO)
        assert policy.is_auto_approved("write") is True
        assert policy.is_auto_approved("shell") is True

    def test_auto_write_approves_writes(self):
        policy = ApprovalPolicy(ExecutionPolicy.AUTO_WRITE)
        assert policy.is_auto_approved("write") is True

    def test_auto_write_denies_shell(self):
        policy = ApprovalPolicy(ExecutionPolicy.AUTO_WRITE)
        assert policy.is_auto_approved("shell") is False

    def test_ask_denies_all(self):
        policy = ApprovalPolicy(ExecutionPolicy.ASK)
        assert policy.is_auto_approved("write") is False
        assert policy.is_auto_approved("shell") is False


class TestRequestApprovalAutoModes:
    def test_yolo_never_prompts(self):
        policy = ApprovalPolicy(ExecutionPolicy.YOLO)
        assert policy.request_approval("shell", "echo hi") is True

    def test_auto_write_auto_approves_write(self):
        policy = ApprovalPolicy(ExecutionPolicy.AUTO_WRITE)
        assert policy.request_approval("write", "write a file") is True

    def test_auto_write_still_prompts_shell(self, monkeypatch):
        policy = ApprovalPolicy(ExecutionPolicy.AUTO_WRITE)
        monkeypatch.setattr("builtins.input", lambda _: "y")
        result = policy.request_approval("shell", "run echo")
        assert isinstance(result, bool)


class TestLiveUpgrade:
    def test_always_switches_to_yolo(self, monkeypatch, capsys):
        policy = ApprovalPolicy(ExecutionPolicy.ASK)
        monkeypatch.setattr("builtins.input", lambda _: "a")
        assert policy.request_approval("write", "desc") is True
        assert policy.mode == ExecutionPolicy.YOLO

    def test_no_still_in_ask(self, monkeypatch):
        policy = ApprovalPolicy(ExecutionPolicy.ASK)
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert policy.request_approval("write", "desc") is False
        assert policy.mode == ExecutionPolicy.ASK

    def test_yes_does_not_upgrade(self, monkeypatch):
        policy = ApprovalPolicy(ExecutionPolicy.ASK)
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert policy.request_approval("write", "desc") is True
        assert policy.mode == ExecutionPolicy.ASK


class TestUpdateFromFlags:
    def test_yolo_flag_overrides_auto_write(self):
        policy = ApprovalPolicy(ExecutionPolicy.ASK)
        policy.update_from_flags(yolo=True, auto_write=True)
        assert policy.mode == ExecutionPolicy.YOLO

    def test_auto_write_flag(self):
        policy = ApprovalPolicy(ExecutionPolicy.ASK)
        policy.update_from_flags(yolo=False, auto_write=True)
        assert policy.mode == ExecutionPolicy.AUTO_WRITE

    def test_neither_flag(self):
        policy = ApprovalPolicy(ExecutionPolicy.YOLO)
        policy.update_from_flags(yolo=False, auto_write=False)
        assert policy.mode == ExecutionPolicy.YOLO

    def test_default_stays_ask(self):
        policy = ApprovalPolicy(ExecutionPolicy.ASK)
        policy.update_from_flags(yolo=False, auto_write=False)
        assert policy.mode == ExecutionPolicy.ASK
