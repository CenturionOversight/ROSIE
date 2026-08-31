"""Shared pytest fixtures for the wrapper test suite."""
import pytest
from pathlib import Path

from wrapper.tools import set_workspace_root, set_policy
from wrapper.policy import ApprovalPolicy, ExecutionPolicy


@pytest.fixture(autouse=True)
def reset_global_state(monkeypatch):
    """Reset the global workspace root and policy before each test."""
    monkeypatch.setattr("wrapper.tools._workspace_root", None, raising=False)
    monkeypatch.setattr("wrapper.tools._policy", None, raising=False)
    monkeypatch.setattr("wrapper.tools._shell_executor", None, raising=False)


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """Provide a temporary workspace directory as the workspace root."""
    root = tmp_path.resolve()
    set_workspace_root(root)
    monkeypatch.setattr("wrapper.tools._workspace_root", root)
    return root


@pytest.fixture
def yolo_policy(monkeypatch):
    """Set a YOLO approval policy (auto-approve all)."""
    policy = ApprovalPolicy(ExecutionPolicy.YOLO)
    set_policy(policy)
    monkeypatch.setattr("wrapper.tools._policy", policy)
    return policy


@pytest.fixture
def auto_write_policy(monkeypatch):
    """Set an auto-write approval policy (auto-write, prompt shell)."""
    policy = ApprovalPolicy(ExecutionPolicy.AUTO_WRITE)
    set_policy(policy)
    monkeypatch.setattr("wrapper.tools._policy", policy)
    return policy


@pytest.fixture
def ask_policy(monkeypatch):
    """Set an ask approval policy (prompt for all)."""
    policy = ApprovalPolicy(ExecutionPolicy.ASK)
    set_policy(policy)
    monkeypatch.setattr("wrapper.tools._policy", policy)
    return policy
