"""Runtime harness for L1.19 / L1.20 on C repositories - the gcov/lcov counterpart to
pytest_trace, rust_trace, and go_trace. C has no universal test runner, no standard coverage
format, and no standard test-order randomizer, so this harness is deliberately conservative:
it measures only what a Makefile `test`/`check` target plus gcov/lcov can measure, and returns
an explicit *not measured* reason everywhere else rather than a guessed number.

- **L1.19 decision-space coverage** (best-effort): when the repo has a Makefile with a `test`
  or `check` target and lcov (which drives gcov) is installed, build with coverage
  instrumentation (`CFLAGS`/`LDFLAGS` carry `--coverage`), run the target, and total gcov's
  line coverage with lcov. Line coverage is the honest decision-space proxy on the standard C
  toolchain - C has no standard branch-coverage convention - and the details string says so.
  Without a Makefile test target, or without lcov, or when the instrumented build produced no
  gcov data, coverage is n/a with an actionable reason, never a 0.0 that reads as
  real-but-terrible coverage (a silent failure is a lie).
- **L1.20 test determinism**: C has no standard test-order randomizer (no pytest-randomly or
  `go test -shuffle` analogue), so execution-order determinism is not measured. The result is
  n/a, naming the compiler that would have run the suite, never a misleading 0/5.

Directory-insensitive by construction: the compiler (`cc`) and the target's own Makefile are
detected against `cwd=repo`, whatever launched the analyzer, and the resolved `cc --version`
is named in every result. The target's (untrusted) test build runs in a new process group with
a hard timeout, exactly like the sibling harnesses.
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
)

_MAKEFILES = ("Makefile", "makefile", "GNUmakefile")
_TEST_TARGETS = ("test", "check")
_COVERAGE_FLAGS = "-O0 -g -fprofile-arcs -ftest-coverage"
# lcov's summary prints e.g. "  lines......: 87.5% (700 of 800 lines)"; the counts let us tell
# a real 0% from "no instrumented lines at all" (0 of 0), which is n/a, not Slop.
_LCOV_LINES = re.compile(r"lines\.+:\s+([\d.]+)%\s+\((\d+)\s+of\s+(\d+)\s+lines\)")


def _cc() -> str | None:
    return shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def _lcov() -> str | None:
    return shutil.which("lcov")


def _compiler(cc: str, repo: Path, timeout_seconds: float) -> str:
    """The C compiler `cc` resolves in the target's environment, named so the result says which
    toolchain measured it (or would have). Directory-insensitive: probed with cwd=repo."""
    probe = _run_untrusted([cc, "--version"], cwd=repo, env={}, timeout_seconds=min(timeout_seconds, 30))
    return _first_line(probe.stdout) if probe.returncode == 0 else "an unknown C compiler"


def _make_target(repo: Path) -> str | None:
    """The first of `test`/`check` the repo's Makefile declares as a target, or None. Read-only
    detection of the target's own build: the harness never edits the Makefile."""
    for name in _MAKEFILES:
        makefile = repo / name
        if makefile.exists():
            try:
                text = makefile.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return None
            for target in _TEST_TARGETS:
                if re.search(rf"^{target}\s*:", text, re.MULTILINE):
                    return target
            return None
    return None


def _coverage_verdict(summary_text: str, build_returncode: int, build_output: str,
                      compiler: str, target: str) -> L1Result:
    """L1.19 for C from lcov's summary text and the build that produced it. No I/O, so it can
    be asserted as a value.

    Extracted because it could not be reached otherwise. `decision_space_coverage` probes the
    toolchain, drives an instrumented `make`, shells out to lcov twice and decides the band
    inside one function, so this band table and these three refusals were only ever provable
    through a replaced `_run_untrusted` - a fake that answered from strings the test author
    wrote, and whose unrecognised-command branch returned a canned success, so a command it did
    not know about was filed under an answer written for a different one.

    The substitution this function performs and cannot show in its own value: L1.19 carries
    branch coverage for Python, and the standard C toolchain has no branch-coverage convention,
    so gcov LINE coverage goes into the same field. The `details` line discloses it. The value
    and the band cannot.

    `0 of 0` lines is the refusal that matters. lcov prints 0.0% for an instrumented build that
    executed no instrumented code, and a rate over no lines is an absent measurement rather
    than a measurement of zero - the difference between not-looked-at and read-and-terrible.
    """
    if build_returncode == 124:
        return _na(f"the test build/run timed out before coverage could be measured (make {target})")
    match = _LCOV_LINES.search(summary_text)
    # No gcov data means the instrumented build did not run the target's tests: n/a with the
    # reason, never a 0.0 that reads as real-but-terrible coverage.
    if match is None:
        return _na(f"coverage produced no gcov data (make {target} exit {build_returncode}): "
                   f"{_first_line(build_output)}")
    total_lines = int(match.group(3))
    if total_lines == 0:
        return _na(f"the instrumented build produced no gcov lines; `make {target}` did not run "
                   f"instrumented code (compiler: {compiler})")

    pct = float(match.group(1))
    covered = int(match.group(2))
    result_band = coverage_band(pct)
    suite = f"make {target} passed" if build_returncode == 0 else f"make {target} exit {build_returncode}"
    return {
        "value": round(pct, 1),
        "band": result_band,
        "details": f"{pct}% gcov LINE coverage ({covered}/{total_lines} lines; {suite}; "
                   f"compiled by {compiler}); C has no standard branch-coverage convention, so "
                   f"this field carries line coverage where other languages carry branch coverage",
    }


def _determinism_verdict(compiler: str) -> L1Result:
    """L1.20 for C: a permanent n/a, naming the compiler that would have run the suite.

    Not a gap in this harness and not a failure on the repository. C ships no standard
    test-order randomizer - no pytest-randomly, no `go test -shuffle` - so there is no shuffled
    run to count, and 0/5 would read as a suite that falls over when reordered rather than one
    that was never reordered. Pure, so the distinction is asserted rather than assumed.
    """
    return _na(f"C has no standard test-order randomizer; determinism not measured (compiler: {compiler})")


def decision_space_coverage(repo: Path, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.19 for C (best-effort): line coverage from a gcov-instrumented `make <target>`,
    totalled by lcov. Bands match the spec: >90% Healthy, 60-90% Not Healthy, <60% Slop.
    `runtime_override` is accepted for a uniform harness signature and ignored: C selects its
    compiler from PATH, not from a repo-pinned toolchain."""
    cc = _cc()
    if cc is None:
        return _na("needs a C compiler (cc/gcc/clang) in PATH")
    compiler = _compiler(cc, repo, timeout_seconds)
    target = _make_target(repo)
    if target is None:
        return _na("C has no standard coverage convention; provide a build that runs tests under "
                   "gcov/lcov (no Makefile test/check target found)")
    lcov = _lcov()
    if lcov is None:
        return _na(f"C coverage needs lcov to total gcov data; install lcov (compiler: {compiler})")

    with tempfile.TemporaryDirectory(prefix="l1-ccov-") as directory:
        info = Path(directory) / "cov.info"
        env = {"CFLAGS": _COVERAGE_FLAGS, "CXXFLAGS": _COVERAGE_FLAGS, "LDFLAGS": "--coverage"}
        build = _run_untrusted(["make", target], cwd=repo, env=env, timeout_seconds=timeout_seconds)
        build_output = build.stderr or build.stdout or ""
        if build.returncode == 124:
            return _coverage_verdict("", 124, build_output, compiler, target)
        capture = _run_untrusted(
            [lcov, "--capture", "--directory", str(repo), "--output-file", str(info), "--quiet"],
            cwd=repo, env={}, timeout_seconds=min(timeout_seconds, 120),
        )
        if capture.returncode == 124:
            return _na("lcov coverage capture timed out")
        summary = _run_untrusted([lcov, "--summary", str(info)], cwd=repo, env={},
                                 timeout_seconds=min(timeout_seconds, 60))
        summary_text = (summary.stdout or "") + (summary.stderr or "")

    return _coverage_verdict(summary_text, build.returncode, build_output, compiler, target)


def test_determinism(repo: Path, runs: int, timeout_seconds: float, runtime_override: str | None = None) -> L1Result:
    """L1.20 for C: C has no standard test-order randomizer (no pytest-randomly or
    `go test -shuffle` analogue), so execution-order determinism is not measured. Returns n/a,
    naming the compiler that would run the suite, never a misleading 0/5. `runs` and
    `runtime_override` are accepted for a uniform harness signature."""
    cc = _cc()
    if cc is None:
        return _na("needs a C compiler (cc/gcc/clang) in PATH")
    return _determinism_verdict(_compiler(cc, repo, timeout_seconds))
