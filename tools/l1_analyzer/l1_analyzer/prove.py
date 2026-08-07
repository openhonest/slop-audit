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
GPT-5.6 for generation and the stress runner for execution.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

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
