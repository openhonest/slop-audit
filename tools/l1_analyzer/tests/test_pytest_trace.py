"""L1.19 decision-space coverage must report n/a when the suite did not actually run,
never a 0.0 that reads as real-but-terrible coverage. A silent failure is a lie, and this
is the honesty tool auditing its own honesty. Pure assertions, the run boundary stubbed."""

import subprocess

from l1_analyzer import pytest_trace


def _fake_run(returncode):
    return lambda *a, **k: subprocess.CompletedProcess([], returncode, "", "")


def test_l19_is_na_when_the_suite_did_not_complete_a_valid_run(monkeypatch, tmp_path):
    # pytest exit 2 (interrupted), 3 (internal), 4 (usage/collection), 5 (no tests) are not
    # valid test runs -> n/a with the reason, never a coverage figure.
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m: True)
    for rc in (2, 3, 4, 5):
        monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(rc))
        result = pytest_trace.decision_space_coverage(tmp_path, "python", 5)
        assert result["band"] == "n/a", f"exit {rc} must be n/a, not a number"
        assert result["value"] == "n/a"
        assert "did not complete a valid run" in result["details"]


def test_l19_no_tests_collected_names_the_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m: True)
    monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(5))
    result = pytest_trace.decision_space_coverage(tmp_path, "python", 5)
    assert result["band"] == "n/a" and "collected no tests" in result["details"]


def test_l19_timeout_is_na(monkeypatch, tmp_path):
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m: True)
    monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(124))
    result = pytest_trace.decision_space_coverage(tmp_path, "python", 5)
    assert result["band"] == "n/a" and "timed out" in result["details"]


def test_l19_is_na_without_a_python_target(tmp_path):
    result = pytest_trace.decision_space_coverage(tmp_path, "rust", 5)
    assert result["band"] == "n/a"
