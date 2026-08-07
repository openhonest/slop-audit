"""Runtime thread-safety harness: run the repo's test suite under a race detector.

This is the dynamic counterpart to the static thread-surface meter, and it sits in
the same seat as L1.19/L1.20: those run the suite under coverage / repeated
randomized execution; this runs it under ThreadSanitizer. The static meter says
WHERE the concurrency surface is; this says whether a race actually FIRES.

Honesty, three ways, each with a precedent in pytest_trace:
  1. Bounded by the suite. TSan only reports races the tests actually schedule.
     "no race observed" is NOT "race-free" - it is evidence bounded by the test
     suite, exactly as coverage is bounded by it. Never a proof of absence.
  2. Runs untrusted code (builds and executes the target), so it is CLI/CI/local
     only, never the public web path (which is exec_tests=False, "never run your
     code"). Execution goes through pytest_trace._run_untrusted: new process group,
     hard timeout.
  3. Toolchain-gated. No nightly + sanitizer -> n/a with a reason, reported loud,
     never a false "clean".

Verdicts:
  race-observed     - TSan reported >=1 data race during the suite (a proven finding)
  no-race-in-tests  - the suite ran under TSan and reported none (bounded by the suite)
  n/a               - not run (no toolchain, no tests, build failed, timeout), with why

The parser (parse_tsan) is the pure, behaviour-tested core; the orchestrator is the
untrusted-execution wrapper around it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TypedDict

from l1_analyzer.pytest_trace import _run_untrusted

RACE_OBSERVED = "race-observed"
NO_RACE_IN_TESTS = "no-race-in-tests"
NA = "n/a"


class RaceFinding(TypedDict):
    """One data race ThreadSanitizer reported. file/line come from the SUMMARY line;
    accesses are the two conflicting source sites (the first in-tree frame of each)."""
    file: str
    line: int
    symbol: str
    accesses: list[tuple[str, int]]


class RaceResult(TypedDict):
    verdict: str
    value: str
    band: str
    tool: str
    findings: list[RaceFinding]
    details: str


# A TSan report is a block starting at this banner; each ends in a SUMMARY line.
_RACE_BANNER = "WARNING: ThreadSanitizer: data race"
_SUMMARY = re.compile(r"SUMMARY: ThreadSanitizer: data race (?P<file>[^:\s]+):(?P<line>\d+)(?::\d+)? in (?P<symbol>.+)")
# A stack frame:  "#0 module::func::hHASH src/wal.rs:1955:24 (binary+0x...)"
_FRAME = re.compile(r"#\d+ .+?\s(?P<file>[^\s:]+\.\w+):(?P<line>\d+)(?::\d+)?(?:\s|$|\()")
# The access header lines that precede each conflicting frame.
_ACCESS = re.compile(r"(?:Write|Read|Previous write|Previous read|Atomic write|Atomic read) of size")


def parse_tsan(output: str) -> list[RaceFinding]:
    """Extract the data races from ThreadSanitizer output. Deterministic, pure.

    One finding per race block: the SUMMARY line gives the primary file:line:symbol;
    the first source frame under each access header gives the two conflicting sites.
    """
    findings: list[RaceFinding] = []
    blocks = output.split(_RACE_BANNER)
    for block in blocks[1:]:                       # blocks[0] is preamble before the first race
        summary = _SUMMARY.search(block)
        if summary is None:
            continue                               # an incomplete block (e.g. truncated by timeout)
        accesses: list[tuple[str, int]] = []
        lines = block.splitlines()
        for i, ln in enumerate(lines):
            if _ACCESS.search(ln):
                frame = next((_FRAME.search(lines[j]) for j in range(i + 1, min(i + 6, len(lines)))
                              if _FRAME.search(lines[j])), None)
                if frame is not None:
                    accesses.append((frame["file"], int(frame["line"])))
        findings.append({
            "file": summary["file"],
            "line": int(summary["line"]),
            "symbol": summary["symbol"].strip(),
            "accesses": accesses,
        })
    return findings


def _verdict(findings: list[RaceFinding]) -> tuple[str, str, str]:
    """(verdict, band, value) from the parsed findings, for a suite that ran."""
    if findings:
        return RACE_OBSERVED, "Slop", f"{len(findings)} data race(s) observed"
    return NO_RACE_IN_TESTS, "Healthy", "no data race observed (bounded by the test suite)"


def _na(reason: str, tool: str = "tsan") -> RaceResult:
    return {"verdict": NA, "value": "n/a", "band": "n/a", "tool": tool, "findings": [], "details": reason}


def _rust_toolchain_reason() -> str | None:
    """Why the Rust race toolchain can't run, or None if it looks available. A loud
    reason beats a false clean: absence is disclosed, never measured as safe."""
    if shutil.which("cargo") is None or shutil.which("rustup") is None:
        return "needs cargo + rustup on PATH"
    try:
        toolchains = subprocess.run(["rustup", "toolchain", "list"], capture_output=True, text=True, timeout=30, check=False).stdout
    except (subprocess.SubprocessError, OSError):
        return "could not query rustup toolchains"
    if "nightly" not in toolchains:
        return "needs a nightly toolchain for -Zsanitizer=thread (rustup toolchain install nightly)"
    return None


def _host_target() -> str | None:
    try:
        out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, timeout=30, check=False).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    m = re.search(r"^host:\s*(\S+)", out, re.MULTILINE)
    return m.group(1) if m else None


def _rust_tsan_command(target: str) -> list[str]:
    """cargo test under ThreadSanitizer. -Zbuild-std rebuilds std with the sanitizer
    (required); the explicit --target is what makes the sanitizer instrumentation
    apply. RUSTFLAGS is set by the caller in env."""
    return ["cargo", "+nightly", "test", "-Zbuild-std", "--target", target, "--", "--test-threads=4"]


def detect_races(repo: Path, lang: str, timeout_seconds: float) -> RaceResult:
    """Run the repo's tests under a race detector and report observed data races.

    A finding is proven (TSan saw the race). The absence of findings is bounded by
    the suite, never a proof of safety - the details say so.
    """
    if lang != "rust":
        return _na(f"runtime race harness is Rust/ThreadSanitizer only; {lang} not supported yet")
    reason = _rust_toolchain_reason()
    if reason is not None:
        return _na(reason)
    target = _host_target()
    if target is None:
        return _na("could not determine the host target triple for the sanitizer")

    run = _run_untrusted(
        _rust_tsan_command(target), cwd=repo,
        env={"RUSTFLAGS": "-Zsanitizer=thread", "RUSTUP_TOOLCHAIN": "nightly"},
        timeout_seconds=timeout_seconds,
    )
    output = (run.stderr or "") + "\n" + (run.stdout or "")   # TSan writes to stderr
    if run.returncode == 124:
        # A race already found before the kill still counts; else it's simply not measured.
        found = parse_tsan(output)
        if found:
            verdict, band, value = _verdict(found)
            return {"verdict": verdict, "value": value, "band": band, "tool": "tsan", "findings": found,
                    "details": f"{value}; suite timed out before completing (partial run)"}
        return _na("suite timed out under ThreadSanitizer before any result")
    if _RACE_BANNER not in output and ("error[" in output or "could not compile" in output or "error: " in output):
        return _na(f"could not build the suite under ThreadSanitizer: {_first_error(output)}")

    findings = parse_tsan(output)
    verdict, band, value = _verdict(findings)
    suite = "suite passed" if run.returncode == 0 else f"suite exit {run.returncode}"
    return {"verdict": verdict, "value": value, "band": band, "tool": "tsan", "findings": findings,
            "details": f"{value} ({suite})"}


def _first_error(output: str) -> str:
    for line in output.splitlines():
        if line.strip().startswith("error"):
            return line.strip()[:200]
    return "unknown build error"


# --------------------------------------------------------------------------
# Stress runner. A second concurrency runner, and the one that needs no nightly:
# it builds and runs the suite under contention repeatedly on the STABLE toolchain.
# The code's own invariant checks (assert!, turso_assert!, debug_assert!) are the
# oracle; the runner's job is only to supply a schedule that trips one. A run that
# panics when other runs passed is a PROVEN nondeterministic failure - a race the
# suite's own asserts caught. Bounded by the suite's concurrency and the run count.
# --------------------------------------------------------------------------

NO_RACE_IN_STRESS = "no-race-in-stress"

# Rust panic, both formats: old `panicked at 'msg', file:line`, new `panicked at file:line:`.
_PANIC = re.compile(
    r"thread '(?P<thread>[^']*)' panicked at "
    r"(?:'(?P<msg_old>[^']*)', )?"
    r"(?P<file>[^\s:,]+\.\w+):(?P<line>\d+)"
)


class PanicFinding(TypedDict):
    file: str
    line: int
    thread: str
    message: str


def parse_panic(output: str) -> list[PanicFinding]:
    """Extract Rust panics from test output. Deterministic, pure. A panic during a
    stress run is an invariant check firing - the oracle that caught the race."""
    findings: list[PanicFinding] = []
    lines = output.splitlines()
    for i, line in enumerate(lines):
        m = _PANIC.search(line)
        if m is None:
            continue
        # New format carries the message on the following line; old format inline.
        message = m["msg_old"] or (lines[i + 1].strip() if i + 1 < len(lines) else "")
        findings.append({"file": m["file"], "line": int(m["line"]), "thread": m["thread"], "message": message[:200]})
    return findings


def _cargo_available() -> str | None:
    """Stress needs only cargo (stable), no rustup/nightly - that is the point."""
    return None if shutil.which("cargo") is not None else "needs cargo on PATH"


def stress_races(repo: Path, lang: str, runs: int, timeout_seconds: float) -> RaceResult:
    """Run the suite under contention `runs` times and report a panic that fires on
    some runs but not all - a proven nondeterministic (racy) failure.

    Verdicts: all runs pass -> no-race-in-stress (bounded by the suite + run count);
    a mix of pass and panic -> race-observed (the code's own assert caught it); every
    run fails the same way -> n/a (a deterministic failure, not a stress-caught race).
    """
    if lang != "rust":
        return _na(f"stress runner is Rust-only for now; {lang} not supported yet", tool="stress")
    reason = _cargo_available()
    if reason is not None:
        return _na(reason, tool="stress")

    passed = 0
    panics: list[PanicFinding] = []
    for _ in range(runs):
        run = _run_untrusted(
            ["cargo", "test", "--", "--test-threads=8"], cwd=repo, env={}, timeout_seconds=timeout_seconds,
        )
        output = (run.stderr or "") + "\n" + (run.stdout or "")
        if run.returncode == 124:
            return _na("a stress run timed out; concurrency not measured", tool="stress")
        if run.returncode == 0:
            passed += 1
        else:
            hit = parse_panic(output)
            if not hit and ("error[" in output or "could not compile" in output):
                return _na(f"could not build the suite: {_first_error(output)}", tool="stress")
            panics.extend(hit)

    if passed == runs:
        return {"verdict": NO_RACE_IN_STRESS, "value": f"{runs}/{runs} stress runs passed", "band": "Healthy",
                "tool": "stress", "findings": [], "details": f"no panic across {runs} contended runs (bounded by the suite)"}
    if passed == 0:
        return _na(f"every run failed the same way ({runs}/{runs}) - a deterministic failure, not a stress-caught race", tool="stress")
    # Mixed: proven nondeterministic. Report the panic(s), attributed to file:line.
    deduped = {(p["file"], p["line"]): p for p in panics}
    findings: list[RaceFinding] = [
        {"file": p["file"], "line": p["line"], "symbol": p["message"] or p["thread"], "accesses": []}
        for p in deduped.values()
    ]
    return {"verdict": RACE_OBSERVED, "value": f"nondeterministic failure ({passed}/{runs} passed)", "band": "Slop",
            "tool": "stress", "findings": findings,
            "details": f"a panic fired on {runs - passed} of {runs} contended runs but not the others - a proven race the suite's own asserts caught"}


def confirmed_surface(findings: list[RaceFinding], surface_files: set[str]) -> list[RaceFinding]:
    """Cross-reference: the observed races whose site sits in a file the static
    surface meter flagged. These are CONFIRMED exposed - static said 'verify here',
    the runtime says 'it raced here'. File-granular on purpose: a race lands on a
    field-access line, the static site on the `unsafe impl` line, same file."""
    def in_surface(f: RaceFinding) -> bool:
        candidates = [f["file"], *(a[0] for a in f["accesses"])]
        return any(any(c.endswith(sf) or sf.endswith(c) for sf in surface_files) for c in candidates)
    return [f for f in findings if in_surface(f)]
