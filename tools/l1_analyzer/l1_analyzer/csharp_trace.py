"""Runtime harness for L1.19 / L1.20 on C# repositories - the `dotnet test` counterpart to
pytest_trace, go_trace, and rust_trace.

- **L1.19 decision-space coverage**: branch coverage from `dotnet test --collect:"XPlat Code
  Coverage"`, which drives the coverlet.collector data collector to emit a Cobertura report
  (`coverage.cobertura.xml`). The report's root `<coverage ... branch-rate="0.xx">` attribute
  is branch coverage directly, so `pct = branch-rate * 100` is the honest decision-space
  figure on the standard toolchain, and the details string says so.
- **L1.20 test determinism**: `dotnet test` run five times, counting the runs where the whole
  suite passes. `dotnet test` has no seed CLI and does not force order randomization, so this
  detects flakiness under scheduler-varied order rather than a seed-controlled shuffle; the
  details string says the order is scheduler-varied, not seed-controlled.

Directory-insensitive by construction: `dotnet` is invoked with `cwd=repo`, so the repo's own
`global.json` selects the SDK, whatever launched the analyzer. The resolved `dotnet --version`
is named in every measured result. Following the shared discipline, each path returns an
explicit *not measured* reason rather than a guessed number, and runs the repo's (untrusted)
tests in a new process group with a hard timeout.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from l1_analyzer.pytest_trace import L1Result, _first_line, _na, _run_untrusted

_BRANCH_RATE = re.compile(r"<coverage[^>]*\bbranch-rate=\"([\d.]+)\"")
# `dotnet test` prints one of these banners only when the test runner actually executed a
# suite. Their absence means the build failed or no tests were discovered, not 0/5.
_RAN = ("Passed!", "Failed!", "Passed: ", "Failed: ", "Total tests:", "Passed :", "Failed :")


def _dotnet() -> str | None:
    return shutil.which("dotnet")


def _sdk(dotnet: str, repo: Path, timeout_seconds: float) -> str:
    """The SDK `dotnet` resolves for this repo (global.json wins), named so the result says
    which environment measured it."""
    probe = _run_untrusted([dotnet, "--version"], cwd=repo, env={}, timeout_seconds=min(timeout_seconds, 30))
    return f"dotnet {_first_line(probe.stdout)}" if probe.returncode == 0 else "an unknown dotnet SDK"


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.19 for C#: branch coverage from `dotnet test --collect:"XPlat Code Coverage"`. Bands
    match the spec: >90% Healthy, 60-90% Not Healthy, <60% Slop. `runtime_override` is accepted
    for a uniform harness signature and ignored: `dotnet` selects the SDK from the repo itself."""
    dotnet = _dotnet()
    if dotnet is None:
        return _na("needs the dotnet SDK in PATH")
    sdk = _sdk(dotnet, repo, timeout_seconds)
    with tempfile.TemporaryDirectory(prefix="l1-cscov-") as directory:
        run = _run_untrusted(
            [dotnet, "test", "--collect:XPlat Code Coverage", "--results-directory", directory],
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        if run.returncode == 124:
            return _na("test suite timed out before coverage could be measured")
        # coverlet.collector writes a Cobertura file for every project that built and ran, even
        # when some tests failed. No file means the collector was not wired in (or nothing ran):
        # n/a with the reason, never a 0.0 that reads as real-but-terrible coverage.
        reports = sorted(Path(directory).rglob("coverage.cobertura.xml"))
        if not reports:
            return _na("C# branch coverage needs coverlet.collector in the test project "
                       "(coverage.cobertura.xml not produced)")
        match = _BRANCH_RATE.search(reports[0].read_text(errors="ignore"))
        if match is None:
            return _na("cobertura report had no branch-rate")

    pct = float(match.group(1)) * 100
    result_band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{round(pct, 1)}% branch coverage from `dotnet test --collect \"XPlat Code Coverage\"` "
                   f"({suite}; ran under {sdk})",
    }


def _ran_tests(output: str) -> bool:
    """True when `dotnet test` actually built and ran a suite, false when nothing ran (a build
    error, or a project with no discovered tests) - the difference between a real determinism
    data point and the suite never executing."""
    return any(marker in output for marker in _RAN)


def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.20 for C#: `dotnet test` `runs` times, counting the runs where the whole suite passes.
    `dotnet test` has no seed CLI, so the order is scheduler-varied, not seed-controlled. A run
    that does not build or runs no tests is not a determinism result, so return n/a with the
    reason rather than a misleading 0/5."""
    dotnet = _dotnet()
    if dotnet is None:
        return _na("needs the dotnet SDK in PATH")
    sdk = _sdk(dotnet, repo, timeout_seconds)

    passing = 0
    failing: list[str] = []
    for attempt in range(1, runs + 1):
        run = _run_untrusted([dotnet, "test"], cwd=repo, env={}, timeout_seconds=timeout_seconds)
        output = (run.stdout or "") + (run.stderr or "")
        if run.returncode == 124:
            return _na(f"a run timed out (run {attempt}); determinism not measured")
        if not _ran_tests(output):
            return _na(f"the suite did not run (run {attempt}: no test project built or executed under "
                       f"{sdk}); determinism not measured")
        if run.returncode == 0:
            passing += 1
        else:
            failing.append(f"run {attempt}: {_first_line(output)}")

    result_band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    details = (f"{passing} of {runs} `dotnet test` runs passed cleanly (order is scheduler-varied, "
               f"not seed-controlled; under {sdk})")
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}
