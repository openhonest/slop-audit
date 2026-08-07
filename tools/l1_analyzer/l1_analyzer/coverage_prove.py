"""Coverage-gap prove loop - slop-audit's own, no Umbra at runtime.

The same discipline as the concurrency prove loop and as Umbra (which was the reference,
not a dependency): structure is deterministic, the model only fills an already-located
gap, and the EXECUTION gate decides. Here the gap is an uncovered decision branch:

  locate   rust_facets over the module + rust_trace's per-module uncovered lines
  propose  a model writes one calling test: concrete args + an expected property
  render   a #[cfg(test)] proof module naming the function
  run      IN-CRATE via `cargo test`, so it reaches private, deeply-integrated
           functions (turso), not only self-contained ones
  retain   iff the test FAILS - the uncovered branch is also a bug, and the failing
           test both closes the gap and documents the expectation

slop-audit proves the gap; it never writes into the user's test file. The module is
edited only for the duration of one run and restored byte-for-byte afterward. Retained
proofs land on the card's adoptable-proofs surface (results['coverage_proofs']).

Opt-in and CLI-only (it runs code): needs OPENAI_API_KEY, cargo, and cargo-llvm-cov.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from l1_analyzer import rust_facets, rust_trace

_INSTRUCTION = (
    "You are given ONE Rust function and one of its decision branches that no test ever reached. "
    "Infer the caller-facing behavior the branch SHOULD have from the function name, its signature, and "
    "the branch condition - do not just echo what the code visibly does. Propose one calling test that "
    "exercises exactly that branch. Return ONLY a JSON object with keys: "
    '"args" (a JSON array of Rust literal expressions, one per parameter, in order), '
    '"expected" (a Rust boolean expression over the identifier `result` and literals only - no calls, no `?`), '
    '"explanation" (one plain sentence stating the behavior you assert). '
    "The proof is kept only if execution contradicts your expectation, so state the behavior a correct "
    "implementation must have, not a prediction of the current output."
)

_PROOF_MOD = "l1_coverage_proof"


def model_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _gap_prompt(gap: dict) -> str:
    params = ", ".join(f"{p['name']}: {p['type']}" for p in gap["parameters"])
    return json.dumps({
        "function_source": gap["function_source"],
        "signature": f"fn {gap['function']}({params}) -> {gap['return_type']}",
        "uncovered_branch": f"the `{gap['kind']}` branch at line {gap['line']} is never exercised",
    })


def propose(gap: dict) -> dict | None:
    """Ask a model for one calling test for the located gap. Returns {args, expected,
    explanation} or None when no model is available or the reply is unusable."""
    if not model_available():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    try:
        response = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(
            model="gpt-5.6",
            input=[{"role": "developer", "content": _INSTRUCTION}, {"role": "user", "content": _gap_prompt(gap)}],
        )
        raw = re.sub(r"^```(?:json)?\n|```$", "", response.output_text.strip(), flags=re.MULTILINE)
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 - any failure yields no proposal, never a false claim
        return None
    args, expected = data.get("args"), data.get("expected")
    if not isinstance(args, list) or not isinstance(expected, str) or not expected.strip():
        return None
    return {"args": [str(a) for a in args], "expected": expected, "explanation": str(data.get("explanation", ""))}


def render_test(gap: dict, proposal: dict) -> str:
    """A #[cfg(test)] proof module appended to the target file. `use super::*` reaches the
    function in its own module scope, so private and crate-internal functions are callable."""
    call = f"{gap['function']}({', '.join(proposal['args'])})"
    message = json.dumps(proposal["explanation"] or f"uncovered {gap['kind']} branch of {gap['function']}")
    return (
        f"\n#[cfg(test)]\nmod {_PROOF_MOD} {{\n    use super::*;\n    #[test]\n    fn proof() {{\n"
        f"        let result = {call};\n        assert!({proposal['expected']}, {message});\n    }}\n}}\n"
    )


def _classify_run(output: str, returncode: int) -> str:
    """pass / fail / error from one in-crate `cargo test` of the proof. A failing test and a
    passing test both print a `test result:` line, so they are checked BEFORE compile errors:
    cargo prints its own `error: test failed` for a failed assertion, which is a fail, not a
    build error. A real build error has no `test result:` line, only rustc's `error[E...]` /
    `could not compile`."""
    if "test result: FAILED" in output or "1 failed" in output or "panicked" in output:
        return "fail"
    if "test result: ok" in output and "1 passed" in output:
        return "pass"
    if "could not compile" in output or re.search(r"error\[E\d+\]", output):
        return "error"
    return "error" if returncode != 0 else "pass"


def _run_in_crate(repo: Path, module_relpath: str, test_source: str, timeout_seconds: float) -> str:
    """Append the proof module to the file, run `cargo test`, and restore the file
    byte-for-byte. Returns pass / fail / error. The file is always restored."""
    cargo = rust_trace._cargo()
    if cargo is None:
        return "error"
    module = repo / module_relpath
    original = module.read_bytes()
    try:
        module.write_bytes(original + test_source.encode("utf8"))
        run = rust_trace._run_untrusted(
            [cargo, "test", "--quiet", f"{_PROOF_MOD}::proof"], cwd=repo, env={}, timeout_seconds=timeout_seconds)
    finally:
        module.write_bytes(original)
    if run.returncode == 124:
        return "error"
    return _classify_run((run.stdout or "") + (run.stderr or ""), run.returncode)


def prove_coverage(repo: Path, module_relpath: str, cap: int = 3, timeout_seconds: float = 600.0) -> dict:
    """Locate uncovered decision branches in one Rust module, ask a model for a calling
    test per gap, run each in-crate, and retain the ones that fail. Returns the
    coverage_proofs shape the card consumes. Every not-run path carries an explicit reason."""
    if not rust_trace._cargo():
        return {"retained": [], "attempted": 0, "detail": "needs a Rust toolchain (cargo) in PATH"}
    if not model_available():
        return {"retained": [], "attempted": 0, "detail": "needs OPENAI_API_KEY to generate coverage proofs"}

    cov = rust_trace.module_uncovered_lines(repo, module_relpath, timeout_seconds)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    module = repo / module_relpath
    functions = rust_facets.module_functions(module.read_text(errors="ignore"))
    gaps = rust_facets.uncovered_gaps(functions, cov["uncovered_lines"])[:cap]
    if not gaps:
        return {"retained": [], "attempted": 0, "detail": "no proof-ready uncovered branches located in this module"}

    retained: list[dict] = []
    attempted = 0
    for gap in gaps:
        proposal = propose(gap)
        if proposal is None:
            continue
        attempted += 1
        source = render_test(gap, proposal)
        if _run_in_crate(repo, module_relpath, source, timeout_seconds) == "fail":
            retained.append({
                "function": gap["function"], "language": "rust",
                "location": f"{module_relpath}:{gap['line']}",
                "explanation": proposal["explanation"],
                "test_source": source.strip(),
            })
    return {"retained": retained, "attempted": attempted,
            "detail": f"{len(retained)}/{attempted} generated coverage proofs were retained (genuinely failed)"}
