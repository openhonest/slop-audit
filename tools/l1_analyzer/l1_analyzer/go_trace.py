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

from l1_analyzer.pytest_trace import L1Result, _first_line, _na, _run_untrusted

_TOTAL = re.compile(r"total:\s+\(statements\)\s+([\d.]+)%")
_RAN = ("ok  ", "--- FAIL", "FAIL", "PASS")


def _go() -> str | None:
    return shutil.which("go")


def _toolchain(go: str, repo: Path, timeout_seconds: float) -> str:
    """The toolchain `go` resolves for this module (go.mod's `toolchain` directive wins),
    named so the result says which environment measured it."""
    probe = _run_untrusted([go, "version"], cwd=repo, env={}, timeout_seconds=min(timeout_seconds, 30))
    return _first_line(probe.stdout) if probe.returncode == 0 else "an unknown go toolchain"


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
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
        if run.returncode == 124:
            return _na("test suite timed out before coverage could be measured")
        # The profile is written for every package that built and ran, even if some tests
        # failed. No profile means the module did not build or ran no tests: n/a with the
        # reason, never a 0.0 that reads as real-but-terrible coverage (a silent failure is a lie).
        if not profile.exists() or profile.stat().st_size == 0:
            return _na(f"coverage produced no data (go test exit {run.returncode}): "
                       f"{_first_line(run.stderr or run.stdout)}")
        func = _run_untrusted([go, "tool", "cover", f"-func={profile}"], cwd=repo, env={},
                              timeout_seconds=min(timeout_seconds, 60))
        match = _TOTAL.search(func.stdout or "")
        if match is None:
            return _na("coverage profile had no statement total")

    pct = float(match.group(1))
    result_band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{pct}% statement coverage from `go test -coverprofile` ({suite}; ran under {toolchain})",
    }


def _ran_tests(output: str) -> bool:
    """True when `go test` actually built and ran a package, false when nothing ran (a build
    error, or a module with no test files) - the difference between a real determinism data
    point and the suite never executing."""
    return any(marker in output for marker in _RAN)


def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.20 for Go: `go test -shuffle=<seed> -count=1` `runs` times, counting the runs where
    every package passes. A run that does not build or runs no tests is not a determinism
    result, so return n/a with the reason rather than a misleading 0/5."""
    go = _go()
    if go is None:
        return _na("needs the Go toolchain (go) in PATH")
    toolchain = _toolchain(go, repo, timeout_seconds)

    passing = 0
    failing: list[str] = []
    for seed in range(1, runs + 1):
        run = _run_untrusted(
            [go, "test", "./...", f"-shuffle={seed}", "-count=1"],
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        output = (run.stdout or "") + (run.stderr or "")
        if run.returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if not _ran_tests(output):
            return _na(f"the suite did not run (seed {seed}: no test packages built or executed under "
                       f"{toolchain}); determinism not measured")
        if run.returncode == 0:
            passing += 1
        else:
            failing.append(f"seed {seed}: {_first_line(output)}")

    result_band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    details = f"{passing} of {runs} shuffled-order runs passed cleanly (under {toolchain})"
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}
