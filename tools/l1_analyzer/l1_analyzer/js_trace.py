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

Directory-insensitive by construction: commands run with `cwd=repo`, so the project's own
`node_modules` and `package.json` test script are used. When nvm is installed it is sourced
and `nvm use` runs in the repo, so `.nvmrc` selects the node version (nvm is shell-resident,
sourced from `$NVM_DIR/nvm.sh`, and cannot be found on PATH like a shim); without nvm the
ambient node is used. The resolved `node --version` is named in every measured result.
Following the shared discipline, each path returns an explicit *not measured* reason rather
than a guessed number, and runs the project's (untrusted) suite in a new process group with a
hard timeout. `runtime_override` is accepted for a uniform harness signature and ignored: the
project's own node (via nvm/.nvmrc when present) is the runtime, and it selects its own runner.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
from pathlib import Path

from l1_analyzer.boundary import boundary, text_or_empty
from l1_analyzer.pytest_trace import (
    L1Result,
    _first_line,
    _na,
    _run_untrusted,
    coverage_band,
    determinism_band,
)

# The default `npm init` test script; a real command, but it runs no tests.
_NO_TEST_SCRIPT = "no test specified"


def _node() -> str | None:
    return shutil.which("node")


def _nvm_dir() -> Path | None:
    """The nvm install, or None. nvm is a shell function sourced from `$NVM_DIR/nvm.sh`
    (default `~/.nvm/nvm.sh`) - there is nowhere else for it to be - so it cannot be found on
    PATH like a shim; it must be sourced."""
    directory = Path(os.environ.get("NVM_DIR") or (Path.home() / ".nvm"))
    return directory if (directory / "nvm.sh").exists() else None


def _wrap(repo: Path, cmd: list[str]) -> list[str]:
    """Run `cmd` under the node version the repo pins. When nvm is installed, source it and
    `nvm use` (with cwd=repo, so its `.nvmrc` selects the version), then exec the command so a
    bare `node`/`npx` resolves to that version. Without nvm, run the command unchanged under
    the ambient node. This is what makes JS directory-insensitive under nvm."""
    nvm = _nvm_dir()
    if nvm is None:
        return cmd
    script = f'. "{nvm / "nvm.sh"}" >/dev/null 2>&1; nvm use --silent >/dev/null 2>&1; exec "$@"'
    return ["bash", "-c", script, "nvm", *cmd]


def _using_nvm() -> str:
    return " via nvm" if _nvm_dir() is not None else ""


def _node_version(repo: Path, timeout_seconds: float) -> str:
    probe = _run_untrusted(_wrap(repo, ["node", "--version"]), cwd=repo, env={},
                           timeout_seconds=min(timeout_seconds, 30))
    return _first_line(probe.stdout) if probe.returncode == 0 else "an unknown node runtime"


def _runtime_name(repo: Path, timeout_seconds: float) -> str:
    """The Node runtime that ran, named so the result says which environment measured it.
    Under nvm the version is the one `.nvmrc` selected; the pin is appended for confirmation."""
    version = _node_version(repo, timeout_seconds)
    pin = pin_in(text_or_empty(repo / ".nvmrc"))
    pinned = f" (.nvmrc pins {pin})" if pin and pin != "no output" else ""
    return f"{version}{_using_nvm()}{pinned}"


def pin_in(text: str) -> str:
    """The version an `.nvmrc` selects, from its text. Nothing if it names none."""
    return _first_line(text) if text else ""




def _node_modules_present(repo: Path) -> bool:
    return (repo / "node_modules").is_dir()


@boundary
def _package_json(repo: Path) -> dict | None:
    """The repository's own package.json, parsed, or nothing when it cannot be had.

    Declared the boundary rather than split: there is no decision here to lift out. It
    obtains bytes and hands back what they parse to, and the caller turns None into a
    refusal to measure."""
    try:
        return json.loads((repo / "package.json").read_text())
    # honest-code-allow: L1.21.8 - the caller turns this None into _na("no readable package.json in the repo"), which covers absent and malformed alike and is a refusal to measure rather than a clean reading
    except (OSError, json.JSONDecodeError):
        return None


def _test_command(pkg: dict) -> str | None:
    """The project's own test command from `package.json` scripts.test, or None when there is
    no real one (missing, empty, or the `npm init` placeholder that only prints an error)."""
    script = (pkg.get("scripts") or {}).get("test") or ""
    return None if (not script.strip() or _NO_TEST_SCRIPT in script) else script


def _installed_major(repo: Path, package: str) -> tuple[int | None, str]:
    """The installed major version of a node_modules package, and why it is unknown.

    Directory-insensitive: it reads the target's own installed copy, not any global one.

    The reason travels with the absence because the caller's guard used to read
    `if major is not None and major < 30`, so a version nobody could read PROCEEDED to the
    measurement. Unknown has to be its own answer, or an assumption is measured as a fact."""
    text = _read_installed(repo / "node_modules" / package / "package.json")
    if text is None:
        return None, f"{package}'s installed package.json could not be read"
    return major_in(text, package)


def major_in(text: str, package: str) -> tuple[int | None, str]:
    """The major version an installed package.json declares, and why it is unknown.

    Every reason names the package and what was wrong with it, because a caller's guard
    once read `if major is not None and major < 30` and a version nobody could read
    PROCEEDED to the measurement."""
    try:
        version = json.loads(text)["version"]
    except json.JSONDecodeError:
        return None, f"{package}'s installed package.json is not valid JSON"
    except KeyError:
        return None, f"{package}'s installed package.json declares no version"
    try:
        return int(str(version).lstrip("^~=v").split(".", 1)[0]), ""
    except ValueError:
        return None, f"{package}'s installed version {version!r} has no readable major number"


@boundary
def _read_installed(path: Path) -> str | None:
    """One installed package.json's text, or nothing when it cannot be read."""
    try:
        return path.read_text()
    # honest-code-allow: L1.21.8 - the None is the caller's "could not be read" reason, which it names and hands on, so nothing is reported as success
    except OSError:
        return None


# ---------------------------------------------------------------------------
# L1.19 decision-space coverage (branch coverage via c8 / V8)
# ---------------------------------------------------------------------------

def _c8_available(repo: Path, timeout_seconds: float) -> bool:
    probe = _run_untrusted(_wrap(repo, ["npx", "--no-install", "c8", "--version"]), cwd=repo, env={},
                           timeout_seconds=min(timeout_seconds, 60))
    return probe.returncode == 0


def _coverage_verdict(branches: dict, returncode: int, runtime: str) -> L1Result:
    """L1.19 from a finished run and c8's branch totals. No I/O, so it can be asserted.

    Extracted because it could not be reached otherwise. `decision_space_coverage` probes node,
    probes c8, wraps the command in nvm, opens a temp directory, reads the summary and decides
    the band inside one function, so the band table below was only ever provable through a fake
    that wrote the very summary file the module then read back.

    The timeout is decided first, before any total is touched: a killed run wrote no summary,
    so the caller has nothing to hand over but an empty object.

    `branches` is read by subscript. c8 writes `total`, `covered`, `skipped` and `pct` into
    every json-summary report it produces, and a summary missing them is a schema change rather
    than a tree with no branches. Defaulting the miss to zero would file that schema change
    under the answer written for an empty tree, which is the one thing this module must not do.
    """
    if returncode == 124:
        return _na("test suite timed out before coverage could be measured")
    if int(branches["total"]) == 0:
        return _na("no enumerable decision branches found in the measured tree")
    pct = float(branches["pct"])
    suite = "suite passed" if returncode == 0 else f"suite exit {returncode}"
    return {
        "value": round(pct, 1),
        "band": coverage_band(pct),
        "details": f"{pct}% branch coverage from c8 (V8) ({suite}; ran under {runtime})",
    }


def _toolchain(repo: Path) -> tuple[L1Result | None, dict | None]:
    """Either a refusal or a usable toolchain, never a half-resolved one. Exactly one of the
    two is None, so a caller that forgets the check gets a TypeError rather than a run
    against a toolchain that was never found.

    Both L1.19 and L1.20 carried these eight lines. Two copies is two sets of preconditions
    that can drift: one indicator could learn a new one and the other keep running without
    it, and the panel would then report n/a for coverage and a number for determinism on a
    repo where neither could be measured."""
    # Only node's PRESENCE is resolved, never its path: every command here runs through
    # _wrap, which spells a bare `node` so nvm can select the repo's version. A field
    # holding the path would be a value nobody reads.
    if _node() is None:
        return _na("needs Node.js (node) in PATH"), None
    if not _node_modules_present(repo):
        return _na("dependencies not installed (node_modules missing); run the project's "
                   "install first"), None
    pkg = _package_json(repo)
    if pkg is None:
        return _na("no readable package.json in the repo"), None
    return None, pkg


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.19 for JS/TS: branch coverage from c8 (V8). Bands match the spec: >90% Healthy,
    60-90% Not Healthy, <60% Slop. `runtime_override` is accepted for a uniform harness
    signature and ignored: `node` on PATH is the runtime."""
    refusal, tools = _toolchain(repo)
    if refusal is not None:
        return refusal
    pkg = tools
    test_cmd = _test_command(pkg)
    if test_cmd is None:
        return _na("no test command in package.json (scripts.test)")
    if not _c8_available(repo, timeout_seconds):
        return _na("needs c8 for coverage (npm i -D c8)")

    with tempfile.TemporaryDirectory(prefix="l1-jscov-") as directory:
        reports = Path(directory) / "reports"
        summary = reports / "coverage-summary.json"
        run = _run_untrusted(
            _wrap(repo, ["npx", "--no-install", "c8", "--reporter=json-summary",
                         f"--reports-dir={reports}", f"--temp-directory={Path(directory) / 'tmp'}",
                         *shlex.split(test_cmd)]),
            cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        runtime = _runtime_name(repo, timeout_seconds)
        if run.returncode == 124:
            return _coverage_verdict({}, run.returncode, runtime)
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

    return _coverage_verdict(branches, run.returncode, runtime)


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


def _determinism_verdict(per_seed: list[tuple[int, str]], runner: str, runtime: str) -> L1Result:
    """L1.20 from the outcome of every shuffled-order run. No I/O, so it can be asserted.

    `per_seed` is one `(returncode, combined output)` pair per run made, in seed order, so seed
    N is the Nth pair. The denominator is the number of pairs handed over rather than a count
    passed alongside them: a promised total and a list of outcomes are two statements of one
    fact, and only one of them can be right when they disagree.

    A run that stopped the count leaves a shorter list, and its own row says which run it was,
    so the n/a is reached before the denominator matters. No runs at all is n/a as well: zero
    clean out of zero satisfies `passing == runs`, which is how a measure that ran nothing
    issues itself a clean bill.
    """
    if not per_seed:
        return _na("no shuffled-order runs were made; determinism not measured")
    passing = 0
    failing: list[str] = []
    for seed, (returncode, output) in enumerate(per_seed, start=1):
        if returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if not _suite_ran(runner, output):
            return _na(f"the suite did not run (seed {seed}: no {runner} tests executed under "
                       f"{runtime}); determinism not measured")
        if returncode == 0:
            passing += 1
        else:
            failing.append(f"seed {seed}: {_failure_summary(output)}")

    runs = len(per_seed)
    details = f"{passing} of {runs} shuffled-order {runner} runs passed cleanly (under {runtime})"
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {
        "value": f"{passing}/{runs}",
        "band": determinism_band(passing, runs),
        "details": details,
    }


def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None) -> L1Result:
    """L1.20 for JS/TS: run the project's own runner `runs` times in a shuffled order with a
    distinct seed, counting the runs where the whole suite passes. Value is "passing/runs".
    Bands: 5/5 Healthy, 4/5 Not Healthy, <4/5 Slop. `runtime_override` is accepted for a
    uniform harness signature and ignored.

    A run that does not execute (missing runner, build error, no tests) is not a determinism
    result, so return n/a with the reason rather than a misleading 0/5. When the suite runs
    but some tests fail, the failing seeds' reasons are surfaced in details."""
    refusal, tools = _toolchain(repo)
    if refusal is not None:
        return refusal
    pkg = tools
    runner = _detect_runner(pkg)
    builder = _RUNNERS.get(runner or "")
    if builder is None:
        return _na("determinism needs an order-randomizing runner (vitest --sequence.shuffle or "
                   f"jest --seed); detected {runner or 'no recognized test runner'}")
    if runner == "jest":
        major, unknown = _installed_major(repo, "jest")
        # Refused rather than attempted. `jest --seed` needs jest 30, and driving it at a
        # version nobody could identify produces a determinism figure with an assumption
        # underneath it.
        if unknown:
            return _na(f"determinism needs a known jest version to know whether --seed "
                       f"exists, and {unknown}")
        if major is not None and major < 30:
            return _na(f"jest --seed needs jest>=30; detected jest {major} in node_modules")

    runtime = _runtime_name(repo, timeout_seconds)
    per_seed: list[tuple[int, str]] = []
    for seed in range(1, runs + 1):
        run = _run_untrusted(_wrap(repo, builder(seed)), cwd=repo, env={}, timeout_seconds=timeout_seconds)
        output = (run.stdout or "") + (run.stderr or "")
        per_seed.append((run.returncode, output))
        # A run that timed out or never executed a suite ends the measurement, and nothing a
        # later seed could do would change that, so the remaining seeds are not spent. The
        # verdict names which of the two happened; this only stops the spending.
        if run.returncode == 124 or not _suite_ran(runner, output):
            break
    return _determinism_verdict(per_seed, runner, runtime)
