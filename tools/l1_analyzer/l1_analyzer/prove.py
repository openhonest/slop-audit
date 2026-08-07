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


# --------------------------------------------------------------------------
# Production loop: the model call and the execution, wired for the CLI.
#
# The generator follows Umbra's discipline (structure deterministic; the model only
# fills an already-located gap; the execution gate, not the model, decides), ported
# into slop-audit so the whole platform is self-contained. openai is an optional
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
    """Whether a generation model can be called (an OpenAI key is present)."""
    import os
    return bool(os.getenv("OPENAI_API_KEY"))


def _strip_fences(code: str) -> str:
    import re
    return re.sub(r"^```(?:rust)?\n|```$", "", code.strip(), flags=re.MULTILINE)


def generate(request: ProofRequest) -> str | None:
    """The prove-stage generator: GPT-5.6 writes a self-contained Rust test that
    reproduces the located hazard as a failing, nondeterministic race. Returns None when
    no model / openai is available - the loop then reports not-generated, never a false
    claim. The execution gate, not this call, decides whether the proof stands."""
    import os
    if not model_available():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    try:
        response = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(
            model="gpt-5.6",
            input=[
                {"role": "developer", "content": _CONCURRENCY_INSTRUCTION},
                {"role": "user", "content": request["context"]},
            ],
        )
    except Exception:  # noqa: BLE001 - any generation failure yields no proof, never a false claim
        return None
    return _strip_fences(response.output_text)


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
    return {"verdict": result["verdict"], "detail": result.get("details", result.get("value", ""))}


def prove_hazard(
    request: ProofRequest,
    work_dir: str,
    runs: int = 100,
    timeout_seconds: float = 300.0,
    model_call: ConcurrencyModelCall | None = None,
    run_generated: RunGenerated | None = None,
) -> ProofOutcome:
    """The full production loop for one located hazard: generate a test, run it under
    stress, retain iff it fires. model_call and run_generated default to the real
    generator and the stress runner; both are injectable so the honesty property stays
    testable without an API key or a build."""
    gen = model_call or generate
    run = run_generated or (lambda test: write_crate_and_stress(test, work_dir, runs, timeout_seconds))
    return prove(request, gen, run)
