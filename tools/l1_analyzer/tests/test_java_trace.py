"""The Java runtime harness (L1.19 JaCoCo branch coverage, L1.20 Surefire random-order
determinism). The live harness needs Maven and a JDK, so here the run boundary is stubbed
and the deterministic pieces are asserted: BRANCH-counter parsing, the not-run guard, the
coverage-missing n/a, per-seed failure reasons, and n/a with a reason rather than a guessed
number. Pure assertions, no mocks of business logic."""

import subprocess

from l1_analyzer import java_trace


def _cp(rc, stdout="", stderr=""):
    return subprocess.CompletedProcess([], rc, stdout, stderr)


_JAVA_VERSION = 'openjdk version "26.0.1" 2026-04-21'


def _branch_xml(covered, missed):
    return (f'<report name="x"><counter type="INSTRUCTION" missed="1" covered="9"/>'
            f'<counter type="BRANCH" missed="{missed}" covered="{covered}"/></report>')


def _cover_run(monkeypatch, tmp_path, *, covered=12, missed=7, test_rc=0, write_report=True):
    """Stub java -version + `mvn test jacoco:report` (writes jacoco.xml if asked)."""
    (tmp_path / "pom.xml").write_text("<project/>")

    def fake(cmd, cwd, env, timeout_seconds):
        if "-version" in cmd:
            return _cp(0, stderr=_JAVA_VERSION)
        if write_report:
            site = tmp_path / "target" / "site" / "jacoco"
            site.mkdir(parents=True, exist_ok=True)
            (site / "jacoco.xml").write_text(_branch_xml(covered, missed))
        return _cp(test_rc, "BUILD SUCCESS" if test_rc == 0 else "BUILD FAILURE")

    monkeypatch.setattr(java_trace, "_maven", lambda repo: "/usr/bin/mvn")
    monkeypatch.setattr(java_trace, "_run_untrusted", fake)


# --- L1.19 JaCoCo branch coverage ---------------------------------------------

def test_l19_reports_branch_coverage_and_names_the_jdk(monkeypatch, tmp_path):
    _cover_run(monkeypatch, tmp_path, covered=12, missed=7)  # 12/19 = 63.2%
    r = java_trace.decision_space_coverage(tmp_path, 30)
    assert r["value"] == 63.2 and r["band"] == "Not Healthy"
    assert "decision branches" in r["details"] and "26.0.1" in r["details"]


def test_l19_na_for_gradle(monkeypatch, tmp_path):
    # build.gradle without pom.xml: named as not-yet-supported, never a guessed number.
    (tmp_path / "build.gradle").write_text("")
    monkeypatch.setattr(java_trace, "_maven", lambda repo: "/usr/bin/mvn")
    r = java_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "Gradle" in r["details"]


def test_l19_na_when_jacoco_report_is_missing(monkeypatch, tmp_path):
    # the JaCoCo plugin is not wired in, so no jacoco.xml: n/a with the reason, never a 0.0.
    _cover_run(monkeypatch, tmp_path, write_report=False, test_rc=1)
    r = java_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "jacoco.xml not produced" in r["details"]


def test_l19_bands_follow_the_spec(monkeypatch, tmp_path):
    _cover_run(monkeypatch, tmp_path, covered=95, missed=5)   # 95%
    assert java_trace.decision_space_coverage(tmp_path, 30)["band"] == "Healthy"
    _cover_run(monkeypatch, tmp_path, covered=40, missed=60)  # 40%
    assert java_trace.decision_space_coverage(tmp_path, 30)["band"] == "Slop"


# --- L1.20 Surefire random-order determinism ----------------------------------

def _det_run(monkeypatch, tmp_path, test_output, test_rc):
    (tmp_path / "pom.xml").write_text("<project/>")
    monkeypatch.setattr(java_trace, "_maven", lambda repo: "/usr/bin/mvn")

    def fake(cmd, cwd, env, timeout_seconds):
        if "-version" in cmd:
            return _cp(0, stderr=_JAVA_VERSION)
        return _cp(test_rc, test_output)

    monkeypatch.setattr(java_trace, "_run_untrusted", fake)


def test_l20_all_green_is_healthy(monkeypatch, tmp_path):
    _det_run(monkeypatch, tmp_path, "Tests run: 12, Failures: 0, Errors: 0, Skipped: 0", 0)
    r = java_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "5/5" and r["band"] == "Healthy" and "26.0.1" in r["details"]


def test_l20_na_when_nothing_ran(monkeypatch, tmp_path):
    # no "Tests run:" marker means a compile error or no tests: n/a, not 0/5.
    _det_run(monkeypatch, tmp_path, "[ERROR] COMPILATION ERROR\nBUILD FAILURE", 1)
    r = java_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "did not run" in r["details"]


def test_l20_surfaces_failing_seed_not_a_bare_score(monkeypatch, tmp_path):
    _det_run(monkeypatch, tmp_path, "Tests run: 12, Failures: 2, Errors: 0, Skipped: 0\nBUILD FAILURE", 1)
    r = java_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "0/5" and r["band"] == "Slop"
    assert "seed 1" in r["details"] and "Failures: 2" in r["details"]


def test_ran_tests_detects_execution():
    assert java_trace._ran_tests("Tests run: 5, Failures: 0, Errors: 0")
    assert not java_trace._ran_tests("[ERROR] COMPILATION ERROR : cannot find symbol")
