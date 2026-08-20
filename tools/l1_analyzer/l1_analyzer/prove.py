"""Concurrency prove loop: turn a LOCATED hazard into a DEMONSTRATED one.

This is the runtime prove stage of the platform, mirroring Umbra's honesty discipline
on the concurrency axis:
  - Structure is deterministic. The hazard is located by the thread-surface meter (no
    model). The model never chooses what to prove.
  - The model runs only on an already-located gap. It receives one hazard plus the
    code context and returns a candidate threaded test.
  - Never trust, always run. The candidate is executed under a concurrency runner and
    RETAINED only if it genuinely fires a race. A hazard the loop cannot demonstrate is
    not claimed - the execution gate is the honesty.

Both the model call and the execution are injected, so the loop's honesty property
(retain iff demonstrated) is testable without an API key or a build. Production wires in
Claude Sonnet 5 for generation and the stress runner for execution.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from l1_analyzer import model_call as llm

DEMONSTRATED = "demonstrated"           # generated, run, and it fired a race (retained)
NOT_DEMONSTRATED = "not-demonstrated"   # generated and run, but no race fired (NOT claimed)
NOT_GENERATED = "not-generated"         # the model was unavailable or declined
NOT_RUN = "not-run"                     # no toolchain / build failed; not measured


class ProofRequest(TypedDict):
    """One located hazard to prove. Deterministic product of the static layer."""
    kind: str
    file: str
    line: int
    symbol: str
    context: str


class ProofRecord(TypedDict):
    """One attempted concurrency proof as the CLI RECORDS it and the card renders it.

    Not ProofOutcome, which is below and is what prove_hazard returns: that one carries the
    request it was made from, this one carries the located hazard flattened into a file, a
    line and a symbol. Two shapes, so two names. Writing this one as ProofOutcome first
    silently shadowed the other, which is the collision the separate names exist to stop.

    Declared because the card was reading these by guess: `o.get("symbol", "?")` over a
    `dict[str, object]`, with nothing to hold the producer to. A retained proof whose
    symbol went missing rendered as a question mark beside a real test source, which reads
    as a proof of something nobody can name rather than as a broken record.

    `generated_test` is None when the model produced nothing; that absence is a real case
    and the card tests for it before exposing the proof.

    Declared because the card was reading these by guess, `o.get("symbol", "?")` over a
    `dict[str, object]`, with nothing to hold the producer to. A proof whose symbol went
    missing rendered as a question mark beside a real test source, which reads as a proof
    of something nobody can name rather than as a broken record."""
    file: str
    line: int
    symbol: str
    verdict: str
    detail: str
    generated_test: str | None


class RunResult(TypedDict):
    """What a concurrency runner reports back about a generated test."""
    verdict: str        # a race_harness verdict: race-observed / no-race-* / n/a
    detail: str


class ProofOutcome(TypedDict):
    request: ProofRequest
    generated_test: str | None
    verdict: str
    detail: str


# The model receives a located hazard and returns a candidate test (or None if it is
# unavailable / declines). It never sees the whole codebase and never picks the hazard.
ConcurrencyModelCall = Callable[[ProofRequest], str | None]
# The runner writes the candidate into the repo, builds, and runs it under contention.
RunGenerated = Callable[[str], RunResult]

# A runner verdict that counts as a fired race (the demonstration).
_RACE_VERDICTS = frozenset({"race-observed"})
# A runner verdict that means "ran clean" (a real not-demonstrated, not a non-result).
_CLEAN_VERDICTS = frozenset({"no-race-in-tests", "no-race-in-stress"})


def proof_request(finding: dict, context: str) -> ProofRequest:
    """Build a proof request from a thread-surface finding plus its code context."""
    return {
        "kind": finding["kind"],
        "file": finding["file"],
        "line": finding["line"],
        "symbol": finding["symbol"],
        "context": context,
    }


def prove(request: ProofRequest, model_call: ConcurrencyModelCall, run_generated: RunGenerated) -> ProofOutcome:
    """Generate a test for the hazard, run it, and retain it only if it fires a race.

    The gate is strict on purpose: only an observed race is DEMONSTRATED. A clean run is
    NOT_DEMONSTRATED (bounded, not claimed); an unavailable model is NOT_GENERATED; an
    absent toolchain / failed build is NOT_RUN. The loop never claims what it did not run.
    """
    test = model_call(request)
    if test is None:
        return {"request": request, "generated_test": None, "verdict": NOT_GENERATED,
                "detail": "no model available to generate a proof for this hazard"}

    result = run_generated(test)
    verdict = result["verdict"]
    if verdict in _RACE_VERDICTS:
        return {"request": request, "generated_test": test, "verdict": DEMONSTRATED,
                "detail": f"the generated test fired a race: {result['detail']}"}
    if verdict in _CLEAN_VERDICTS:
        return {"request": request, "generated_test": test, "verdict": NOT_DEMONSTRATED,
                "detail": f"the generated test ran without firing a race (bounded, not a proof of safety): {result['detail']}"}
    return {"request": request, "generated_test": test, "verdict": NOT_RUN,
            "detail": f"the generated test could not be measured: {result['detail']}"}


def retained(outcomes: list[ProofOutcome]) -> list[ProofOutcome]:
    """Only demonstrated proofs survive into the report - Umbra's retention rule."""
    return [o for o in outcomes if o["verdict"] == DEMONSTRATED]


# --------------------------------------------------------------------------
# Production loop: the model call and the execution, wired for the CLI.
#
# The generator follows Umbra's discipline (structure deterministic; the model only
# fills an already-located gap; the execution gate, not the model, decides), ported
# into slop-audit so the whole platform is self-contained. anthropic is an optional
# dependency - absent, the loop reports not-generated, never a false claim.
# --------------------------------------------------------------------------

_CONCURRENCY_INSTRUCTION = (
    "You are given a located concurrency hazard from real code. Write ONE self-contained Rust file (a "
    "`#[cfg(test)] mod tests` with a single `#[test]` fn) that REPRODUCES the race the hazard describes and "
    "makes an assertion FAIL nondeterministically - failing on some runs and passing on others. Model the "
    "shared state with std types, or these crates if apt: crossbeam-skiplist, crossbeam-utils, crossbeam-queue. "
    "Spawn threads that drive the racy access concurrently and assert an invariant the race violates (a lost "
    "update, a torn read, an out-of-order observation). Use SMALL iteration counts and NO barrier so it is "
    "nondeterministic; the assertion must fail only because of the race. Output ONLY Rust code, no markdown "
    "fences, no prose."
)
# The reproduction crate may reach for these; std otherwise. Pinned, so the build is stable.
_PROVE_CRATE_DEPS = 'crossbeam-skiplist = "0.1"\ncrossbeam-utils = "0.8"\ncrossbeam-queue = "0.3"\n'


def model_available() -> bool:
    """Whether a generation model can be called (an Anthropic key is present).

    Re-exported from the one reader of the variable's NAME, so a rename cannot leave a
    second copy checking the old one. Three modules asked this question and two of them
    spelled the answer themselves."""
    return llm.model_available()


def _strip_fences(code: str) -> str:
    import re
    return re.sub(r"^```(?:rust)?\n|```$", "", code.strip(), flags=re.MULTILINE)


def generate(request: ProofRequest) -> str | None:
    """The prove-stage generator: Claude Sonnet 5 writes a self-contained Rust test that
    reproduces the located hazard as a failing, nondeterministic race. Returns None when
    no model / anthropic is available - the loop then reports not-generated, never a false
    claim. The execution gate, not this call, decides whether the proof stands."""
    # Through the one boundary. `model_call` is taken as a PARAMETER by `prove` above,
    # so the module is imported under a name that cannot shadow it.
    reply = llm.call(_CONCURRENCY_INSTRUCTION, request["context"], max_tokens=4096)
    return None if reply["text"] is None else _strip_fences(reply["text"])


def write_crate_and_stress(test_source: str, work_dir: str, runs: int, timeout_seconds: float) -> RunResult:
    """Execution gate: drop the generated test into a fresh crate and run it under the
    stress runner. A panic on some runs but not all is a proven race."""
    from pathlib import Path

    from l1_analyzer import race_harness
    crate = Path(work_dir)
    (crate / "src").mkdir(parents=True, exist_ok=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname = "proofcrate"\nversion = "0.0.0"\nedition = "2021"\n[dependencies]\n' + _PROVE_CRATE_DEPS
    )
    (crate / "src" / "lib.rs").write_text(test_source)
    result = race_harness.stress_races(crate, "rust", runs, timeout_seconds)
    # RaceResult is total, so details is there. The chain that stood here fell through to
    # the value and then to the empty string, two fallbacks for a field that cannot be
    # missing, and an empty detail would have read as a proof that explained nothing.
    return {"verdict": result["verdict"], "detail": result["details"]}


def prove_hazard(
    request: ProofRequest,
    model_call: ConcurrencyModelCall,
    run_generated: RunGenerated,
) -> ProofOutcome:
    """The loop for one located hazard: generate a test, run it under stress, retain iff
    it fires.

    BOTH COLLABORATORS ARE REQUIRED, and they defaulted to the real thing until
    2026-08-19: `model_call=None` meant the real generator and `run_generated=None` meant
    writing a crate and building it. A test that forgot either argument reached a paid API
    and a `cargo build` instead of failing, and it would have looked like it was testing
    the loop.

    `python_coverage_prove._prove_one` had the same shape and had already fixed it, with
    the reason written at the site. One module learned it and the other did not, which is
    the same class of defect twice in one package.

    The convenience the defaults bought belongs at the boundary, and cli.py is the one
    production caller: the place that knows a run is meant to spend money is the place
    that names the real generator and the real runner."""
    return prove(request, model_call, run_generated)
