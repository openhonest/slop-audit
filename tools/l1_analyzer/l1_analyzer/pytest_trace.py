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
untrusted code. Execution happens in a new process group with a hard timeout so
a hung or runaway suite is killed. Pass exec_tests=False to skip it entirely.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

L1Result = dict[str, Any]

DEFAULT_TIMEOUT_SECONDS = 300.0


def _timeout_seconds() -> float:
    raw = os.environ.get("L1_TEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        parsed = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_TIMEOUT_SECONDS


def _run_untrusted(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run untrusted test code in a new process group; kill the whole group on
    timeout. Mirrors umbra.process.run_untrusted. Returncode 124 signals timeout.
    """
    full_env = {**os.environ, **(env or {})}
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
        stdout, stderr = process.communicate(timeout=_timeout_seconds())
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(command, 124, stdout or "", (stderr or "") + "\ntimed out")


def _module_available(module: str) -> bool:
    """True if `python -m module` (or an importable module) is present in this
    interpreter. The suite runs under sys.executable, so this reflects the
    environment the analyzer was launched in (e.g. the target repo's venv)."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True, text=True, timeout=30,
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

def decision_space_coverage(repo: Path, lang: str) -> L1Result:
    """L1.19: branch-level decision coverage from coverage.py.

    Bands (spec 03-layer1-indicators.md): >90% Healthy, 60-90% Not Healthy,
    <60% Slop.
    """
    if lang != "python":
        return _na(f"runtime decision-coverage harness is Python-only; {lang} not supported yet")
    if not _module_available("pytest") or not _module_available("coverage"):
        return _na("needs pytest and coverage.py in the target environment (e.g. run inside the repo's venv)")

    with tempfile.TemporaryDirectory(prefix="l1-cov-") as directory:
        data_file = Path(directory) / ".coverage"
        report_file = Path(directory) / "coverage.json"
        env = {"COVERAGE_FILE": str(data_file)}
        run = _run_untrusted(
            [sys.executable, "-m", "coverage", "run", "--branch", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=repo, env=env,
        )
        if run.returncode == 5:
            return _na("pytest collected no tests")
        if run.returncode == 124:
            return _na("test suite timed out before coverage could be measured")
        # `coverage json` is our own trusted, fast step.
        subprocess.run(
            [sys.executable, "-m", "coverage", "json", "-o", str(report_file)],
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
    band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": band,
        "details": f"{covered_branches}/{num_branches} decision branches exercised by tests ({suite})",
    }


# ---------------------------------------------------------------------------
# L1.20 test determinism
# ---------------------------------------------------------------------------

def test_determinism(repo: Path, lang: str, runs: int = 5) -> L1Result:
    """L1.20: run the suite `runs` times in randomized order and count the runs
    where every test passes. Value is "passing/runs".

    Bands (spec): 5/5 Healthy, 4/5 Not Healthy, <4/5 Slop.
    """
    if lang != "python":
        return _na(f"runtime determinism harness is Python-only; {lang} not supported yet")
    if not _module_available("pytest"):
        return _na("needs pytest in the target environment")
    if not _module_available("pytest_randomly"):
        return _na("needs pytest-randomly to randomize execution order (install it in the target environment)")

    passing = 0
    # Fixed seeds make the audit itself reproducible; each seed is a different order.
    for seed in range(1, runs + 1):
        run = _run_untrusted(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--randomly-seed={seed}"],
            cwd=repo,
        )
        if run.returncode == 5:
            return _na("pytest collected no tests")
        if run.returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if run.returncode == 0:
            passing += 1

    band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    return {
        "value": f"{passing}/{runs}",
        "band": band,
        "details": f"{passing} of {runs} randomized-order runs passed cleanly",
    }
