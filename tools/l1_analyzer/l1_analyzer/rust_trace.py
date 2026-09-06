"""Runtime harness for L1.19 / L1.20 on Rust repositories - the cargo counterpart
to pytest_trace. It actually executes the crate's test suite (untrusted code, in a
new process group with a hard timeout, exactly like the Python path) rather than
reporting n/a.

- **L1.19 decision-space coverage**: region coverage from `cargo llvm-cov --json`
  (`totals.regions.{covered,count}`). LLVM *branch* coverage would be the closer
  analogue of coverage.py's branch totals, but on stable Rust it needs nightly
  (`-Zcoverage-options=branch`); region coverage is the honest decision-space proxy
  that runs on a stable toolchain, and the details string says which was used.
- **L1.20 test determinism**: `cargo test` run five times, counting the runs where
  every test passes. Rust's libtest schedules tests across threads, so execution
  order already varies run to run - that is the randomization source, so no
  pytest-randomly analogue is needed.

Following the same discipline as pytest_trace, every path returns an explicit
*not measured* reason rather than a guessed number. Requires `cargo`; coverage
additionally requires `cargo-llvm-cov` and the LLVM coverage tools (the
`llvm-tools-preview` rustup component, or LLVM_COV / LLVM_PROFDATA pointing at a
system llvm-cov / llvm-profdata).
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import TypedDict

from l1_analyzer import disclosure, toolchain
from l1_analyzer.boundary import boundary
from l1_analyzer.pytest_trace import (
    L1Result,
    _first_line,
    _na,
    _run_untrusted,
    coverage_band,
    determinism_band,
)

# "test result: ok. 2 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out"
_RESULT = re.compile(r"test result:.*?(\d+) passed;\s*(\d+) failed;\s*(\d+) ignored")


class Entry(TypedDict, total=False):
    """One file's entry in the coverage report the toolchain writes.

    `segments` is the only field this module reads, and each segment is a list of five
    numbers: line, column, count, whether the count is real, and whether it opens a region.
    Written out because a mapping of anything to anything has no fields to be wrong about."""

    filename: str
    segments: list[list[int]]


class Uncovered(TypedDict):
    """What a coverage run found, or why it found nothing.

    Three fields and every one is read. It was declared as a mapping of names to sets of
    line numbers, which is what only ONE of the three holds: `measured` is a yes or no and
    `reason` is a sentence, so two of the three fields disagreed with the declaration above
    them at every site that built one.

    `files` is absent on the single-module reading and `uncovered_lines` on the whole-repo
    one, because each answers a different question and inventing the other would be a blank
    nobody measured."""

    measured: bool
    reason: str


class ModuleUncovered(Uncovered, total=False):
    """One module's uncovered lines."""

    uncovered_lines: frozenset[int]


class RepoUncovered(Uncovered, total=False):
    """Every file's uncovered lines, by path from the repository root."""

    files: dict[str, frozenset[int]]



def _cargo() -> str | None:
    return shutil.which("cargo")


def _toolchain(repo: Path, timeout_seconds: float) -> str:
    """The rustc toolchain rustup resolves for this repo (its rust-toolchain.toml wins),
    named so the result says which environment measured it. Directory-insensitive: the
    rustup shim run with cwd=repo selects the repo's pinned toolchain."""
    # Named once. Two reasons reach it, no cargo at all and a rustc that would not answer,
    # and the sentence is the same for both; written twice it is two owners of one fact.
    unknown = "an unknown rust toolchain"
    cargo = _cargo()
    if cargo is None:
        return unknown
    probe = _run_untrusted([str(Path(cargo).with_name("rustc")), "--version"],
                           cwd=repo, env={}, timeout_seconds=min(timeout_seconds, 30))
    return toolchain.named(probe.stdout, probe.returncode, unknown=unknown)


def _llvm_cov_available() -> bool:
    cargo = _cargo()
    if cargo is None:
        return False
    probe = _run_untrusted([cargo, "llvm-cov", "--version"], cwd=Path.cwd(), env={}, timeout_seconds=30)
    return probe.returncode == 0


def _tests_run(output: str) -> tuple[int, int]:
    """(total tests, failed tests) summed across every 'test result:' line in the
    combined cargo-test output. total == 0 means the suite collected no tests."""
    total = failed = 0
    for passed, failed_n, ignored in _RESULT.findall(output):
        total += int(passed) + int(failed_n) + int(ignored)
        failed += int(failed_n)
    return total, failed


# ---------------------------------------------------------------------------
# L1.19 decision-space coverage (region coverage via cargo-llvm-cov)
# ---------------------------------------------------------------------------

def llvm_cov_command(cargo: str, report_file: Path, cargo_args: tuple[str, ...]) -> list[str]:
    """The one command this module runs to measure Rust coverage.

    Two functions built it, character for character, and only one of them could ever have
    grown an argument. `cargo_args` is the caller's own words, handed to cargo untouched.

    It exists because a workspace can hold a target that will not build, and one that will
    not build fails the whole build. The session auditing turso met it on 2026-09-06: one
    test target links a library by a relative path that cargo-llvm-cov's redirected target
    directory breaks, and there was no way to say "sweep this workspace but not that
    package". The only scoping lever was which directory you pointed at.

    Cargo already has the vocabulary for this, `-p` and `--exclude` and `--workspace`, so
    this passes the words through rather than inventing a second one. The alternative
    considered was degrading per package, and it is worse: the tool would decide on its own
    which packages to drop and report a share of a denominator nobody named."""
    return [cargo, "llvm-cov", "--json", "--quiet", "--output-path", str(report_file),
            *cargo_args]


@boundary
def _llvm_cov_report(repo: Path, timeout_seconds: float,
                     cargo_args: tuple[str, ...]) -> tuple[dict | None, str]:
    """Run cargo-llvm-cov on the real crate once and return (parsed export JSON, reason).
    The JSON's data[0].files carries every file's coverage in one build, so a whole-repo
    sweep pays the (expensive) instrumented build a single time."""
    cargo = _cargo()
    if cargo is None:
        return None, "needs a Rust toolchain (cargo) in PATH"
    if not _llvm_cov_available():
        return None, "needs cargo-llvm-cov"
    with tempfile.TemporaryDirectory(prefix="l1-rustcov-") as directory:
        report_file = Path(directory) / "cov.json"
        run = _run_untrusted(llvm_cov_command(cargo, report_file, cargo_args),
                             cwd=repo, env={}, timeout_seconds=timeout_seconds)
        if run.returncode == 124:
            return None, "coverage run timed out"
        if not report_file.exists():
            return None, f"coverage produced no data (cargo exit {run.returncode}): {_first_line(run.stderr or run.stdout)}"
        try:
            return json.loads(report_file.read_text()), ""
        except (OSError, json.JSONDecodeError):
            return None, "coverage report was unreadable"


def _uncovered_lines(entry: Entry) -> frozenset[int]:
    """1-based lines a region entry marked never-executed. A segment is
    [line, col, count, has_count, is_region_entry]; a region entry with a real count of
    zero is a never-executed decision point on that line."""
    return frozenset(int(seg[0]) for seg in entry.get("segments", ())
                     if len(seg) >= 5 and seg[3] and seg[4] and int(seg[2]) == 0)


def module_uncovered_lines(repo: Path, module_relpath: str, timeout_seconds: float,
                           cargo_args: tuple[str, ...]) -> ModuleUncovered:
    """Uncovered lines for ONE module file, measured against the module in its crate (so it
    works for a deeply-integrated module). {measured, uncovered_lines, reason}."""
    report, reason = _llvm_cov_report(repo, timeout_seconds, cargo_args)
    if report is None:
        return {"measured": False, "uncovered_lines": frozenset(), "reason": reason}
    target = str((repo / module_relpath).resolve())
    try:
        entry = next((f for f in report["data"][0]["files"] if str(Path(f["filename"]).resolve()) == target), None)
    except (KeyError, IndexError, TypeError):
        return {"measured": False, "uncovered_lines": frozenset(), "reason": "coverage report had no file table"}
    if entry is None:
        return {"measured": False, "uncovered_lines": frozenset(), "reason": f"{module_relpath} not found in the coverage report"}
    return {"measured": True, "uncovered_lines": _uncovered_lines(entry), "reason": ""}


def repo_uncovered_lines(repo: Path, timeout_seconds: float,
                         cargo_args: tuple[str, ...]) -> RepoUncovered:
    """Uncovered lines for EVERY file under the repo, from a single coverage build. Returns
    {measured, files: {relpath: frozenset(lines)}, reason}. Only files inside `repo` with at
    least one uncovered line are included, keyed by their path relative to repo."""
    report, reason = _llvm_cov_report(repo, timeout_seconds, cargo_args)
    if report is None:
        return {"measured": False, "files": {}, "reason": reason}
    root = repo.resolve()
    files: dict[str, frozenset[int]] = {}
    try:
        for entry in report["data"][0]["files"]:
            path = Path(entry["filename"]).resolve()
            if root in path.parents:
                lines = _uncovered_lines(entry)
                if lines:
                    files[str(path.relative_to(root))] = lines
    except (KeyError, IndexError, TypeError, ValueError):
        return {"measured": False, "files": {}, "reason": "coverage report had no file table"}
    return {"measured": True, "files": files, "reason": ""}


class Regions(TypedDict):
    """The two region counts cargo-llvm-cov writes into a report's totals."""
    count: int
    covered: int


class Totals(TypedDict):
    """The grand totals of one coverage run. Only the regions are read here."""
    regions: Regions


class Run(TypedDict):
    """One measured run in a cargo-llvm-cov export."""
    totals: Totals
    files: list[Entry]


class Report(TypedDict):
    """What `cargo llvm-cov --json` writes. Declared because the four levels this reader
    walks were four unchecked subscripts on a value nothing described, and they decide the
    whole indicator for Rust."""
    data: list[Run]


def _region_totals(report: Report) -> tuple[int, int] | None:
    """(count, covered) regions from a cargo-llvm-cov export, or None when it has no totals.

    None, never (0, 0), for a report this reader cannot find totals in. That is a schema it
    does not know, which is a different fact from a tree with no regions, and reading it as
    zero would publish Slop for a repository whose coverage was never measured.

    A tree with no regions at all comes back as (0, 0) and is refused by the verdict below,
    where the reason can say which of the two happened."""
    try:
        regions = report["data"][0]["totals"]["regions"]
        return int(regions["count"]), int(regions["covered"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _coverage_verdict(totals: tuple[int, int] | None, returncode: int,
                      toolchain: str, timeout_seconds: float, output: str) -> L1Result:
    """L1.19 from a finished run and cargo-llvm-cov's region totals. No I/O, so it can be
    asserted.

    Lifted out of the function that runs cargo, which is what every other harness here did
    on 2026-08-17 and this one did not. Until now the totals, both refusals and the band all
    sat inside the subprocess path, so proving any of them needed a Rust toolchain and
    cargo-llvm-cov on the machine, and after the stand-ins were removed they were proved by
    nothing at all.

    The timeout is decided first, before any total is touched: a killed run wrote no summary,
    so the caller has nothing to hand over.

    Region coverage, and the details line says so. LLVM branch coverage is the closer
    analogue of what the other harnesses report, and on a stable toolchain it is not
    available, so a reader comparing this number against another language's has to be told
    which one they are looking at."""
    if returncode == 124:
        return _na("test suite timed out before coverage could be measured"
                   + disclosure.timeout_note(timeout_seconds))
    if totals is None:
        return _na("coverage report had no region totals")
    count, covered = totals
    if count == 0:
        return _na("no coverage regions found, so nothing this reader can measure compiled")
    # Whether a test RAN, which is a different question from whether a region exists.
    # Regions come from compiled code, so a crate that compiles and has no tests has regions
    # and no measurement: it was banded Slop at 0.0 with the details line saying "suite
    # passed", which is true, because cargo test passes when there is nothing to run.
    # Reported on 2026-09-06 by the session auditing turso.
    #
    # Cargo says how many tests ran in its own words and `_tests_run` already reads them for
    # L1.20, so this asks rather than infers. A build that failed before any test could run
    # prints no result line at all and lands here too, which is the right answer for a
    # different reason: nothing ran, so there is nothing to report.
    ran, _failed = _tests_run(output)
    if ran == 0:
        return _na("no test ran, so a share of the regions they exercised is a share of "
                   "nothing; region coverage needs a suite that executes")
    pct = covered / count * 100
    suite = "suite passed" if returncode == 0 else f"suite exit {returncode}"
    return {
        "value": round(pct, 1),
        "band": coverage_band(pct),
        "details": f"{covered}/{count} llvm-cov regions exercised by tests, region coverage "
                   f"({suite}; ran under {toolchain})",
    }


def decision_space_coverage(repo: Path, timeout_seconds: float,
                            build_args: tuple[str, ...]) -> L1Result:
    """L1.19 for Rust: region coverage from cargo-llvm-cov. Bands match the spec:
    >90% Healthy, 60-90% Not Healthy, <60% Slop."""
    cargo = _cargo()
    if cargo is None:
        return _na("needs a Rust toolchain (cargo) in PATH")
    if not _llvm_cov_available():
        return _na("needs cargo-llvm-cov to measure coverage (cargo install cargo-llvm-cov)")

    with tempfile.TemporaryDirectory(prefix="l1-rustcov-") as directory:
        report_file = Path(directory) / "cov.json"
        run = _run_untrusted(
            llvm_cov_command(cargo, report_file, build_args),
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        if run.returncode == 124:
            # The note, like every other timeout refusal. This one was missed, and it is the
            # path a Rust workspace actually takes: the instrumented build's own stopwatch,
            # not the suite's. Without the number "the test suite timed out" reads as a fact
            # about the repository when the fact is that nobody asked for long enough.
            return _na("test suite timed out before coverage could be measured"
                       + disclosure.timeout_note(timeout_seconds))
        if "llvm-tools" in (run.stderr or "") and not report_file.exists():
            return _na("cargo-llvm-cov could not find the LLVM coverage tools; install the "
                       "llvm-tools-preview rustup component, or set LLVM_COV / LLVM_PROFDATA")
        if not report_file.exists():
            return _na(f"coverage produced no data (cargo exit {run.returncode}): {_first_line(run.stderr or run.stdout)}")
        try:
            report = json.loads(report_file.read_text())
        except (OSError, json.JSONDecodeError):
            return _na("coverage report was unreadable")

    return _coverage_verdict(_region_totals(report), run.returncode,
                             _toolchain(repo, timeout_seconds), timeout_seconds,
                             (run.stdout or "") + (run.stderr or ""))


# ---------------------------------------------------------------------------
# L1.20 test determinism (repeated cargo test)
# ---------------------------------------------------------------------------

def test_determinism(repo: Path, runs: int, timeout_seconds: float) -> L1Result:
    """L1.20 for Rust: run `cargo test` `runs` times and count the runs where every
    test passes. libtest's concurrent scheduling varies order between runs. Bands:
    5/5 Healthy, 4/5 Not Healthy, <4/5 Slop."""
    cargo = _cargo()
    if cargo is None:
        return _na("needs a Rust toolchain (cargo) in PATH")

    passing = 0
    for i in range(1, runs + 1):
        run = _run_untrusted([cargo, "test", "--quiet"], cwd=repo, env={}, timeout_seconds=timeout_seconds)
        if run.returncode == 124:
            return _na(f"a test run timed out (run {i}); determinism not measured"
                       + disclosure.timeout_note(timeout_seconds))
        total, _failed = _tests_run((run.stdout or "") + (run.stderr or ""))
        if i == 1 and total == 0:
            return _na("cargo test collected no tests")
        if run.returncode == 0 and total > 0:
            passing += 1

    result_band = determinism_band(passing, runs)
    return {
        "value": f"{passing}/{runs}",
        "band": result_band,
        "details": f"{passing} of {runs} cargo-test runs passed cleanly (libtest varies order across runs; "
                   f"ran under {_toolchain(repo, timeout_seconds)})",
    }
