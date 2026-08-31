"""Regression tests for output-bound and timeout contracts."""

from wrapper.output_bounds import box_output, format_shell_result


def test_box_output_nonpositive_budget_is_clamped_to_one():
    assert box_output("abcdef", max_chars=0) == "a"
    assert box_output("abcdef", max_chars=-10) == "a"


def test_timeout_forces_exit_code_minus_one():
    result = format_shell_result(
        "sleep 10",
        stdout="partial",
        stderr="",
        exit_code=0,
        timed_out=True,
        timeout_seconds=1,
    )
    assert "EXIT_CODE: -1" in result
    assert "TIMED_OUT: true" in result
