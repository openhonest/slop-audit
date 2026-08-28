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
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

from l1_analyzer import incomplete
from l1_analyzer.boundary import boundary
from l1_analyzer.pytest_trace import (
    L1Result,
    _first_line,
    _na,
    _run_untrusted,
    coverage_verdict,
    determinism_tally,
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


@boundary
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
            covered, missed = counter.get("covered"), counter.get("missed")
            if covered is None or missed is None:
                # Both are required attributes of a JaCoCo counter element. One missing is a
                # malformed report, and defaulting it to zero would grade the project 0%
                # covered rather than saying the report could not be read.
                raise incomplete.refuse(
                    "L1.19 decision-space coverage",
                    "the JaCoCo BRANCH counter is missing its covered or missed attribute")
            return int(covered), int(missed)
    return 0, 0


def _coverage_verdict(branches: tuple[int, int] | None, returncode: int, jdk: str) -> L1Result:
    """L1.19 from a finished build and what the coverage report carried. No I/O, so it can be
    asserted as a value.

    `branches` is JaCoCo's (covered, missed) pair, or None when the build wrote no jacoco.xml
    at all. Absence is a case here rather than a pair of zeroes because the two say different
    things: no report means the plugin is not in the build, while a report of (0, 0) means the
    plugin ran and found nothing to cover. Both are n/a, and each names its own reason.

    The decision itself lives in pytest_trace, written once for every language whose tool
    hands back a covered-and-total pair. What stays here is Java's arithmetic, JaCoCo counts
    covered and MISSED so the total is their sum, and Java's sentences."""
    covered, total = (None, None) if branches is None else (branches[0], sum(branches))
    return coverage_verdict(
        covered=covered, total=total, returncode=returncode,
        no_report="Java branch coverage needs the JaCoCo plugin in the build "
                  "(jacoco.xml not produced)",
        nothing_to_cover="no enumerable decision branches found "
                         "(JaCoCo reported zero BRANCH counters)",
        how="JaCoCo BRANCH counters", toolchain=jdk)


class JavaTools(TypedDict):
    """A resolved Maven toolchain: the command to run, the environment that pins the JDK,
    and the JDK's name with its provenance for the details line."""
    maven: str
    env: dict[str, str]
    jdk: str


def _toolchain(repo: Path, timeout_seconds: float) -> tuple[L1Result | None, JavaTools | None]:
    """Either a refusal or a usable toolchain, never a half-resolved one. Exactly one of the
    two is None, so a caller that forgets the check gets a TypeError rather than a run
    against a toolchain that was never found.

    Both L1.19 and L1.20 carried these six lines. Two copies is two sets of preconditions
    that can drift: one indicator could learn a new one and the other keep running without
    it, and the panel would then report n/a for coverage and a number for determinism on a
    repo where neither could be measured."""
    reason = _unsupported_reason(repo)
    if reason is not None:
        return _na(reason), None
    # _unsupported_reason has already refused a repo with no Maven, so this cannot be None.
    # Re-checking here would be a guard against a contract the line above already holds.
    maven = _maven(repo)
    env, prov = _pin_jdk(repo, timeout_seconds)
    return None, {"maven": maven, "env": env, "jdk": _jdk(repo, timeout_seconds, env) + prov}


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.19 for Java: branch coverage from JaCoCo (`mvn test jacoco:report`). Bands match the
    spec: >90% Healthy, 60-90% Not Healthy, <60% Slop. `runtime_override` is accepted for a
    uniform harness signature and ignored: the project's build selects the runtime."""
    refusal, tools = _toolchain(repo, timeout_seconds)
    if refusal is not None:
        return refusal
    maven, env, jdk = tools["maven"], tools["env"], tools["jdk"]
    run = _run_untrusted([maven, "-q", "test", "jacoco:report"], cwd=repo, env=env, timeout_seconds=timeout_seconds)
    report = repo / "target" / "site" / "jacoco" / "jacoco.xml"
    if run.returncode == 124 or not report.exists():
        return _coverage_verdict(None, run.returncode, jdk)
    try:
        branches = _branch_totals(report.read_text())
    except (OSError, ET.ParseError):
        return _na("JaCoCo report was unreadable")
    return _coverage_verdict(branches, run.returncode, jdk)


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


def _determinism_verdict(outcomes: Iterable[tuple[int, str]], jdk: str) -> L1Result:
    """L1.20 for Java from finished randomized-order Maven runs. See
    pytest_trace.determinism_tally for the rules; only the words are here. Surefire takes a
    seed, so the position in the sequence IS the seed and is named as one."""
    return determinism_tally(
        outcomes,
        {"unit": "seed",
         "never_ran": f"no tests executed under {jdk}",
         "no_runs": "no randomized-order runs were made; determinism not measured",
         "describe": f"randomized-order runs passed cleanly (under {jdk})"},
        _ran_tests,
        _surefire_summary,
    )

def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.20 for Java: `mvn -Dsurefire.runOrder=random test` run `runs` times, counting the
    runs where the whole suite passes. Value is "passing/runs". Bands: 5/5 Healthy, 4/5 Not
    Healthy, <4/5 Slop. A run that does not build or runs no tests is not a determinism result,
    so return n/a with the reason rather than a misleading 0/5. When the suite runs but some
    tests fail, the failing seeds' Surefire counts are surfaced in `details`."""
    refusal, tools = _toolchain(repo, timeout_seconds)
    if refusal is not None:
        return refusal
    maven, env, jdk = tools["maven"], tools["env"], tools["jdk"]

    def outcomes() -> Iterable[tuple[int, str]]:
        # Lazy, so the verdict's return on a timed-out or never-run seed stops the rest.
        for _ in range(runs):
            run = _run_untrusted(
                [maven, "-q", "-Dsurefire.runOrder=random", "test"],
                cwd=repo, env=env, timeout_seconds=timeout_seconds,
            )
            yield run.returncode, (run.stdout or "") + (run.stderr or "")

    return _determinism_verdict(outcomes(), jdk)
