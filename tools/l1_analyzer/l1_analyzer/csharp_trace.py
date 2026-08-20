"""Runtime harness for L1.19 / L1.20 on C# repositories - the `dotnet test` counterpart to
pytest_trace, go_trace, and rust_trace.

- **L1.19 decision-space coverage**: branch coverage from `dotnet test --collect:"XPlat Code
  Coverage"`, which drives the coverlet.collector data collector to emit a Cobertura report
  (`coverage.cobertura.xml`). The report's root `branches-covered` / `branches-valid` counts
  give branch coverage as `covered / valid * 100`; `branches-valid == 0` means nothing had a
  branch to cover (usually the code under test sits in the test assembly, which coverlet
  excludes) and is reported n/a with the remedy, never a misleading 0.0.
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
from collections.abc import Iterable
from pathlib import Path

from l1_analyzer.pytest_trace import (
    L1Result,
    _first_line,
    _na,
    _run_untrusted,
    coverage_band,
    determinism_tally,
)

_BRANCHES_VALID = re.compile(r"<coverage[^>]*\bbranches-valid=\"(\d+)\"")
_BRANCHES_COVERED = re.compile(r"<coverage[^>]*\bbranches-covered=\"(\d+)\"")
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


def _coverage_verdict(branches: tuple[int, int] | None, returncode: int, sdk: str) -> L1Result:
    """L1.19 from a finished run and what the Cobertura report carried. No I/O, so it can be
    asserted as a value.

    `branches` is the report's (covered, valid) pair, or None when the run wrote no
    coverage.cobertura.xml at all. Absence is a case here rather than a pair of zeroes because
    the two say different things: no report means the collector is not referenced by the test
    project, while a report with `branches-valid="0"` means the collector ran and found nothing
    with a branch in it. Both are n/a, and each names its own remedy.

    Extracted because it could not be reached otherwise. The old tests replaced `_dotnet` and
    `_run_untrusted` with a fake that both answered `dotnet --version` and wrote the report the
    module read back, so this table was proved against the test's own XML and `dotnet test`
    could have been invoked with any flags at all.
    """
    if returncode == 124:
        return _na("test suite timed out before coverage could be measured")
    # coverlet.collector writes a Cobertura file for every project that built and ran, even
    # when some tests failed. No file means the collector was not wired in (or nothing ran):
    # n/a with the reason, never a 0.0 that reads as real-but-terrible coverage.
    if branches is None:
        return _na("C# branch coverage needs coverlet.collector in the test project "
                   "(coverage.cobertura.xml not produced)")
    covered, valid = branches
    # branches-valid == 0 means nothing had a branch to cover, NOT that coverage is 0. It
    # usually means the code under test sits in the test assembly, which coverlet excludes by
    # default. n/a with the remedy, never a 0.0 that reads as real-but-terrible coverage.
    if valid == 0:
        return _na("no branches instrumented; the code under test may be in the test assembly "
                   "(coverlet excludes it) - put it in a separate project the tests reference")
    pct = covered / valid * 100
    suite = "suite passed" if returncode == 0 else f"suite exit {returncode}"
    return {
        "value": round(pct, 1),
        "band": coverage_band(pct),
        "details": f"{covered}/{valid} branches exercised by tests from `dotnet test --collect "
                   f"\"XPlat Code Coverage\"` ({suite}; ran under {sdk})",
    }


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
        reports = sorted(Path(directory).rglob("coverage.cobertura.xml"))
        if run.returncode == 124 or not reports:
            return _coverage_verdict(None, run.returncode, sdk)
        text = reports[0].read_text(errors="ignore")
        valid_match = _BRANCHES_VALID.search(text)
        covered_match = _BRANCHES_COVERED.search(text)
        if valid_match is None or covered_match is None:
            return _na("cobertura report had no branch counts")
        branches = (int(covered_match.group(1)), int(valid_match.group(1)))

    return _coverage_verdict(branches, run.returncode, sdk)


def _ran_tests(output: str) -> bool:
    """True when `dotnet test` actually built and ran a suite, false when nothing ran (a build
    error, or a project with no discovered tests) - the difference between a real determinism
    data point and the suite never executing."""
    return any(marker in output for marker in _RAN)


def _determinism_verdict(outcomes: Iterable[tuple[int, str]], sdk: str) -> L1Result:
    """L1.20 for C# from finished `dotnet test` runs. See pytest_trace.determinism_tally for
    the rules; only the words are here, and they are C#'s own. `dotnet test` has no seed CLI,
    so an attempt is a run whose order the scheduler varied, never a seed."""
    return determinism_tally(
        outcomes,
        {"unit": "run",
         "never_ran": f"no test project built or executed under {sdk}",
         "no_runs": "no `dotnet test` runs were made; determinism not measured",
         "describe": f"`dotnet test` runs passed cleanly (order is scheduler-varied, "
                     f"not seed-controlled; under {sdk})"},
        _ran_tests,
        _first_line,
    )

def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.20 for C#: `dotnet test` `runs` times, counting the runs where the whole suite passes.
    `dotnet test` has no seed CLI, so the order is scheduler-varied, not seed-controlled. A run
    that does not build or runs no tests is not a determinism result, so return n/a with the
    reason rather than a misleading 0/5."""
    dotnet = _dotnet()
    if dotnet is None:
        return _na("needs the dotnet SDK in PATH")
    sdk = _sdk(dotnet, repo, timeout_seconds)

    def outcomes() -> Iterable[tuple[int, str]]:
        # Lazy, so the verdict's return on a timed-out or never-run attempt stops the rest.
        for _ in range(runs):
            run = _run_untrusted([dotnet, "test"], cwd=repo, env={}, timeout_seconds=timeout_seconds)
            yield run.returncode, (run.stdout or "") + (run.stderr or "")

    return _determinism_verdict(outcomes(), sdk)
