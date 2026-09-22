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
  run, so that is the randomization source and no external plugin is needed. Whether a run
  executed any tests, and how many failed, is read from the XML files Surefire writes under
  `target/surefire-reports/`, never from the console, because `-q` suppresses the console
  summary.

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
from typing import Literal, TypedDict

from l1_analyzer import incomplete, toolchain
from l1_analyzer.boundary import boundary
from l1_analyzer.pytest_trace import (
    L1Result,
    _na,
    _run_untrusted,
    coverage_verdict,
    determinism_tally,
    resolve_via_shim,
)

# Surefire's per-run summary, e.g. "Tests run: 12, Failures: 0, Errors: 0, Skipped: 0".
_SUREFIRE = re.compile(r"(Tests run: \d+[^\n]*)")


_NO_MAVEN = "needs Maven (mvn) on PATH or a ./mvnw wrapper in the repo"


@boundary
def _maven(repo: Path) -> str | None:
    """The Maven command for this project: its own wrapper `./mvnw` (which pins the Maven
    version) when present, else a system `mvn`. None when neither is available. This is what
    makes the audit directory-insensitive: the wrapper in the target repo wins over whatever
    Maven happens to be on PATH where the analyzer was launched."""
    wrapper = repo / "mvnw"
    if wrapper.exists():
        return str(wrapper)
    return shutil.which("mvn")


@boundary
def _unsupported_reason(repo: Path, maven: str | None) -> str | None:
    """The specific, actionable reason this project cannot be measured by the Maven harness,
    or None when it can. A Gradle project is named as not-yet-supported rather than silently
    failing, and a project with no pom.xml at all is told what it needs.

    The command it judges is passed in rather than looked up here. This function decides
    that the repo HAS one, `_toolchain` then called `_maven` a second time to use it, and a
    comment carried the promise that the two calls agreed. Two reads of the filesystem are
    two answers, and the promise is false for any repo that changes between them. One read
    now, at the caller, judged here."""
    if not (repo / "pom.xml").exists():
        if (repo / "build.gradle").exists() or (repo / "build.gradle.kts").exists():
            return "Gradle Java projects not yet supported by this harness"
        return "needs a Maven build (no pom.xml found)"
    if maven is None:
        return _NO_MAVEN
    return None


@boundary
def _pin_jdk(repo: Path, timeout_seconds: float) -> tuple[dict[str, str], str]:
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
    return toolchain.named(probe.stderr, probe.returncode, unknown="an unknown JDK")


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


def _coverage_verdict(branches: tuple[int, int] | None, returncode: int, jdk: str,
                      timeout_seconds: float) -> L1Result:
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
        timeout_seconds=timeout_seconds,
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


class Refused(TypedDict):
    """No toolchain, and the result the indicator returns instead."""
    ok: Literal[False]
    refusal: L1Result


class Resolved(TypedDict):
    """A toolchain, and nothing to refuse."""
    ok: Literal[True]
    tools: JavaTools


def _toolchain(repo: Path, timeout_seconds: float) -> Refused | Resolved:
    """Either a refusal or a usable toolchain, never a half-resolved one.

    It returned the pair `(refusal, tools)` with this docstring promising exactly one of
    them was None. The type permitted (None, None) and (a refusal, a toolchain) equally, and
    nothing enforced the promise. Both indicators then indexed `tools` on the line after the
    refusal check, so the promise was the only thing between them and a stack trace.

    Tagged instead. `ok` says which case it is, the other half is absent rather than None,
    and reading it is a KeyError at the line that read it.

    Both L1.19 and L1.20 carried these six lines. Two copies is two sets of preconditions
    that can drift: one indicator could learn a new one and the other keep running without
    it, and the panel would then report n/a for coverage and a number for determinism on a
    repo where neither could be measured."""
    maven = _maven(repo)
    reason = _unsupported_reason(repo, maven)
    if reason is not None:
        return {"ok": False, "refusal": _na(reason)}
    if maven is None:
        # Not reachable by argument: with a pom.xml the line above refuses a missing Maven,
        # and without one it refuses the pom. Written as a branch rather than an assertion
        # because the argument holds over today's `_unsupported_reason` and this file is the
        # only place that knows it, so a rule added there would silently make it false.
        return {"ok": False, "refusal": _na(_NO_MAVEN)}
    env, prov = _pin_jdk(repo, timeout_seconds)
    return {"ok": True,
            "tools": {"maven": maven, "env": env,
                      "jdk": _jdk(repo, timeout_seconds, env) + prov}}


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.19 for Java: branch coverage from JaCoCo (`mvn test jacoco:report`). Bands match the
    spec: >90% Healthy, 60-90% Not Healthy, <60% Slop. `runtime_override` is accepted for a
    uniform harness signature and ignored: the project's build selects the runtime."""
    answer = _toolchain(repo, timeout_seconds)
    if answer["ok"] is False:
        return answer["refusal"]
    tools = answer["tools"]
    maven, env, jdk = tools["maven"], tools["env"], tools["jdk"]
    run = _run_untrusted([maven, "-q", "test", "jacoco:report"], cwd=repo, env=env, timeout_seconds=timeout_seconds)
    report = repo / "target" / "site" / "jacoco" / "jacoco.xml"
    if run.returncode == 124 or not report.exists():
        return _coverage_verdict(None, run.returncode, jdk, timeout_seconds)
    try:
        branches = _branch_totals(report.read_text())
    except (OSError, ET.ParseError):
        return _na("JaCoCo report was unreadable")
    return _coverage_verdict(branches, run.returncode, jdk, timeout_seconds)


def _ran_tests(evidence: str) -> bool:
    """True when Surefire actually ran tests, false when nothing ran - a compilation error,
    or a module with no tests. This is the difference between a real determinism data point
    and the suite never executing."""
    return "Tests run:" in evidence


def _surefire_summary(evidence: str) -> str:
    """The Surefire count line (e.g. `Tests run: 12, Failures: 2, Errors: 0, Skipped: 0`), or
    a generic note. This is what turns a bare 0/5 into a reason a reader can act on."""
    matches = _SUREFIRE.findall(evidence)
    return matches[-1].strip() if matches else "no test summary line"


_NO_REPORTS = "Surefire wrote no test report"
_UNREADABLE_REPORT = "a Surefire test report was unreadable"

# Surefire's own totals, the attributes it writes on every <testsuite> element.
_COUNTED = ("tests", "failures", "errors", "skipped")


@boundary
def _reports(repo: Path) -> list[Path]:
    """Every Surefire result file under the repo, one per test class, in each module's
    `target/surefire-reports/`. Globbed across the whole tree so a multi-module build counts
    all its modules and not just the root."""
    return sorted(repo.glob("**/target/surefire-reports/TEST-*.xml"))


@boundary
def _clear_reports(repo: Path) -> None:
    """Delete the previous run's Surefire results before starting the next one.

    Maven leaves them on disk. Without this, a seed that fails to compile inherits the
    reports the seed before it wrote, and the harness reads a suite that never ran this time
    as a suite that ran and passed."""
    for report in _reports(repo):
        report.unlink(missing_ok=True)


@boundary
def _surefire_evidence(repo: Path) -> str:
    """What Surefire recorded about the run that just finished, as the `Tests run:` line the
    readers above expect, or a sentence saying why there is no count.

    Maven's console log used to be the source, and `-q` is on every command this module runs
    for the same reason it is on the coverage command: to keep an untrusted project's build
    chatter out of the result. But `-q` suppresses INFO, and Surefire's `Tests run:` summary
    is an INFO line. So the console said nothing, `_ran_tests` read nothing as no tests, and
    EVERY Maven project on earth got "the suite did not run" from this harness. The fixture
    at hand ran one test, passed, and was reported as having executed none.

    One fact with two owners: the console log and the XML reports both claimed to say
    whether tests ran, and the quiet flag silently retired one of them. The XML is what
    Surefire writes for machines and `-q` does not touch it, so read that and let the console
    go back to being chatter. Coverage already worked this way, reading jacoco.xml rather
    than the log, which is why coverage kept measuring while determinism refused."""
    reports = _reports(repo)
    if not reports:
        return _NO_REPORTS
    totals = dict.fromkeys(_COUNTED, 0)
    for report in reports:
        try:
            suite = ET.fromstring(report.read_text())
        except (OSError, ET.ParseError):
            return _UNREADABLE_REPORT
        for name in _COUNTED:
            totals[name] += int(suite.get(name) or 0)
    if totals["tests"] == 0:
        return _NO_REPORTS
    return (f"Tests run: {totals['tests']}, Failures: {totals['failures']}, "
            f"Errors: {totals['errors']}, Skipped: {totals['skipped']}")


def _determinism_verdict(outcomes: Iterable[tuple[int, str]], jdk: str,
                         timeout_seconds: float) -> L1Result:
    """L1.20 for Java from finished randomized-order Maven runs. See
    pytest_trace.determinism_tally for the rules; only the words are here. Surefire takes a
    seed, so the position in the sequence IS the seed and is named as one."""
    return determinism_tally(
        outcomes,
        {"unit": "seed",
         "timed_out": "a seed timed out",
         "no_runs": "no randomized-order runs were made; determinism not measured",
         "describe": f"randomized-order runs passed cleanly (under {jdk})"},
        _ran_tests,
        _surefire_summary,
        # Two ways to have no count, and they are different news. No report at all means
        # Maven never got as far as running the suite. An unreadable one means it did and we
        # cannot tell what happened, which is a broken measurement and not a broken project.
        lambda _returncode, evidence: f"{evidence} under {jdk}",
        timeout_seconds=timeout_seconds,
    )

def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.20 for Java: `mvn -Dsurefire.runOrder=random test` run `runs` times, counting the
    runs where the whole suite passes. Value is "passing/runs". Bands: 5/5 Healthy, 4/5 Not
    Healthy, <4/5 Slop. A run that does not build or runs no tests is not a determinism result,
    so return n/a with the reason rather than a misleading 0/5. When the suite runs but some
    tests fail, the failing seeds' Surefire counts are surfaced in `details`."""
    answer = _toolchain(repo, timeout_seconds)
    if answer["ok"] is False:
        return answer["refusal"]
    tools = answer["tools"]
    maven, env, jdk = tools["maven"], tools["env"], tools["jdk"]

    def outcomes() -> Iterable[tuple[int, str]]:
        # Lazy, so the verdict's return on a timed-out or never-run seed stops the rest.
        for _ in range(runs):
            _clear_reports(repo)
            run = _run_untrusted(
                [maven, "-q", "-Dsurefire.runOrder=random", "test"],
                cwd=repo, env=env, timeout_seconds=timeout_seconds,
            )
            yield run.returncode, _surefire_evidence(repo)

    return _determinism_verdict(outcomes(), jdk, timeout_seconds)
