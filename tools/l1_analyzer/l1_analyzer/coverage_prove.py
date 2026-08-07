"""Coverage-gap prove loop, the Umbra way - merged into slop-audit.

Umbra already does exactly this: locate the uncovered decision facets in a module
(from cargo-llvm-cov region coverage), turn each into an isolated proof request, ask a
model for one candidate test, render it, run it, and RETAIN it only when execution
contradicts the proposed expectation (a real gap the test now pins). We call Umbra's
own code for the whole loop and map its retained proofs onto slop-audit's adoptable-proof
surface (results['coverage_proofs'], rendered by card._proofs). Umbra proves the gap; it
never writes into the user's test file - adopting a surviving proof is the user's choice.

This is opt-in and needs the `coverage-prove` extra (umbra + openai) plus a Rust toolchain
with cargo-llvm-cov. Every path returns an explicit not-run reason rather than a guess.
"""

from __future__ import annotations

from pathlib import Path


def umbra_available() -> bool:
    try:
        import umbra.audit
        import umbra.semantic  # noqa: F401
    except ImportError:
        return False
    return True


def _mapped(proof: dict) -> dict:
    """One Umbra GeneratedProof -> slop-audit's adoptable-proof shape."""
    gap = proof.get("gap") or {}
    proposal = proof.get("proposal") or {}
    verification = proof.get("verification") or {}
    return {
        "function": proof.get("function", "?"),
        "language": proof.get("language", "rust"),
        "location": str(gap.get("location", "")),
        "explanation": proposal.get("plain_explanation", "") or str(gap.get("kind", "")),
        "test_source": verification.get("test_source", ""),
    }


def prove_coverage(module_path: Path, tests_path: Path, cap: int = 3) -> dict:
    """Run Umbra's coverage-gap proof loop for one (module, tests) pair and return the
    retained proofs in slop-audit's coverage_proofs shape. `retained` holds only proofs
    whose generated test genuinely failed against the current code (Umbra's gate)."""
    if not umbra_available():
        return {"retained": [], "attempted": 0, "detail": "needs the coverage-prove extra (umbra + openai)"}
    from umbra.audit import audit_rust
    from umbra.semantic import generate_proofs, model_available, proof_is_retained

    if not model_available():
        return {"retained": [], "attempted": 0, "detail": "needs OPENAI_API_KEY to generate coverage proofs"}

    result = audit_rust(Path(module_path), Path(tests_path))
    if not result.get("coverage_measured", False):
        return {"retained": [], "attempted": 0,
                "detail": f"coverage not measured: {result.get('reason', 'cargo-llvm-cov produced no data')}"}

    proof_run = generate_proofs(result, Path(module_path), model_call_cap=cap)
    proofs = proof_run.get("proofs", ())
    retained = [_mapped(p) for p in proofs if proof_is_retained(p)]
    return {"retained": retained, "attempted": len(proofs),
            "detail": f"{len(retained)}/{len(proofs)} generated coverage proofs were retained (genuinely failed)"}
