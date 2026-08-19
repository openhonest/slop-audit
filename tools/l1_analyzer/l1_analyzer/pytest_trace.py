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
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from l1_analyzer import incomplete


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
    """Resolve a bare interpreter override: the named path, or the analyzer's own. Used by
    the module-availability probe, which has no repo to auto-detect a venv from."""
    return python_executable or sys.executable


# venv layouts, in the order a target repo is most likely to use. The suite must run under
# the interpreter where the target package and its test deps are installed, not the one that
# happened to launch the analyzer, or coverage records nothing and every run fails.
_VENV_PYTHONS = (
    ".venv/bin/python", ".venv/bin/python3", "venv/bin/python", "venv/bin/python3",
    ".venv/Scripts/python.exe", "venv/Scripts/python.exe",
)


def detect_target_interpreter(repo: Path) -> str | None:
    """The target repo's own venv interpreter, or None when it has none. This is what makes
    the audit directory-insensitive: the runtime result depends on the target's environment,
    not on where or how the analyzer was launched."""
    for rel in _VENV_PYTHONS:
        candidate = repo / rel
        if candidate.exists():
            return str(candidate)
    return None


def resolve_interpreter(repo: Path, python_executable: str | None) -> tuple[str, str]:
    """(interpreter, provenance) for running the target suite. Precedence: an explicit
    override, then the target repo's own venv, then the analyzer's interpreter. The
    provenance string is surfaced in the result so which interpreter ran is never hidden."""
    if python_executable:
        return python_executable, f"--python {python_executable}"
    detected = detect_target_interpreter(repo)
    if detected:
        return detected, f"target venv {detected}"
    return sys.executable, f"the analyzer's own interpreter {sys.executable}"


# Version managers that expose a per-directory `<manager> which <tool>`, honoring the repo's
# version file (.ruby-version / .tool-versions / .java-version). Unlike nvm (shell-resident),
# these are real binaries, so we ask them directly instead of trusting PATH order - which a
# homebrew ruby/java ahead of the shim would otherwise silently win.
_SHIM_MANAGERS = ("mise", "rbenv", "asdf", "jenv")


def resolve_via_shim(repo: Path, tool: str, timeout_seconds: float) -> tuple[str | None, str]:
    """(resolved path, provenance) for `tool` as a version manager pins it for this repo dir,
    or (None, "") when no manager resolves it (caller falls back to the ambient runtime). This
    defeats PATH-shadowing: it uses the manager's own resolution, not whatever is first on PATH.
    A manager that does not manage `tool` (jenv for ruby, rbenv for java) simply fails and is
    skipped."""
    for manager in _SHIM_MANAGERS:
        if shutil.which(manager) is None:
            continue
        probe = _run_untrusted([manager, "which", tool], cwd=repo, env={},
                               timeout_seconds=min(timeout_seconds, 30))
        path = _first_line(probe.stdout).strip()
        if probe.returncode == 0 and path.startswith("/") and Path(path).exists():
            return path, f"{manager} which {tool}"
    return None, ""


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


def coverage_band(pct: float) -> str:
    """The published L1.19 band: strictly above 90 is Healthy, at or above 60 is Not
    Healthy, below that is Slop. One rule for every language, because comparing languages
    is what the meter claims to do, and eight copies of a threshold is eight places for
    one language to start grading the same evidence differently from the rest."""
    return "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")


def determinism_band(passing: int, runs: int) -> str:
    """The published L1.20 band: every run clean is Healthy, exactly one short is Not
    Healthy, worse is Slop. The caller refuses a zero denominator before it reaches here,
    since zero clean out of zero satisfies "every run passed" and would band Healthy."""
    return "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")


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

# Why a pytest exit code is not a coverage figure. 0 and 1 mean the suite ran; everything
# else means it did not, and a percentage computed over a run that never happened reads as
# real-but-terrible coverage, which is the silent failure this package exists to name.
_INVALID_RUN = {
    2: "the run was interrupted",
    3: "pytest hit an internal error",
    4: "pytest usage or collection error",
    5: "pytest collected no tests",
    124: "the test suite timed out before coverage could be measured",
}


def _coverage_verdict(returncode: int, totals: dict, provenance: str) -> L1Result:
    """L1.19 from a finished run and coverage.py's totals. No I/O, so it can be asserted.

    Extracted because it could not be reached otherwise. `decision_space_coverage` runs the
    suite, opens a temp directory, shells out again for `coverage json`, reads the report and
    decides the band inside one function, so the exit-code table below was only ever provable
    through a replaced `_run_untrusted` - a fake that ignored its arguments, and so would have
    passed had the harness invoked pytest with the wrong flags against the wrong interpreter.

    An exit code no row names reports the code itself. That is a named miss and not a default:
    it cannot be mistaken for a row somebody wrote, which is the thing a default does wrong.
    """
    if returncode not in (0, 1):
        why = _INVALID_RUN.get(returncode, f"pytest exit {returncode}")
        if returncode == 124:
            return _na(why)
        return _na(f"the test suite did not complete a valid run ({why}); coverage not measured")
    num_branches = int(totals.get("num_branches", 0))
    covered = int(totals.get("covered_branches", 0))
    if num_branches == 0:
        # Raised rather than returned, now that the boundary covers this measure. A share of
        # no branches is absent and not zero, and `incomplete` exists so that the absence
        # cannot be spelled as a value by a caller who forgets to check one.
        raise incomplete.refuse(
            "L1.19 decision-space coverage",
            "no enumerable decision branches found in the measured tree")
    pct = covered / num_branches * 100
    suite = "suite passed" if returncode == 0 else f"suite exit {returncode}"
    return {
        "value": round(pct, 1),
        "band": coverage_band(pct),
        "details": f"{covered}/{num_branches} decision branches exercised by tests "
                   f"({suite}; ran under {provenance})",
    }


def decision_space_coverage(repo: Path, lang: str, timeout_seconds: float,
                            python_executable: str | None = None) -> L1Result:
    """L1.19: branch-level decision coverage from coverage.py.

    Bands (spec 03-layer1-indicators.md): >90% Healthy, 60-90% Not Healthy,
    <60% Slop. `python_executable` selects the interpreter that runs the suite; the target
    package must be importable there, or coverage records nothing.
    """
    if lang != "python":
        return _na(f"runtime decision-coverage harness is Python-only; {lang} not supported yet")
    exe, provenance = resolve_interpreter(repo, python_executable)
    if not _module_available("pytest", exe) or not _module_available("coverage", exe):
        return _na(f"needs pytest and coverage.py in the target environment ({provenance})")

    with tempfile.TemporaryDirectory(prefix="l1-cov-") as directory:
        data_file = Path(directory) / ".coverage"
        report_file = Path(directory) / "coverage.json"
        env = {"COVERAGE_FILE": str(data_file)}
        run = _run_untrusted(
            [exe, "-m", "coverage", "run", "--branch", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=repo, env=env, timeout_seconds=timeout_seconds,
        )
        if run.returncode not in (0, 1):
            return _coverage_verdict(run.returncode, {}, provenance)
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

    return _coverage_verdict(run.returncode, report.get("totals", {}), provenance)


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
    exe, provenance = resolve_interpreter(repo, python_executable)
    if not _module_available("pytest", exe):
        return _na(f"needs pytest in the target environment ({provenance})")
    if not _module_available("pytest_randomly", exe):
        return _na(f"needs pytest-randomly to randomize execution order (install it in {provenance})")

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

    result_band = determinism_band(passing, runs)
    details = f"{passing} of {runs} randomized-order runs passed cleanly (under {provenance})"
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}
