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

from l1_analyzer.pytest_trace import L1Result, _first_line, _na, _run_untrusted

# "test result: ok. 2 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out"
_RESULT = re.compile(r"test result:.*?(\d+) passed;\s*(\d+) failed;\s*(\d+) ignored")


def _cargo() -> str | None:
    return shutil.which("cargo")


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

def _llvm_cov_report(repo: Path, timeout_seconds: float) -> tuple[dict | None, str]:
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
        run = _run_untrusted([cargo, "llvm-cov", "--json", "--quiet", "--output-path", str(report_file)],
                             cwd=repo, env={}, timeout_seconds=timeout_seconds)
        if run.returncode == 124:
            return None, "coverage run timed out"
        if not report_file.exists():
            return None, f"coverage produced no data (cargo exit {run.returncode}): {_first_line(run.stderr or run.stdout)}"
        try:
            return json.loads(report_file.read_text()), ""
        except (OSError, json.JSONDecodeError):
            return None, "coverage report was unreadable"


def _uncovered_lines(entry: dict) -> frozenset[int]:
    """1-based lines a region entry marked never-executed. A segment is
    [line, col, count, has_count, is_region_entry]; a region entry with a real count of
    zero is a never-executed decision point on that line."""
    return frozenset(int(seg[0]) for seg in entry.get("segments", ())
                     if len(seg) >= 5 and seg[3] and seg[4] and int(seg[2]) == 0)


def module_uncovered_lines(repo: Path, module_relpath: str, timeout_seconds: float) -> dict:
    """Uncovered lines for ONE module file, measured against the module in its crate (so it
    works for a deeply-integrated module). {measured, uncovered_lines, reason}."""
    report, reason = _llvm_cov_report(repo, timeout_seconds)
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


def repo_uncovered_lines(repo: Path, timeout_seconds: float) -> dict:
    """Uncovered lines for EVERY file under the repo, from a single coverage build. Returns
    {measured, files: {relpath: frozenset(lines)}, reason}. Only files inside `repo` with at
    least one uncovered line are included, keyed by their path relative to repo."""
    report, reason = _llvm_cov_report(repo, timeout_seconds)
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


def decision_space_coverage(repo: Path, timeout_seconds: float) -> L1Result:
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
            [cargo, "llvm-cov", "--json", "--quiet", "--output-path", str(report_file)],
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        if run.returncode == 124:
            return _na("test suite timed out before coverage could be measured")
        if "llvm-tools" in (run.stderr or "") and not report_file.exists():
            return _na("cargo-llvm-cov could not find the LLVM coverage tools; install the "
                       "llvm-tools-preview rustup component, or set LLVM_COV / LLVM_PROFDATA")
        if not report_file.exists():
            return _na(f"coverage produced no data (cargo exit {run.returncode}): {_first_line(run.stderr or run.stdout)}")
        try:
            report = json.loads(report_file.read_text())
        except (OSError, json.JSONDecodeError):
            return _na("coverage report was unreadable")

    try:
        regions = report["data"][0]["totals"]["regions"]
        count, covered = int(regions["count"]), int(regions["covered"])
    except (KeyError, IndexError, TypeError, ValueError):
        return _na("coverage report had no region totals")
    if count == 0:
        return _na("no coverage regions found (did the suite run any tests?)")

    pct = covered / count * 100
    result_band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{covered}/{count} llvm-cov regions exercised by tests, region coverage ({suite})",
    }


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
            return _na(f"a test run timed out (run {i}); determinism not measured")
        total, _failed = _tests_run((run.stdout or "") + (run.stderr or ""))
        if i == 1 and total == 0:
            return _na("cargo test collected no tests")
        if run.returncode == 0 and total > 0:
            passing += 1

    result_band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    return {
        "value": f"{passing}/{runs}",
        "band": result_band,
        "details": f"{passing} of {runs} cargo-test runs passed cleanly (libtest varies order across runs)",
    }
