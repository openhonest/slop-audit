"""Runtime harness for L1.19 / L1.20 on Ruby repositories - the `bundle exec`
counterpart to pytest_trace, rust_trace and go_trace. It actually executes the
target's own test suite (untrusted code, in a new process group with a hard
timeout, exactly like the other paths) rather than reporting n/a.

- **L1.19 decision-space coverage**: SimpleCov branch coverage, read from the
  suite's own `coverage/.resultset.json` after one run. SimpleCov must be started
  in the target's `spec_helper` / `test_helper`; the analyzer cannot inject it
  non-invasively, so when no resultset appears the result is n/a with that exact,
  actionable reason rather than a guessed number.
- **L1.20 test determinism**: the suite run five times in randomized order,
  counting the runs where every test passes. RSpec randomizes natively
  (`--order random --seed <N>`); Minitest randomizes via `TESTOPTS=--seed=<N>`,
  so no external plugin is needed.

Directory-insensitive by construction: `ruby` and `bundle` are invoked with
`cwd=repo`, so the target's `Gemfile` and `.ruby-version` (rbenv / asdf shims)
select ruby and its gems, whatever launched the analyzer. The resolved
`ruby --version` is named in every measured result. Following the shared
discipline, each path returns an explicit *not measured* reason rather than a
guessed number, and RSpec is preferred over Minitest when both are present.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from l1_analyzer.pytest_trace import (
    L1Result,
    _first_line,
    _na,
    _run_untrusted,
    resolve_via_shim,
)

# One summary line per runner: group(1) is the number of tests that ran, group(0)
# is the whole line (surfaced verbatim when a seed fails). No summary line at all
# means the suite never ran - a build error, missing gems, or an empty suite.
_SUMMARY = {
    "rspec": re.compile(r"(\d+) examples?, \d+ failures?[^\n]*"),
    "minitest": re.compile(r"(\d+) runs?, \d+ assertions?, \d+ (?:failures?|errors?)[^\n]*"),
}

# `bundle exec` commands per runner. RSpec and Minitest each randomize order natively.
_DETERMINISM_COMMAND = {
    "rspec": lambda bundle, seed: [bundle, "exec", "rspec", "--order", "random", "--seed", str(seed)],
    "minitest": lambda bundle, seed: [bundle, "exec", "rake", "test", f"TESTOPTS=--seed={seed}"],
}
_COVERAGE_COMMAND = {
    "rspec": lambda bundle: [bundle, "exec", "rspec"],
    "minitest": lambda bundle: [bundle, "exec", "rake", "test"],
}


def _ruby() -> str | None:
    return shutil.which("ruby")


def _bundle() -> str | None:
    return shutil.which("bundle")


def _lock_has_rspec(repo: Path) -> bool:
    """True when Gemfile.lock names rspec - the third RSpec signal, so a repo whose specs
    live outside a top-level spec/ directory is still detected as RSpec."""
    try:
        return "rspec" in (repo / "Gemfile.lock").read_text()
    except OSError:
        return False


def _detect_runner(repo: Path) -> str | None:
    """'rspec', 'minitest', or None. RSpec is preferred: a spec/ directory, a .rspec file,
    or rspec in Gemfile.lock. Otherwise a test/ directory with a Rakefile signals Minitest.
    None means neither suite shape is present - measured as n/a, never as 0/5."""
    if (repo / "spec").is_dir() or (repo / ".rspec").exists() or _lock_has_rspec(repo):
        return "rspec"
    if (repo / "test").is_dir() and (repo / "Rakefile").exists():
        return "minitest"
    return None


def _pin(repo: Path, timeout_seconds: float) -> tuple[str | None, str | None, dict, str]:
    """(ruby, bundle, env, provenance): pin ruby via a shim manager (rbenv/asdf/mise which
    ruby) when one resolves it for this repo, so a homebrew ruby ahead of the shim on PATH
    cannot silently win. env prepends the pinned ruby's bin so bundle and the suite run under
    it. Falls back to the ambient ruby/bundle (env {}, no provenance suffix)."""
    ruby_path, note = resolve_via_shim(repo, "ruby", timeout_seconds)
    if ruby_path is None:
        return _ruby(), _bundle(), {}, ""
    bindir = Path(ruby_path).parent
    pinned_bundle = bindir / "bundle"
    bundle = str(pinned_bundle) if pinned_bundle.exists() else _bundle()
    return ruby_path, bundle, {"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", "")}, f", {note}"


def _ruby_version(ruby: str, repo: Path, timeout_seconds: float, env: dict) -> str:
    """The pinned ruby's version, run with cwd=repo (and the pin's PATH) so .ruby-version
    wins, named so every measured result says which interpreter measured it."""
    probe = _run_untrusted([ruby, "--version"], cwd=repo, env=env, timeout_seconds=min(timeout_seconds, 30))
    return _first_line(probe.stdout) if probe.returncode == 0 else "an unknown ruby"


def _ran(runner: str, output: str) -> int:
    """Total tests the runner reported across its summary lines. Zero means nothing ran."""
    return sum(int(match.group(1)) for match in _SUMMARY[runner].finditer(output))


def _summary_line(runner: str, output: str) -> str:
    """The runner's summary line (e.g. '5 examples, 2 failures'), or the first output line -
    what turns a bare 0/5 into a reason a reader can act on."""
    match = _SUMMARY[runner].search(output)
    return match.group(0).strip() if match else _first_line(output)


# ---------------------------------------------------------------------------
# L1.19 decision-space coverage (SimpleCov branch data)
# ---------------------------------------------------------------------------

def _branch_totals(resultset: dict) -> tuple[int, int]:
    """(covered, total) SimpleCov branches summed across every command and file in the
    resultset. A branch leaf is covered when its hit count is greater than zero. Files
    stored in the old line-only format (a list, no 'branches') contribute nothing."""
    covered = total = 0
    for command in resultset.values():
        for file_data in command.get("coverage", {}).values():
            if not isinstance(file_data, dict):
                continue
            for sub_branches in file_data.get("branches", {}).values():
                for hits in sub_branches.values():
                    total += 1
                    if hits > 0:
                        covered += 1
    return covered, total


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.19 for Ruby: SimpleCov branch coverage from the suite's own coverage/.resultset.json.
    Bands match the spec: >90% Healthy, 60-90% Not Healthy, <60% Slop. `runtime_override` is
    accepted for a uniform harness signature and ignored: the target's shims select ruby."""
    ruby, bundle, env, prov = _pin(repo, timeout_seconds)
    if ruby is None or bundle is None:
        return _na("needs Ruby and Bundler (ruby, bundle) in PATH")
    runner = _detect_runner(repo)
    if runner is None:
        return _na("no RSpec (spec/, .rspec, or rspec in Gemfile.lock) or Minitest (test/ + Rakefile) suite detected")
    version = _ruby_version(ruby, repo, timeout_seconds, env) + prov

    resultset_file = repo / "coverage" / ".resultset.json"
    run = _run_untrusted(_COVERAGE_COMMAND[runner](bundle), cwd=repo, env=env, timeout_seconds=timeout_seconds)
    if run.returncode == 124:
        return _na("test suite timed out before coverage could be measured")
    # SimpleCov must be started in the suite's spec_helper; it cannot be injected
    # non-invasively. No resultset means we cannot measure - n/a with the exact remedy,
    # never a 0.0 that reads as real-but-terrible coverage (a silent failure is a lie).
    if not resultset_file.exists():
        return _na("Ruby branch coverage needs SimpleCov started in the suite's spec_helper "
                   f"(coverage/.resultset.json not produced under {version})")
    try:
        resultset = json.loads(resultset_file.read_text())
    except (OSError, json.JSONDecodeError):
        return _na("SimpleCov resultset was unreadable")

    covered, total = _branch_totals(resultset)
    if total == 0:
        return _na(f"SimpleCov produced no branch data; enable branch coverage in the suite's spec_helper "
                   f"(SimpleCov.start {{ enable_coverage :branch }}) under {version}")

    pct = covered / total * 100
    result_band = "Healthy" if pct > 90 else ("Not Healthy" if pct >= 60 else "Slop")
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{covered}/{total} SimpleCov branches exercised by tests "
                   f"({suite}; ran under {version})",
    }


# ---------------------------------------------------------------------------
# L1.20 test determinism (repeated randomized-order runs)
# ---------------------------------------------------------------------------

def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.20 for Ruby: run the suite `runs` times in randomized order and count the runs
    where every test passes. Value is "passing/runs". Bands: 5/5 Healthy, 4/5 Not Healthy,
    <4/5 Slop. A run that builds nothing or runs no tests is not a determinism result, so
    return n/a with the reason rather than a misleading 0/5. When the suite runs but some
    tests fail, the failing seeds' summary lines are surfaced in details."""
    ruby, bundle, env, prov = _pin(repo, timeout_seconds)
    if ruby is None or bundle is None:
        return _na("needs Ruby and Bundler (ruby, bundle) in PATH")
    runner = _detect_runner(repo)
    if runner is None:
        return _na("no RSpec (spec/, .rspec, or rspec in Gemfile.lock) or Minitest (test/ + Rakefile) suite detected")
    version = _ruby_version(ruby, repo, timeout_seconds, env) + prov

    passing = 0
    failing: list[str] = []
    for seed in range(1, runs + 1):
        run = _run_untrusted(_DETERMINISM_COMMAND[runner](bundle, seed), cwd=repo, env=env, timeout_seconds=timeout_seconds)
        output = (run.stdout or "") + (run.stderr or "")
        if run.returncode == 124:
            return _na(f"a randomized run timed out (seed {seed}); determinism not measured")
        if _ran(runner, output) == 0:
            return _na(f"the suite did not run (seed {seed}, exit {run.returncode}: {_first_line(output)}); "
                       f"determinism not measured under {version}")
        if run.returncode == 0:
            passing += 1
        else:  # the suite ran, but not every test passed
            failing.append(f"seed {seed}: {_summary_line(runner, output)}")

    result_band = "Healthy" if passing == runs else ("Not Healthy" if passing == runs - 1 else "Slop")
    details = f"{passing} of {runs} randomized-order runs passed cleanly (under {version})"
    if failing:
        details += f"; runs with failures: {'; '.join(failing[:3])}"
    return {"value": f"{passing}/{runs}", "band": result_band, "details": details}
