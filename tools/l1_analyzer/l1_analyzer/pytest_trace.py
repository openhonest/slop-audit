"""Runtime harness for the two L1 indicators that require executing the test
suite rather than reading it statically:

- **L1.19 decision-space coverage** - the fraction of enumerable decision
  branches exercised by at least one test, obtained by running the suite under
  coverage.py branch tracing (`coverage run --branch`). coverage.py's branch
  totals (`covered_branches` / `num_branches`) are the enumeration and the
  execution trace in one pass.
- **L1.20 test determinism** - the number of randomized-order suite runs (out of
  five) in which every test passes, per pytest-randomly seeds.

The pytest-under-coverage recipe and the process-group timeout kill mirror the
sibling Slop Audit instrument Umbra (`umbra/src/umbra/structural.py::run_coverage`
and `umbra/src/umbra/process.py::run_untrusted`). Umbra applies the recipe per
(module, test file); here the same recipe runs against a whole repository.

Following the same discipline, every path returns an explicit *not measured*
reason rather than a guessed number. Python-only for now (pytest + coverage.py);
other languages report n/a.

Note: L1.19 and L1.20 execute the target repository's test suite, i.e. they run
untrusted code. Execution happens in a new process group with a hard timeout
(passed in explicitly by the caller) so a hung or runaway suite is killed.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict


class L1Result(TypedDict, total=False):
    value: float | int | str
    band: str
    details: str


def _run_untrusted(command: list[str], cwd: Path, env: dict[str, str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    """Run untrusted test code in a new process group; kill the whole group on
    timeout. Mirrors umbra.process.run_untrusted. Returncode 124 signals timeout.
    """
    full_env = {**os.environ, **env}
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=full_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(command, 124, stdout or "", (stderr or "") + "\ntimed out")


def _interpreter(python_executable: str | None) -> str:
    """Resolve the interpreter that runs the target suite. `None` (the named Nothing) means
    the analyzer's own interpreter; a path selects a different one, e.g. the target repo's
    venv python when it needs a Python the analyzer itself cannot run under."""
    return python_executable or sys.executable


def _module_available(module: str, python_executable: str | None = None) -> bool:
    """True if `import module` succeeds in the interpreter that will run the suite. That is
    the analyzer's own interpreter by default, or the one `python_executable` names."""
    try:
        result = subprocess.run(
            [_interpreter(python_executable), "-c", f"import {module}"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _na(reason: str) -> L1Result:
    return {"value": "n/a", "band": "n/a", "details": reason}


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:200]
    return "no output"


# ---------------------------------------------------------------------------
# L1.19 decision-space coverage
# ---------------------------------------------------------------------------

def decision_space_coverage(repo: Path, lang: str, timeout_seconds: float,
                            python_executable: str | None = None) -> L1Result:
    """L1.19: branch-level decision coverage from coverage.py.

    Bands (spec 03-layer1-indicators.md): >90% Healthy, 60-90% Not Healthy,
    <60% Slop. `python_executable` selects the interpreter that runs the suite; the target
    package must be importable there, or coverage records nothing.
    """
    if lang != "python":
        return _na(f"runtime decision-coverage harness is Python-only; {lang} not supported yet")
    exe = _interpreter(python_executable)
    if not _module_available("pytest", exe) or not _module_available("coverage", exe):
        return _na("needs pytest and coverage.py in the target environment (e.g. run inside the repo's venv)")

    with tempfile.TemporaryDirectory(prefix="l1-cov-") as directory:
        data_file = Path(directory) / ".coverage"
        report_file = Path(directory) / "coverage.json"
        env = {"COVERAGE_FILE": str(data_file)}
        run = _run_untrusted(
            [exe, "-m", "coverage", "run", "--branch", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=repo, env=env, timeout_seconds=timeout_seconds,
        )
        if run.returncode == 124:
            return _na("test suite timed out before coverage could be measured")
        # Coverage is a valid number only when the suite actually ran tests: pytest exit 0
        # (all passed) or 1 (some failed). Exit 2/3/4/5 mean the suite did not complete a
        # valid run, so a coverage figure for it is meaningless. Report n/a with the reason,
        # never a 0.0 that reads as real-but-terrible coverage (a silent failure is a lie).
        if run.returncode not in (0, 1):
            reasons = {2: "the run was interrupted", 3: "pytest hit an internal error",
                       4: "pytest usage or collection error", 5: "pytest collected no tests"}
            why = reasons.get(run.returncode, f"pytest exit {run.returncode}")
            return _na(f"the test suite did not complete a valid run ({why}); coverage not measured")
        # `coverage json` is our own trusted, fast step.
        subprocess.run(
            [exe, "-m", "coverage", "json", "-o", str(report_file)],
            cwd=str(repo), env={**os.environ, **env}, capture_output=True, text=True, check=False,
        )
        if not report_file.exists():
            return _na(f"coverage produced no data (suite exit {run.returncode}): {_first_line(run.stderr or run.stdout)}")
        try:
            report = json.loads(report_file.read_text())
        except (OSError, json.JSONDecodeError):
            return _na("coverage report was unreadable")

    totals = report.get("totals", {})
    num_branches = int(totals.get("num_branches", 0))
    covered_branches = int(totals.get("covered_branches", 0))
    if num_branches == 0:
        return _na("no enumerable decision branches found in the measured tree")

    pct = covered_branches / num_branches * 100
    result_band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{covered_branches}/{num_branches} decision branches exercised by tests ({suite})",
    }


# ---------------------------------------------------------------------------
# L1.20 test determinism
# ---------------------------------------------------------------------------

_SUMMARY_LINE = re.compile(r"(\d+ (?:failed|passed|error)[^\n]*)")


def _pytest_summary(output: str) -> str:
    """The last pytest summary counts line (e.g. `3 failed, 1219 passed in 10.0s`), or a
    generic note. This is what turns a bare 0/5 into a reason a reader can act on."""
    matches = _SUMMARY_LINE.findall(output)
    return matches[-1].strip() if matches else "no summary line"


def test_determinism(repo: Path, lang: str, runs: int, timeout_seconds: float,
                     python_executable: str | None = None) -> L1Result:
    """L1.20: run the suite `runs` times in randomized order and count the runs
    where every test passes. Value is "passing/runs".

    Bands (spec): 5/5 Healthy, 4/5 Not Healthy, <4/5 Slop.

    A run that does not complete (collection or usage error, exit 2/3/4) means the suite did
    not execute, not that it is non-deterministic, so return n/a with the reason rather than a
    misleading 0/5. When the suite runs but some tests fail (exit 1), the failing seeds' counts
    are surfaced in `details`, because a silent 0/5 reads as flakiness when it is a broken run.
    `python_executable` selects the interpreter; the target package must import there.
    """
    if lang != "python":
        return _na(f"runtime determinism harness is Python-only; {lang} not supported yet")
    exe = _interpreter(python_executable)
    if not _module_available("pytest", exe):
        return _na("needs pytest in the target environment")
    if not _module_available("pytest_randomly", exe):
        return _na("needs pytest-randomly to randomize execution order (install it in the target environment)")

    _INCOMPLETE = {2: "the run was interrupted", 3: "pytest hit an internal error",
                   4: "pytest usage or collection error (the suite did not run)"}
    passing = 0
    failing: list[str] = []
    # Fixed seeds make the audit itself reproducible; each seed is a different order.
    for seed in range(1, runs + 1):
        run = _run_untrusted(
            [exe, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--randomly-seed={seed}"],
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        if run.returncode == 5:
            return _na("pytest collected no tests")
        if run.returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if run.returncode in _INCOMPLETE:
            return _na(f"the suite did not complete a valid run (seed {seed}: {_INCOMPLETE[run.returncode]}); "
                       "determinism not measured")
        if run.returncode == 0:
            passing += 1
        else:  # exit 1: the suite ran, but not every test passed
            failing.append(f"seed {seed}: {_pytest_summary((run.stdout or '') + (run.stderr or ''))}")

    result_band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    details = f"{passing} of {runs} randomized-order runs passed cleanly"
    if failing:
        details += f" (runs with failures: {'; '.join(failing[:3])})"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}
