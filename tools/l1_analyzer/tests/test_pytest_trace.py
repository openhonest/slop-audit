"""L1.19 decision-space coverage must report n/a when the suite did not actually run,
never a 0.0 that reads as real-but-terrible coverage. A silent failure is a lie, and this
is the honesty tool auditing its own honesty. Pure assertions, the run boundary stubbed."""

import subprocess

from l1_analyzer import pytest_trace


def _fake_run(returncode, stdout=""):
    return lambda *a, **k: subprocess.CompletedProcess([], returncode, stdout, "")


def test_l19_is_na_when_the_suite_did_not_complete_a_valid_run(monkeypatch, tmp_path):
    # pytest exit 2 (interrupted), 3 (internal), 4 (usage/collection), 5 (no tests) are not
    # valid test runs -> n/a with the reason, never a coverage figure.
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m, exe=None: True)
    for rc in (2, 3, 4, 5):
        monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(rc))
        result = pytest_trace.decision_space_coverage(tmp_path, "python", 5)
        assert result["band"] == "n/a", f"exit {rc} must be n/a, not a number"
        assert result["value"] == "n/a"
        assert "did not complete a valid run" in result["details"]


def test_l19_no_tests_collected_names_the_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m, exe=None: True)
    monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(5))
    result = pytest_trace.decision_space_coverage(tmp_path, "python", 5)
    assert result["band"] == "n/a" and "collected no tests" in result["details"]


def test_l19_timeout_is_na(monkeypatch, tmp_path):
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m, exe=None: True)
    monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(124))
    result = pytest_trace.decision_space_coverage(tmp_path, "python", 5)
    assert result["band"] == "n/a" and "timed out" in result["details"]


def test_l19_is_na_without_a_python_target(tmp_path):
    result = pytest_trace.decision_space_coverage(tmp_path, "rust", 5)
    assert result["band"] == "n/a"


# --- L1.20 determinism: not-run guard, per-seed reasons, interpreter ----------

def test_l20_na_when_a_seed_does_not_complete_a_valid_run(monkeypatch, tmp_path):
    # exit 4 (collection/usage error) means the suite did not run, not that it is flaky.
    # It must be n/a with the reason, never a misleading 0/5 that reads as non-determinism.
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m, exe=None: True)
    monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(4))
    result = pytest_trace.test_determinism(tmp_path, "python", 5, 5)
    assert result["band"] == "n/a" and result["value"] == "n/a"
    assert "did not complete a valid run" in result["details"]


def test_l20_surfaces_the_failing_seed_counts_not_a_bare_score(monkeypatch, tmp_path):
    # The suite runs but a test fails every seed (exit 1). 0/5 is correct, but a bare 0/5 reads
    # as flakiness; the details must name why (the failure counts), so it is not a silent 0/5.
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m, exe=None: True)
    monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(1, "3 failed, 1219 passed in 10.0s\n"))
    result = pytest_trace.test_determinism(tmp_path, "python", 5, 5)
    assert result["value"] == "0/5" and result["band"] == "Slop"
    assert "3 failed, 1219 passed" in result["details"] and "seed 1" in result["details"]


def test_l20_all_green_is_healthy(monkeypatch, tmp_path):
    monkeypatch.setattr(pytest_trace, "_module_available", lambda m, exe=None: True)
    monkeypatch.setattr(pytest_trace, "_run_untrusted", _fake_run(0, "1222 passed in 10.0s\n"))
    result = pytest_trace.test_determinism(tmp_path, "python", 5, 5)
    assert result["value"] == "5/5" and result["band"] == "Healthy"


def test_pytest_summary_reads_the_last_counts_line():
    out = "collected 1222 items\n....\n3 failed, 1219 passed in 10.0s\n"
    assert pytest_trace._pytest_summary(out) == "3 failed, 1219 passed in 10.0s"
    assert pytest_trace._pytest_summary("no counts here") == "no summary line"


def test_interpreter_selects_the_named_python_over_the_default(monkeypatch):
    # None (the named Nothing) resolves to the analyzer's own interpreter; a path is used verbatim.
    import sys
    assert pytest_trace._interpreter(None) == sys.executable
    assert pytest_trace._interpreter("/opt/persistum/.venv/bin/python") == "/opt/persistum/.venv/bin/python"


def test_module_available_probes_the_named_interpreter(monkeypatch):
    seen = {}
    def fake(cmd, **k):
        seen["exe"] = cmd[0]
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake)
    pytest_trace._module_available("pytest", "/tgt/venv/bin/python")
    assert seen["exe"] == "/tgt/venv/bin/python"


# --- directory-insensitive interpreter detection ------------------------------

def test_detect_target_interpreter_finds_a_repo_venv(tmp_path):
    assert pytest_trace.detect_target_interpreter(tmp_path) is None
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("")   # existence is all detection needs
    assert pytest_trace.detect_target_interpreter(tmp_path) == str(venv / "python")


def test_resolve_interpreter_precedence(tmp_path):
    import sys
    # 1. an explicit override wins over everything.
    exe, prov = pytest_trace.resolve_interpreter(tmp_path, "/x/py")
    assert exe == "/x/py" and "--python" in prov
    # 2. else the target repo's own venv (this is what makes the audit dir-insensitive).
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("")
    exe, prov = pytest_trace.resolve_interpreter(tmp_path, None)
    assert exe == str(venv / "python") and "target venv" in prov
    # 3. else the analyzer's own interpreter (a repo with no venv).
    exe, prov = pytest_trace.resolve_interpreter(tmp_path / "no-venv-here", None)
    assert exe == sys.executable and "analyzer" in prov
