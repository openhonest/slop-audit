"""Runtime harness for L1.19 / L1.20 on Go modules - the `go test` counterpart to
pytest_trace and rust_trace.

- **L1.19 decision-space coverage**: statement coverage from `go test -coverprofile`,
  totalled by `go tool cover -func`. Go instruments statements, not branches, so this is
  the honest decision-space proxy on the standard toolchain (as region coverage is for
  Rust), and the details string says so.
- **L1.20 test determinism**: `go test -shuffle` run five times with distinct seeds,
  counting the runs where every package passes. `-shuffle` (Go 1.17+) is the native
  order randomiser, so no external plugin is needed.

Directory-insensitive by construction: `go` is invoked with `cwd=repo`, so the module's
own `go.mod` and its `toolchain` directive select the toolchain, whatever launched the
analyzer. The resolved `go version` is named in every result. Following the shared
discipline, each path returns an explicit *not measured* reason rather than a guessed
number, and runs the module's (untrusted) tests in a new process group with a hard timeout.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from l1_analyzer.pytest_trace import (
    L1Result,
    _first_line,
    _na,
    _run_untrusted,
    coverage_band,
    determinism_band,
)

_TOTAL = re.compile(r"total:\s+\(statements\)\s+([\d.]+)%")
_RAN = ("ok  ", "--- FAIL", "FAIL", "PASS")


def _go() -> str | None:
    return shutil.which("go")


def _toolchain(go: str, repo: Path, timeout_seconds: float) -> str:
    """The toolchain `go` resolves for this module (go.mod's `toolchain` directive wins),
    named so the result says which environment measured it."""
    probe = _run_untrusted([go, "version"], cwd=repo, env={}, timeout_seconds=min(timeout_seconds, 30))
    return _first_line(probe.stdout) if probe.returncode == 0 else "an unknown go toolchain"


def _coverage_verdict(func_output: str, profile_written: bool, run_returncode: int,
                      run_output: str, toolchain: str) -> L1Result:
    """L1.19 for Go from `go tool cover -func`'s stdout and the run that produced the profile.
    No I/O, so it can be asserted as a value.

    Extracted because it could not be reached otherwise. `decision_space_coverage` probes the
    toolchain, runs the whole suite into a temp-directory profile, shells out again to total it
    and decides the band inside one function, so this band table and these three refusals were
    only ever provable through a replaced `_run_untrusted` - a fake that both answered `go
    version` and wrote the profile the module then read back, so the total parser was proved
    against the test's own string.

    The substitution this function performs and cannot show in its own value: L1.19 carries
    branch coverage for Python, and the Go toolchain instruments statements, so statement
    coverage goes into the same field. The `details` line discloses it. The value and the band
    cannot.

    `profile_written` is the caller's reading of the file, passed as a plain fact so the
    decision that depends on it needs no filesystem. No profile at all is n/a with the run's
    own first line, never a 0.0 that reads as real-but-terrible coverage.
    """
    if run_returncode == 124:
        return _na("test suite timed out before coverage could be measured")
    # The profile is written for every package that built and ran, even if some tests failed.
    # No profile means the module did not build or ran no tests.
    if not profile_written:
        return _na(f"coverage produced no data (go test exit {run_returncode}): "
                   f"{_first_line(run_output)}")
    # A PROFILE IS NOT A READING. `go test ./...` over a tree with no module, or a module
    # whose packages carry no test file, exits non-zero having compiled nothing and still
    # writes a profile; `go tool cover -func` totals that empty profile at 0.0%, and 0.0 is
    # the Slop end of this scale. So a directory the toolchain never compiled scored the
    # worst possible reading.
    #
    # `_ran_tests` was written for exactly this distinction and used by the determinism arm
    # only, where its docstring calls it "the difference between a real determinism data
    # point and the suite never executing". The coverage arm needed the same question.
    if not _ran_tests(run_output):
        return _na(f"no Go test ran, so coverage was not measured (go test exit "
                   f"{run_returncode}): {_first_line(run_output)}")
    match = _TOTAL.search(func_output)
    if match is None:
        return _na("coverage profile had no statement total")

    pct = float(match.group(1))
    result_band = coverage_band(pct)
    suite = "suite passed" if run_returncode == 0 else f"suite exit {run_returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{pct}% STATEMENT coverage from `go test -coverprofile` ({suite}; ran under "
                   f"{toolchain}); Go instruments statements rather than branches, so this field "
                   f"carries statement coverage where other languages carry branch coverage",
    }


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.19 for Go: statement coverage from `go test -coverprofile`. Bands match the spec:
    >90% Healthy, 60-90% Not Healthy, <60% Slop. `runtime_override` is accepted for a uniform
    harness signature and ignored: `go` selects the toolchain from the module itself."""
    go = _go()
    if go is None:
        return _na("needs the Go toolchain (go) in PATH")
    toolchain = _toolchain(go, repo, timeout_seconds)
    with tempfile.TemporaryDirectory(prefix="l1-gocov-") as directory:
        profile = Path(directory) / "cover.out"
        run = _run_untrusted(
            [go, "test", "./...", "-covermode=set", f"-coverprofile={profile}"],
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        written = profile.exists() and profile.stat().st_size > 0
        # Totalling a profile that was never written, or one from a run that was killed, buys
        # nothing the verdict can use, so the second subprocess is skipped and the verdict is
        # left to name which of the two happened.
        func_output = ""
        if written and run.returncode != 124:
            func = _run_untrusted([go, "tool", "cover", f"-func={profile}"], cwd=repo, env={},
                                  timeout_seconds=min(timeout_seconds, 60))
            func_output = func.stdout or ""

    return _coverage_verdict(func_output, written, run.returncode,
                             run.stderr or run.stdout or "", toolchain)


def _ran_tests(output: str) -> bool:
    """True when `go test` actually built and ran a package, false when nothing ran (a build
    error, or a module with no test files) - the difference between a real determinism data
    point and the suite never executing."""
    return any(marker in output for marker in _RAN)


def _determinism_verdict(outcomes: list[tuple[int, int, str]], runs: int, toolchain: str) -> L1Result:
    """L1.20 for Go from the shuffled runs' outcomes alone: one `(seed, exit code, combined
    output)` per run, in seed order. No I/O, so it can be asserted as a value.

    Extracted for the same reason as `_coverage_verdict`: the loop that produced these outcomes
    also owned the band table and the three refusals, so a fake subprocess was the only way to
    reach them, and the fake's canned success meant an unrecognised command scored as a clean
    run.

    A failing seed is quoted with its own first line, up to three of them, because a bare 3/5
    is a score a reader cannot act on. A run that timed out and a run whose suite never
    executed are not failing runs at all: they say so and stop, rather than lowering a count
    that would read as a suite falling over when reordered.

    Fewer outcomes than `runs` with nothing among them to refuse over is the same absence one
    step out: a fraction over runs that were never made. It is named, not banded.
    """
    passing = 0
    failing: list[str] = []
    for seed, returncode, output in outcomes:
        if returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if not _ran_tests(output):
            return _na(f"the suite did not run (seed {seed}: no test packages built or executed under "
                       f"{toolchain}); determinism not measured")
        if returncode == 0:
            passing += 1
        else:
            failing.append(f"seed {seed}: {_first_line(output)}")

    if len(outcomes) != runs:
        return _na(f"only {len(outcomes)} of {runs} shuffled-order runs produced an outcome; "
                   f"determinism not measured (under {toolchain})")

    result_band = determinism_band(passing, runs)
    details = f"{passing} of {runs} shuffled-order runs passed cleanly (under {toolchain})"
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}


def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.20 for Go: `go test -shuffle=<seed> -count=1` `runs` times, counting the runs where
    every package passes. A run that does not build or runs no tests is not a determinism
    result, so return n/a with the reason rather than a misleading 0/5."""
    go = _go()
    if go is None:
        return _na("needs the Go toolchain (go) in PATH")
    toolchain = _toolchain(go, repo, timeout_seconds)

    outcomes: list[tuple[int, int, str]] = []
    for seed in range(1, runs + 1):
        run = _run_untrusted(
            [go, "test", "./...", f"-shuffle={seed}", "-count=1"],
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        output = (run.stdout or "") + (run.stderr or "")
        outcomes.append((seed, run.returncode, output))
        # Stop spending suite runs once the verdict can only be a refusal. This is the stopping
        # rule and nothing else: the reason, the band and the value stay in _determinism_verdict,
        # which reaches the same two cases from the outcome it was handed.
        if run.returncode == 124 or not _ran_tests(output):
            break

    return _determinism_verdict(outcomes, runs, toolchain)
