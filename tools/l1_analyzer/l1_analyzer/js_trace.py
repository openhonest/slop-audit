"""Runtime harness for L1.19 / L1.20 on JavaScript / TypeScript repositories - the
Node counterpart to pytest_trace, rust_trace and go_trace. One module serves both the
`javascript` and `typescript` registry keys: V8 coverage and the Node test runners are
language-level, not dialect-level.

- **L1.19 decision-space coverage**: branch coverage from c8 (V8's built-in coverage),
  read from c8's `json-summary` report (`total.branches.pct`). V8 tracks real branches,
  so this is the honest decision-space measure, and the details string names it.
- **L1.20 test determinism**: the project's own runner re-run five times with a shuffled
  order and a distinct seed, counting the runs where the whole suite passes. vitest
  (`--sequence.shuffle --sequence.seed`) and jest>=30 (`--seed`) are the runners this
  harness can drive; a project on any other runner reports n/a with the runner it detected.

Directory-insensitive by construction: `node` and `npx` are invoked with `cwd=repo`, so the
project's own `node_modules`, `package.json` test script, and `.nvmrc` select the toolchain,
whatever launched the analyzer. The resolved `node --version` is named in every measured
result. Following the shared discipline, each path returns an explicit *not measured* reason
rather than a guessed number, and runs the project's (untrusted) suite in a new process group
with a hard timeout. `runtime_override` is accepted for a uniform harness signature and
ignored: `node` on PATH is the runtime, and the project selects its own runner.
"""

from __future__ import annotations

import json
import shlex
import shutil
import tempfile
from pathlib import Path

from l1_analyzer.pytest_trace import L1Result, _first_line, _na, _run_untrusted

# The default `npm init` test script; a real command, but it runs no tests.
_NO_TEST_SCRIPT = "no test specified"


def _node() -> str | None:
    return shutil.which("node")


def _node_version(node: str, repo: Path, timeout_seconds: float) -> str:
    probe = _run_untrusted([node, "--version"], cwd=repo, env={}, timeout_seconds=min(timeout_seconds, 30))
    return _first_line(probe.stdout) if probe.returncode == 0 else "an unknown node runtime"


def _runtime_name(node: str, repo: Path, timeout_seconds: float) -> str:
    """The Node runtime that ran, named so the result says which environment measured it.
    `.nvmrc` is best-effort context: when present, its pin is appended, but the executing
    `node --version` is the authoritative runtime."""
    version = _node_version(node, repo, timeout_seconds)
    nvmrc = repo / ".nvmrc"
    try:
        pin = _first_line(nvmrc.read_text()) if nvmrc.exists() else ""
    except OSError:
        pin = ""
    return f"{version} (.nvmrc pins {pin})" if pin and pin != "no output" else version


def _node_modules_present(repo: Path) -> bool:
    return (repo / "node_modules").is_dir()


def _package_json(repo: Path) -> dict | None:
    try:
        return json.loads((repo / "package.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _test_command(pkg: dict) -> str | None:
    """The project's own test command from `package.json` scripts.test, or None when there is
    no real one (missing, empty, or the `npm init` placeholder that only prints an error)."""
    script = (pkg.get("scripts") or {}).get("test") or ""
    return None if (not script.strip() or _NO_TEST_SCRIPT in script) else script


def _installed_major(repo: Path, package: str) -> int | None:
    """The installed major version of a node_modules package, or None when it cannot be read.
    Directory-insensitive: it reads the target's own installed copy, not any global one."""
    try:
        version = json.loads((repo / "node_modules" / package / "package.json").read_text())["version"]
        return int(str(version).lstrip("^~=v").split(".", 1)[0])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# L1.19 decision-space coverage (branch coverage via c8 / V8)
# ---------------------------------------------------------------------------

def _c8_available(repo: Path, timeout_seconds: float) -> bool:
    probe = _run_untrusted(["npx", "--no-install", "c8", "--version"], cwd=repo, env={},
                           timeout_seconds=min(timeout_seconds, 60))
    return probe.returncode == 0


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.19 for JS/TS: branch coverage from c8 (V8). Bands match the spec: >90% Healthy,
    60-90% Not Healthy, <60% Slop. `runtime_override` is accepted for a uniform harness
    signature and ignored: `node` on PATH is the runtime."""
    node = _node()
    if node is None:
        return _na("needs Node.js (node) in PATH")
    if not _node_modules_present(repo):
        return _na("dependencies not installed (node_modules missing); run the project's install first")
    pkg = _package_json(repo)
    if pkg is None:
        return _na("no readable package.json in the repo")
    test_cmd = _test_command(pkg)
    if test_cmd is None:
        return _na("no test command in package.json (scripts.test)")
    if not _c8_available(repo, timeout_seconds):
        return _na("needs c8 for coverage (npm i -D c8)")

    with tempfile.TemporaryDirectory(prefix="l1-jscov-") as directory:
        reports = Path(directory) / "reports"
        summary = reports / "coverage-summary.json"
        run = _run_untrusted(
            ["npx", "--no-install", "c8", "--reporter=json-summary",
             f"--reports-dir={reports}", f"--temp-directory={Path(directory) / 'tmp'}",
             *shlex.split(test_cmd)],
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        if run.returncode == 124:
            return _na("test suite timed out before coverage could be measured")
        # c8 writes the summary for every file that ran, even when some tests fail. No summary
        # means the suite did not build or ran no tests: n/a with the reason, never a 0.0 that
        # reads as real-but-terrible coverage (a silent failure is a lie).
        if not summary.exists():
            return _na(f"coverage produced no data (test command exit {run.returncode}): "
                       f"{_first_line(run.stderr or run.stdout)}")
        try:
            branches = json.loads(summary.read_text())["total"]["branches"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return _na("coverage summary had no branch totals")

    if int(branches.get("total", 0)) == 0:
        return _na("no enumerable decision branches found in the measured tree")

    pct = float(branches["pct"])
    result_band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{pct}% branch coverage from c8 (V8) "
                   f"({suite}; ran under {_runtime_name(node, repo, timeout_seconds)})",
    }


# ---------------------------------------------------------------------------
# L1.20 test determinism (shuffled-order runner re-runs)
# ---------------------------------------------------------------------------

# The runners this harness can drive into a randomized order, seed -> command. A project on
# any other runner is reported n/a with the runner named, never a guessed score.
_RUNNERS = {
    "vitest": lambda seed: ["npx", "--no-install", "vitest", "run",
                            "--sequence.shuffle", f"--sequence.seed={seed}"],
    "jest": lambda seed: ["npx", "--no-install", "jest", f"--seed={seed}", "--ci"],
}

# Runners this harness recognises but cannot order-randomize; named so the n/a reason is
# specific about what was detected.
_UNDRIVABLE = ("mocha", "ava", "tape", "tap", "jasmine", "node --test")

# A marker that the runner actually executed its suite, so a nonzero exit is read as test
# failures rather than the runner never running (missing binary, build error, no tests).
_RAN_MARKERS = {
    "vitest": ("Test Files", "Tests "),
    "jest": ("Tests:", "Test Suites:"),
}


def _detect_runner(pkg: dict) -> str | None:
    """The test runner the project uses, from its deps and its test script. Returns a drivable
    runner key ('vitest'/'jest'), a recognised-but-undrivable runner name, or None."""
    deps = {**(pkg.get("devDependencies") or {}), **(pkg.get("dependencies") or {})}
    script = (pkg.get("scripts") or {}).get("test") or ""
    for name in _RUNNERS:
        if name in deps or name in script:
            return name
    for name in _UNDRIVABLE:
        if name.split()[0] in deps or name in script:
            return name
    return None


def _suite_ran(runner: str, output: str) -> bool:
    return any(marker in output for marker in _RAN_MARKERS[runner])


def _failure_summary(output: str) -> str:
    """A line that names the failure, so a nonzero run surfaces a reason a reader can act on
    rather than a bare score."""
    for line in output.splitlines():
        if "fail" in line.lower():
            return line.strip()[:200]
    return _first_line(output)


def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.20 for JS/TS: run the project's own runner `runs` times in a shuffled order with a
    distinct seed, counting the runs where the whole suite passes. Value is "passing/runs".
    Bands: 5/5 Healthy, 4/5 Not Healthy, <4/5 Slop. `runtime_override` is accepted for a
    uniform harness signature and ignored.

    A run that does not execute (missing runner, build error, no tests) is not a determinism
    result, so return n/a with the reason rather than a misleading 0/5. When the suite runs
    but some tests fail, the failing seeds' reasons are surfaced in details."""
    node = _node()
    if node is None:
        return _na("needs Node.js (node) in PATH")
    if not _node_modules_present(repo):
        return _na("dependencies not installed (node_modules missing); run the project's install first")
    pkg = _package_json(repo)
    if pkg is None:
        return _na("no readable package.json in the repo")
    runner = _detect_runner(pkg)
    builder = _RUNNERS.get(runner or "")
    if builder is None:
        return _na("determinism needs an order-randomizing runner (vitest --sequence.shuffle or "
                   f"jest --seed); detected {runner or 'no recognized test runner'}")
    if runner == "jest":
        major = _installed_major(repo, "jest")
        if major is not None and major < 30:
            return _na(f"jest --seed needs jest>=30; detected jest {major} in node_modules")

    runtime = _runtime_name(node, repo, timeout_seconds)
    passing = 0
    failing: list[str] = []
    for seed in range(1, runs + 1):
        run = _run_untrusted(builder(seed), cwd=repo, env={}, timeout_seconds=timeout_seconds)
        output = (run.stdout or "") + (run.stderr or "")
        if run.returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if not _suite_ran(runner, output):
            return _na(f"the suite did not run (seed {seed}: no {runner} tests executed under "
                       f"{runtime}); determinism not measured")
        if run.returncode == 0:
            passing += 1
        else:
            failing.append(f"seed {seed}: {_failure_summary(output)}")

    result_band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    details = f"{passing} of {runs} shuffled-order {runner} runs passed cleanly (under {runtime})"
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}
