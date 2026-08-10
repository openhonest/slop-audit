"""The C runtime harness (L1.19 best-effort gcov/lcov line coverage, L1.20 honest n/a - C has
no standard test-order randomizer). The live harness needs cc + make + lcov, so here the run
boundary and the tool-presence probes are stubbed and the deterministic pieces are asserted:
lcov total parsing, the compiler named in details, and n/a with an actionable reason rather
than a guessed number. Pure assertions, no mocks of business logic."""

import subprocess

from l1_analyzer import c_trace


def _cp(rc, stdout=""):
    return subprocess.CompletedProcess([], rc, stdout, "")


def _cov_run(monkeypatch, tmp_path, *, lines="  lines......: 87.5% (700 of 800 lines)",
             build_rc=0, have_lcov=True):
    """Stub cc --version + make <target> + lcov (--capture/--summary), and give tmp_path a
    Makefile with a `test` target so coverage takes the measured path."""
    (tmp_path / "Makefile").write_text("test:\n\t./run_tests\n")

    def fake(cmd, cwd, env, timeout_seconds):
        if "--version" in cmd:
            return _cp(0, "cc (Ubuntu 13.2.0-4ubuntu3) 13.2.0")
        if cmd[0] == "make":
            return _cp(build_rc, "running tests")
        if "--summary" in cmd:
            return _cp(0, f"Reading tracefile\nSummary coverage rate:\n{lines}\n")
        return _cp(0, "")  # --capture

    monkeypatch.setattr(c_trace, "_cc", lambda: "/usr/bin/cc")
    monkeypatch.setattr(c_trace, "_lcov", lambda: "/usr/bin/lcov" if have_lcov else None)
    monkeypatch.setattr(c_trace, "_run_untrusted", fake)


# --- helpers ------------------------------------------------------------------

def test_make_target_detects_test_and_check(tmp_path):
    (tmp_path / "Makefile").write_text("all:\n\tgcc -o app main.c\ncheck:\n\t./t\n")
    assert c_trace._make_target(tmp_path) == "check"
    (tmp_path / "Makefile").write_text("all:\n\tgcc -o app main.c\n")
    assert c_trace._make_target(tmp_path) is None
    (tmp_path / "Makefile").unlink()
    assert c_trace._make_target(tmp_path) is None


# --- L1.19 line coverage (best-effort gcov/lcov) ------------------------------

def test_l19_na_without_cc(monkeypatch, tmp_path):
    monkeypatch.setattr(c_trace, "_cc", lambda: None)
    assert c_trace.decision_space_coverage(tmp_path, 30)["band"] == "n/a"


def test_l19_reports_line_coverage_and_names_the_compiler(monkeypatch, tmp_path):
    _cov_run(monkeypatch, tmp_path, lines="  lines......: 63.2% (632 of 1000 lines)")
    r = c_trace.decision_space_coverage(tmp_path, 30)
    assert r["value"] == 63.2 and r["band"] == "Not Healthy"
    assert "line coverage" in r["details"] and "13.2.0" in r["details"]


def test_l19_na_without_make_test_target(monkeypatch, tmp_path):
    # no Makefile test/check target: honest n/a with an actionable reason, never a 0.0.
    monkeypatch.setattr(c_trace, "_cc", lambda: "/usr/bin/cc")
    monkeypatch.setattr(c_trace, "_run_untrusted", lambda cmd, **k: _cp(0, "cc 13.2.0"))
    r = c_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "no Makefile test/check target found" in r["details"]


def test_l19_na_without_lcov(monkeypatch, tmp_path):
    _cov_run(monkeypatch, tmp_path, have_lcov=False)
    r = c_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "lcov" in r["details"]


def test_l19_na_when_gcov_produced_no_lines(monkeypatch, tmp_path):
    # 0 of 0 lines means the instrumented build ran nothing: n/a, not Slop 0.0.
    _cov_run(monkeypatch, tmp_path, lines="  lines......: 0.0% (0 of 0 lines)")
    r = c_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "no gcov lines" in r["details"]


def test_l19_bands_follow_the_spec(monkeypatch, tmp_path):
    _cov_run(monkeypatch, tmp_path, lines="  lines......: 95.0% (950 of 1000 lines)")
    assert c_trace.decision_space_coverage(tmp_path, 30)["band"] == "Healthy"
    _cov_run(monkeypatch, tmp_path, lines="  lines......: 40.0% (400 of 1000 lines)")
    assert c_trace.decision_space_coverage(tmp_path, 30)["band"] == "Slop"


# --- L1.20 determinism (honest n/a - no standard randomizer) ------------------

def test_l20_na_without_cc(monkeypatch, tmp_path):
    monkeypatch.setattr(c_trace, "_cc", lambda: None)
    assert c_trace.test_determinism(tmp_path, 5, 30)["band"] == "n/a"


def test_l20_na_no_randomizer_but_names_the_compiler(monkeypatch, tmp_path):
    # C has no test-order randomizer: n/a with the reason and the compiler named, never 0/5.
    monkeypatch.setattr(c_trace, "_cc", lambda: "/usr/bin/cc")
    monkeypatch.setattr(c_trace, "_run_untrusted",
                        lambda cmd, **k: _cp(0, "cc (Ubuntu 13.2.0-4ubuntu3) 13.2.0"))
    r = c_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "n/a" and r["band"] == "n/a"
    assert "no standard test-order randomizer" in r["details"] and "13.2.0" in r["details"]
