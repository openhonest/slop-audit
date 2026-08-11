"""Runtime harness for L1.19 / L1.20 on Java repositories - the Maven counterpart to
pytest_trace, rust_trace and go_trace. It actually executes the target project's own test
suite (untrusted code, in a new process group with a hard timeout, exactly like the other
paths) rather than reporting n/a.

- **L1.19 decision-space coverage**: branch coverage from JaCoCo. `./mvnw -q test
  jacoco:report` runs the suite and writes `target/site/jacoco/jacoco.xml`; the report-level
  `<counter type="BRANCH">` is the grand total of covered and missed branches across the
  project, so `covered / (covered + missed)` is the decision-space fraction. JaCoCo measures
  real branches, so this is the direct analogue of coverage.py's branch totals, and the
  details string says so.
- **L1.20 test determinism**: `./mvnw -q -Dsurefire.runOrder=random test` run five times,
  counting the runs where the whole suite passes. Surefire re-randomizes execution order per
  run, so that is the randomization source and no external plugin is needed.

Directory-insensitive by construction: Maven is invoked with `cwd=repo`, and the project's
own wrapper `./mvnw` (which pins the Maven version) is preferred over a system `mvn`, so the
project's build selects the toolchain whatever launched the analyzer. The resolved JDK
(`java -version`) is named in every measured result. Following the shared discipline, each
path returns an explicit *not measured* reason rather than a guessed number, and runs the
project's (untrusted) tests in a new process group with a hard timeout.

Maven only: a Gradle project (build.gradle, no pom.xml) reports n/a. `runtime_override` is
accepted for a uniform harness signature and ignored: the project's own build selects the
runtime.
"""

from __future__ import annotations

import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from l1_analyzer.pytest_trace import (
    L1Result,
    _first_line,
    _na,
    _run_untrusted,
    resolve_via_shim,
)

# Surefire's per-run summary, e.g. "Tests run: 12, Failures: 0, Errors: 0, Skipped: 0".
_SUREFIRE = re.compile(r"(Tests run: \d+[^\n]*)")


def _maven(repo: Path) -> str | None:
    """The Maven command for this project: its own wrapper `./mvnw` (which pins the Maven
    version) when present, else a system `mvn`. None when neither is available. This is what
    makes the audit directory-insensitive: the wrapper in the target repo wins over whatever
    Maven happens to be on PATH where the analyzer was launched."""
    wrapper = repo / "mvnw"
    if wrapper.exists():
        return str(wrapper)
    return shutil.which("mvn")


def _unsupported_reason(repo: Path) -> str | None:
    """The specific, actionable reason this project cannot be measured by the Maven harness,
    or None when it can. A Gradle project is named as not-yet-supported rather than silently
    failing, and a project with no pom.xml at all is told what it needs."""
    if not (repo / "pom.xml").exists():
        if (repo / "build.gradle").exists() or (repo / "build.gradle.kts").exists():
            return "Gradle Java projects not yet supported by this harness"
        return "needs a Maven build (no pom.xml found)"
    if _maven(repo) is None:
        return "needs Maven (mvn) on PATH or a ./mvnw wrapper in the repo"
    return None


def _pin_jdk(repo: Path, timeout_seconds: float) -> tuple[dict, str]:
    """(env, provenance): pin the JDK via a version manager (jenv/asdf/mise which java) when
    one resolves it for this repo, setting JAVA_HOME so Maven uses it rather than letting a
    homebrew java ahead of the shim on PATH silently win. Empty env and no provenance suffix
    when none resolves (the ambient java is used)."""
    java_path, note = resolve_via_shim(repo, "java", timeout_seconds)
    if java_path is None:
        return {}, ""
    bindir = Path(java_path).parent
    return {"JAVA_HOME": str(bindir.parent),
            "PATH": str(bindir) + os.pathsep + os.environ.get("PATH", "")}, f", {note}"


def _jdk(repo: Path, timeout_seconds: float, env: dict) -> str:
    """The JDK that runs the build, named so every measured result says which runtime measured
    it. `java -version` prints to stderr, so read it from there."""
    probe = _run_untrusted(["java", "-version"], cwd=repo, env=env, timeout_seconds=min(timeout_seconds, 30))
    return _first_line(probe.stderr or probe.stdout) if probe.returncode == 0 else "an unknown JDK"


def _branch_totals(xml_text: str) -> tuple[int, int]:
    """(covered, missed) branches from JaCoCo's report-level BRANCH counter - the grand total
    across every package, so there is no per-level double counting. (0, 0) when the report
    carries no BRANCH counter (a project with no branches to cover)."""
    root = ET.fromstring(xml_text)
    for counter in root.findall("counter"):
        if counter.get("type") == "BRANCH":
            return int(counter.get("covered", 0)), int(counter.get("missed", 0))
    return 0, 0


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.19 for Java: branch coverage from JaCoCo (`mvn test jacoco:report`). Bands match the
    spec: >90% Healthy, 60-90% Not Healthy, <60% Slop. `runtime_override` is accepted for a
    uniform harness signature and ignored: the project's build selects the runtime."""
    reason = _unsupported_reason(repo)
    if reason is not None:
        return _na(reason)
    maven = _maven(repo)
    env, prov = _pin_jdk(repo, timeout_seconds)
    jdk = _jdk(repo, timeout_seconds, env) + prov
    run = _run_untrusted([maven, "-q", "test", "jacoco:report"], cwd=repo, env=env, timeout_seconds=timeout_seconds)
    if run.returncode == 124:
        return _na("test suite timed out before coverage could be measured")
    # JaCoCo writes jacoco.xml only when the plugin is wired into the build and the suite
    # built and ran. No report means the coverage tool is not configured, not that coverage
    # is 0: n/a with the reason, never a 0.0 that reads as real-but-terrible coverage (a
    # silent failure is a lie).
    report = repo / "target" / "site" / "jacoco" / "jacoco.xml"
    if not report.exists():
        return _na("Java branch coverage needs the JaCoCo plugin in the build (jacoco.xml not produced)")
    try:
        covered, missed = _branch_totals(report.read_text())
    except (OSError, ET.ParseError):
        return _na("JaCoCo report was unreadable")

    total = covered + missed
    if total == 0:
        return _na("no enumerable decision branches found (JaCoCo reported zero BRANCH counters)")
    pct = covered / total * 100
    result_band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{covered}/{total} decision branches exercised by tests "
                   f"(JaCoCo BRANCH counters; {suite}; ran under {jdk})",
    }


def _ran_tests(output: str) -> bool:
    """True when Surefire actually ran tests (it prints a `Tests run:` summary), false when
    nothing ran - a compilation error, or a module with no tests. This is the difference
    between a real determinism data point and the suite never executing."""
    return "Tests run:" in output


def _surefire_summary(output: str) -> str:
    """The last Surefire `Tests run:` line (e.g. `Tests run: 12, Failures: 2, Errors: 0`), or
    a generic note. This is what turns a bare 0/5 into a reason a reader can act on."""
    matches = _SUREFIRE.findall(output)
    return matches[-1].strip() if matches else "no test summary line"


def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.20 for Java: `mvn -Dsurefire.runOrder=random test` run `runs` times, counting the
    runs where the whole suite passes. Value is "passing/runs". Bands: 5/5 Healthy, 4/5 Not
    Healthy, <4/5 Slop. A run that does not build or runs no tests is not a determinism result,
    so return n/a with the reason rather than a misleading 0/5. When the suite runs but some
    tests fail, the failing seeds' Surefire counts are surfaced in `details`."""
    reason = _unsupported_reason(repo)
    if reason is not None:
        return _na(reason)
    maven = _maven(repo)
    env, prov = _pin_jdk(repo, timeout_seconds)
    jdk = _jdk(repo, timeout_seconds, env) + prov

    passing = 0
    failing: list[str] = []
    for seed in range(1, runs + 1):
        run = _run_untrusted(
            [maven, "-q", "-Dsurefire.runOrder=random", "test"],
            cwd=repo, env=env, timeout_seconds=timeout_seconds,
        )
        output = (run.stdout or "") + (run.stderr or "")
        if run.returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if not _ran_tests(output):
            return _na(f"the suite did not run (seed {seed}: no tests executed under {jdk}); "
                       "determinism not measured")
        if run.returncode == 0:
            passing += 1
        else:
            failing.append(f"seed {seed}: {_surefire_summary(output)}")

    result_band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    details = f"{passing} of {runs} randomized-order runs passed cleanly (under {jdk})"
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}
