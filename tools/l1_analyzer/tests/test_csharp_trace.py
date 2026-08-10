"""The C# runtime harness (L1.19 Cobertura branch coverage, L1.20 repeat-run determinism).
The live harness needs the dotnet SDK, so here the run boundary is stubbed and the
deterministic pieces are asserted: branch-rate parsing, the not-run guard, the coverage-missing
n/a, and per-run failure surfacing rather than a guessed number. Pure assertions, no mocks of
business logic."""

import subprocess

from l1_analyzer import csharp_trace

_COBERTURA = '<coverage line-rate="0.9" branch-rate="0.632" version="1.9">'


def _cp(rc, stdout=""):
    return subprocess.CompletedProcess([], rc, stdout, "")


def _cover_run(monkeypatch, *, branch_rate="0.632", test_rc=0, write_report=True):
    """Stub dotnet test (writes a Cobertura report into the results directory if asked) plus
    dotnet --version."""
    def fake(cmd, cwd, env, timeout_seconds):
        if "--version" in cmd:
            return _cp(0, "8.0.404")
        if "test" in cmd:
            if "--results-directory" in cmd and write_report:
                from pathlib import Path
                out = Path(cmd[cmd.index("--results-directory") + 1]) / "guid"
                out.mkdir(parents=True, exist_ok=True)
                (out / "coverage.cobertura.xml").write_text(
                    f'<coverage line-rate="0.9" branch-rate="{branch_rate}" version="1.9"></coverage>')
            return _cp(test_rc, "Passed!  - Failed:     0, Passed:     5, Skipped:     0, Total:     5")
        return _cp(0, "")
    monkeypatch.setattr(csharp_trace, "_dotnet", lambda: "/usr/bin/dotnet")
    monkeypatch.setattr(csharp_trace, "_run_untrusted", fake)


# --- L1.19 branch coverage ----------------------------------------------------

def test_l19_na_without_dotnet(monkeypatch, tmp_path):
    monkeypatch.setattr(csharp_trace, "_dotnet", lambda: None)
    r = csharp_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "dotnet SDK in PATH" in r["details"]


def test_l19_reports_branch_coverage_and_names_the_sdk(monkeypatch, tmp_path):
    _cover_run(monkeypatch, branch_rate="0.632")
    r = csharp_trace.decision_space_coverage(tmp_path, 30)
    assert r["value"] == 63.2 and r["band"] == "Not Healthy"
    assert "branch coverage" in r["details"] and "dotnet 8.0.404" in r["details"]


def test_l19_na_when_no_cobertura_is_produced(monkeypatch, tmp_path):
    # coverlet not wired in writes no report: n/a with the actionable reason, never a 0.0.
    _cover_run(monkeypatch, write_report=False, test_rc=1)
    r = csharp_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "coverlet.collector" in r["details"]


def test_l19_bands_follow_the_spec(monkeypatch, tmp_path):
    _cover_run(monkeypatch, branch_rate="0.95")
    assert csharp_trace.decision_space_coverage(tmp_path, 30)["band"] == "Healthy"
    _cover_run(monkeypatch, branch_rate="0.40")
    assert csharp_trace.decision_space_coverage(tmp_path, 30)["band"] == "Slop"


# --- L1.20 repeat-run determinism ---------------------------------------------

def test_l20_all_green_is_healthy(monkeypatch, tmp_path):
    monkeypatch.setattr(csharp_trace, "_dotnet", lambda: "/usr/bin/dotnet")
    monkeypatch.setattr(csharp_trace, "_run_untrusted",
                        lambda cmd, **k: _cp(0, "8.0.404" if "--version" in cmd else "Passed!  - Total: 5"))
    r = csharp_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "5/5" and r["band"] == "Healthy" and "dotnet 8.0.404" in r["details"]
    assert "scheduler-varied" in r["details"]


def test_l20_na_when_nothing_ran(monkeypatch, tmp_path):
    # no Passed!/Failed!/Total marker means no project built or no tests: n/a, not 0/5.
    monkeypatch.setattr(csharp_trace, "_dotnet", lambda: "/usr/bin/dotnet")
    monkeypatch.setattr(csharp_trace, "_run_untrusted",
                        lambda cmd, **k: _cp(0, "8.0.404") if "--version" in cmd else _cp(1, "Build FAILED."))
    r = csharp_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "did not run" in r["details"]


def test_l20_surfaces_failing_run_not_a_bare_score(monkeypatch, tmp_path):
    monkeypatch.setattr(csharp_trace, "_dotnet", lambda: "/usr/bin/dotnet")
    monkeypatch.setattr(csharp_trace, "_run_untrusted",
                        lambda cmd, **k: _cp(0, "8.0.404") if "--version" in cmd
                        else _cp(1, "Failed!  - Failed:     2, Passed:     3, Total:     5"))
    r = csharp_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "0/5" and r["band"] == "Slop" and "run 1" in r["details"]


def test_ran_tests_detects_execution():
    assert csharp_trace._ran_tests("Passed!  - Failed: 0, Total: 5")
    assert csharp_trace._ran_tests("Failed!  - Failed: 2, Total: 5")
    assert not csharp_trace._ran_tests("Build FAILED. error CS0246")
