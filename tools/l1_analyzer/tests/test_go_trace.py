"""The Go runtime harness (L1.19 statement coverage, L1.20 shuffle determinism). The live
harness needs the go toolchain, so here the run boundary is stubbed and the deterministic
pieces are asserted: total parsing, the not-run guard, per-seed reasons, and n/a with a
reason rather than a guessed number. Pure assertions, no mocks of business logic."""

import subprocess

from l1_analyzer import go_trace


def _cp(rc, stdout=""):
    return subprocess.CompletedProcess([], rc, stdout, "")


def _cover_run(monkeypatch, *, profile_total="total:\t(statements)\t63.2%", test_rc=0, write_profile=True):
    """Stub go test (writes a profile if asked) + go tool cover + go version."""
    def fake(cmd, cwd, env, timeout_seconds):
        if "version" in cmd:
            return _cp(0, "go version go1.26.4 darwin/arm64")
        if "test" in cmd:
            for arg in cmd:
                if arg.startswith("-coverprofile=") and write_profile:
                    with open(arg.split("=", 1)[1], "w") as fh:
                        fh.write("mode: set\npkg/x.go:1.1,2.2 1 1\n")
            return _cp(test_rc, "ok  pkg 0.1s")
        if "cover" in cmd:
            return _cp(0, f"pkg/x.go:1:\tf\t100.0%\n{profile_total}\n")
        return _cp(0, "")
    monkeypatch.setattr(go_trace, "_go", lambda: "/usr/bin/go")
    monkeypatch.setattr(go_trace, "_run_untrusted", fake)


# --- L1.19 statement coverage -------------------------------------------------

def test_l19_na_without_go(monkeypatch, tmp_path):
    monkeypatch.setattr(go_trace, "_go", lambda: None)
    assert go_trace.decision_space_coverage(tmp_path, 30)["band"] == "n/a"


def test_l19_reports_statement_coverage_and_names_the_toolchain(monkeypatch, tmp_path):
    _cover_run(monkeypatch, profile_total="total:\t(statements)\t63.2%")
    r = go_trace.decision_space_coverage(tmp_path, 30)
    assert r["value"] == 63.2 and r["band"] == "Not Healthy"
    assert "statement coverage" in r["details"] and "go1.26.4" in r["details"]


def test_l19_na_when_no_profile_is_produced(monkeypatch, tmp_path):
    # a build error writes no profile: n/a with the reason, never a 0.0.
    _cover_run(monkeypatch, write_profile=False, test_rc=2)
    r = go_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "produced no data" in r["details"]


def test_l19_bands_follow_the_spec(monkeypatch, tmp_path):
    _cover_run(monkeypatch, profile_total="total:\t(statements)\t95.0%")
    assert go_trace.decision_space_coverage(tmp_path, 30)["band"] == "Healthy"
    _cover_run(monkeypatch, profile_total="total:\t(statements)\t40.0%")
    assert go_trace.decision_space_coverage(tmp_path, 30)["band"] == "Slop"


# --- L1.20 shuffle determinism ------------------------------------------------

def test_l20_all_green_is_healthy(monkeypatch, tmp_path):
    monkeypatch.setattr(go_trace, "_go", lambda: "/usr/bin/go")
    monkeypatch.setattr(go_trace, "_run_untrusted",
                        lambda cmd, **k: _cp(0, "go version go1.26" if "version" in cmd else "ok  pkg\tPASS"))
    r = go_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "5/5" and r["band"] == "Healthy" and "go1.26" in r["details"]


def test_l20_na_when_nothing_ran(monkeypatch, tmp_path):
    # no ok/FAIL/PASS marker means the module did not build or has no tests: n/a, not 0/5.
    monkeypatch.setattr(go_trace, "_go", lambda: "/usr/bin/go")
    monkeypatch.setattr(go_trace, "_run_untrusted",
                        lambda cmd, **k: _cp(0, "go version go1.26" if "version" in cmd else "no test files"))
    r = go_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "did not run" in r["details"]


def test_l20_surfaces_failing_seed_not_a_bare_score(monkeypatch, tmp_path):
    monkeypatch.setattr(go_trace, "_go", lambda: "/usr/bin/go")
    monkeypatch.setattr(go_trace, "_run_untrusted",
                        lambda cmd, **k: _cp(0, "go version") if "version" in cmd else _cp(1, "--- FAIL: TestX\nFAIL"))
    r = go_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "0/5" and r["band"] == "Slop" and "seed 1" in r["details"]


def test_ran_tests_detects_execution():
    assert go_trace._ran_tests("ok  pkg 0.1s")
    assert go_trace._ran_tests("--- FAIL: TestX")
    assert not go_trace._ran_tests("build failed: cannot find package")
