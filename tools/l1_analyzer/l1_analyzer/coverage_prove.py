"""Coverage-gap prove loop - slop-audit's own, no Umbra at runtime.

The same discipline as the concurrency prove loop and as Umbra (the reference, not a
dependency): structure is deterministic, the model only fills an already-located gap, and
the EXECUTION gate decides. The gap is an uncovered decision branch:

  locate   rust_facets over the module + rust_trace's per-module uncovered lines
  propose  a model writes one calling test: build the inputs, call, assert a property
  render   a #[cfg(test)] proof module naming the function
  run      IN-CRATE via `cargo test`, so it reaches private, deeply-integrated
           functions (turso), not only self-contained ones
  repair   (optional, on by default) when the test does not compile, feed rustc's own
           error back to the model and let it rewrite the arrange step - a generic
           compiler-feedback loop that constructs the real argument values a bare literal
           cannot, without any per-type or per-codebase knowledge. The compiler is the
           universal oracle; nothing here knows anything about a particular crate.
  retain   iff the test FAILS - the uncovered branch is also a bug, and the failing test
           both closes the gap and documents the expectation

slop-audit proves the gap; it never writes into the user's test file. The module is edited
only for the duration of one run and restored byte-for-byte afterward. Retained proofs land
on the card's adoptable-proofs surface (results['coverage_proofs']).

Opt-in and CLI-only (it runs code): needs OPENAI_API_KEY, cargo, and cargo-llvm-cov. Repair
trades wall-clock for reach - each round is another in-crate compile - so it is bounded by a
round cap per gap and can be switched off (repair_rounds=0).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from l1_analyzer import rust_facets, rust_trace

_PROPOSE_INSTRUCTION = (
    "You are given ONE Rust function and one of its decision branches that no test ever reached. "
    "Infer the caller-facing behavior the branch SHOULD have from the function name, its signature, and "
    "the branch condition - do not just echo what the code visibly does. Write the BODY of a Rust test "
    "that exercises exactly that branch: construct the argument values (bindings are fine), call the "
    "function into a binding named `result`, then `assert!(<property>, <message>)` on `result`. The proof "
    "is kept only if execution contradicts your assertion, so assert the behavior a correct implementation "
    "MUST have, not a prediction of the current output. `use super::*;` is already in scope, so the "
    "function and its module's types are directly nameable. Return ONLY a JSON object with keys: "
    '"body" (the Rust statements, no fn/mod wrapper) and '
    '"explanation" (one plain sentence stating the behavior you assert).'
)

_REPAIR_INSTRUCTION = (
    "The Rust test below does not compile. Here is the exact rustc error. Rewrite the test BODY so it "
    "compiles and still asserts the same intended behavior. Fix the arrange step: build the real argument "
    "values the signature requires (call constructors, `::new`, `Default::default()`, enum variants - "
    "anything in scope via `use super::*;`), not bare literals of the wrong type. Keep the final "
    "`let result = ...;` and the `assert!` on `result`. Return ONLY a JSON object with keys "
    '"body" (the corrected Rust statements, no fn/mod wrapper) and "explanation".'
)

_PROOF_MOD = "l1_coverage_proof"


def model_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _call_model(instruction: str, payload: str) -> dict | None:
    """One structured model call. Returns the parsed JSON object, or None on any failure -
    an unusable reply never becomes a false proof."""
    if not model_available():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    try:
        response = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(
            model="gpt-5.6",
            input=[{"role": "developer", "content": instruction}, {"role": "user", "content": payload}],
        )
        raw = re.sub(r"^```(?:json)?\n|```$", "", response.output_text.strip(), flags=re.MULTILINE)
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 - any failure yields no proposal, never a false claim
        return None
    return data if isinstance(data, dict) else None


def _signature(gap: dict) -> str:
    params = ", ".join(f"{p['name']}: {p['type']}" for p in gap["parameters"])
    return f"fn {gap['function']}({params}) -> {gap['return_type']}"


def _valid(data: dict | None) -> dict | None:
    if data is None or not isinstance(data.get("body"), str) or not data["body"].strip():
        return None
    return {"body": data["body"].strip(), "explanation": str(data.get("explanation", ""))}


def propose(gap: dict) -> dict | None:
    """First calling test for the located gap: {body, explanation} or None."""
    payload = json.dumps({
        "function_source": gap["function_source"], "signature": _signature(gap),
        "uncovered_branch": f"the `{gap['kind']}` branch at line {gap['line']} is never exercised",
    })
    return _valid(_call_model(_PROPOSE_INSTRUCTION, payload))


def repair(gap: dict, test_source: str, compiler_error: str) -> dict | None:
    """Ask the model to fix a test that did not compile, given rustc's own diagnostic."""
    payload = json.dumps({
        "signature": _signature(gap), "function_source": gap["function_source"],
        "test_that_failed_to_compile": test_source, "rustc_error": compiler_error[-4000:],
    })
    return _valid(_call_model(_REPAIR_INSTRUCTION, payload))


def render_module(body: str) -> str:
    """Wrap a test body in a #[cfg(test)] proof module. `use super::*;` reaches the function
    in its own module scope, so private and crate-internal functions are callable. The body
    carries its own assert! (with the explanation as the panic message)."""
    return (
        f"\n#[cfg(test)]\nmod {_PROOF_MOD} {{\n    use super::*;\n    #[test]\n    fn proof() {{\n"
        f"{body}\n    }}\n}}\n"
    )


def _classify_run(output: str, returncode: int) -> str:
    """pass / fail / error from one in-crate `cargo test`. A failing test and a passing test
    both print a `test result:` line, so they are checked BEFORE compile errors: cargo prints
    its own `error: test failed` for a failed assertion, which is a fail, not a build error."""
    if "test result: FAILED" in output or "1 failed" in output or "panicked" in output:
        return "fail"
    if "test result: ok" in output and "1 passed" in output:
        return "pass"
    if "could not compile" in output or re.search(r"error\[E\d+\]", output):
        return "error"
    return "error" if returncode != 0 else "pass"


def _append_and_run(repo: Path, module_relpath: str, test_source: str, test_filter: str, timeout_seconds: float) -> tuple[int, str]:
    """Append a proof module to the file, run `cargo test <filter>`, and restore the file
    byte-for-byte. Returns (returncode, combined output). The file is always restored."""
    cargo = rust_trace._cargo()
    if cargo is None:
        return 1, "no cargo"
    module = repo / module_relpath
    original = module.read_bytes()
    try:
        module.write_bytes(original + test_source.encode("utf8"))
        run = rust_trace._run_untrusted(
            [cargo, "test", "--quiet", test_filter], cwd=repo, env={}, timeout_seconds=timeout_seconds)
    finally:
        module.write_bytes(original)
    return run.returncode, (run.stdout or "") + (run.stderr or "")


def _run_in_crate(repo: Path, module_relpath: str, test_source: str, timeout_seconds: float) -> tuple[str, str]:
    """One proof, run in-crate. Returns (pass|fail|error, output)."""
    rc, output = _append_and_run(repo, module_relpath, test_source, f"{_PROOF_MOD}::proof", timeout_seconds)
    if rc == 124:
        return "error", output + "\n(timed out)"
    return _classify_run(output, rc), output


def render_batch(bodies: list[str]) -> str:
    """All of a module's proofs in one #[cfg(test)] module - N tests, ONE compile. This is
    what makes a whole-codebase sweep cost ~one build per module instead of one per gap."""
    tests = "\n".join(f"    #[test]\n    fn proof_{i}() {{\n{body}\n    }}" for i, body in enumerate(bodies))
    return f"\n#[cfg(test)]\nmod {_PROOF_MOD} {{\n    use super::*;\n{tests}\n}}\n"


_BATCH_LINE = re.compile(r"proof_(\d+) \.\.\. (ok|FAILED)")


def _classify_batch(output: str) -> dict[int, str]:
    """index -> pass|fail from a batched run. Empty when the batch did not compile (no test
    lines), which signals the caller to fall back to per-gap repair."""
    return {int(m.group(1)): ("fail" if m.group(2) == "FAILED" else "pass") for m in _BATCH_LINE.finditer(output)}


def _retained_entry(module_relpath: str, gap: dict, proposal: dict, source: str) -> dict:
    return {
        "function": gap["function"], "language": "rust",
        "location": f"{module_relpath}:{gap['line']}",
        "explanation": proposal["explanation"], "test_source": source.strip(),
    }


def _prove_one(repo: Path, module_relpath: str, gap: dict, repair_rounds: int, timeout_seconds: float) -> tuple[str, dict | None, str]:
    """Propose -> run -> (repair -> run)* for one gap. Returns (status, proposal, test_source)
    where status is fail (retained), pass (branch correct), error (did not compile even after
    repair), or skipped (no model reply)."""
    proposal = propose(gap)
    if proposal is None:
        return "skipped", None, ""
    source = render_module(proposal["body"])
    status, output = _run_in_crate(repo, module_relpath, source, timeout_seconds)
    rounds = 0
    while status == "error" and rounds < repair_rounds:
        rounds += 1
        fixed = repair(gap, source, output)
        if fixed is None:
            break
        proposal = fixed
        source = render_module(fixed["body"])
        status, output = _run_in_crate(repo, module_relpath, source, timeout_seconds)
    return status, proposal, source


def _prove_module(repo: Path, module_relpath: str, gaps: list[dict], repair_rounds: int,
                  timeout_seconds: float) -> tuple[list[dict], dict]:
    """Prove all of one module's gaps. Fast path: batch every proposal into one compile and
    run once. If the batch does not compile (one bad test poisons it), fall back to per-gap
    with compiler-feedback repair. Returns (retained, outcomes)."""
    outcomes = {"fail": 0, "pass": 0, "error": 0}
    ready = [(g, p) for g in gaps for p in (propose(g),) if p is not None]
    if not ready:
        return [], outcomes
    rc, output = _append_and_run(repo, module_relpath, render_batch([p["body"] for _g, p in ready]),
                                 _PROOF_MOD, timeout_seconds)
    batch = {} if rc == 124 else _classify_batch(output)
    if batch:  # the module compiled: read each test's verdict, no repair needed
        retained = []
        for i, (gap, proposal) in enumerate(ready):
            status = batch.get(i, "error")
            outcomes[status] += 1
            if status == "fail":
                retained.append(_retained_entry(module_relpath, gap, proposal, render_module(proposal["body"])))
        return retained, outcomes
    # The batch did not compile: isolate and repair each gap individually.
    retained = []
    for gap in gaps:
        status, proposal, source = _prove_one(repo, module_relpath, gap, repair_rounds, timeout_seconds)
        if status == "skipped":
            continue
        outcomes[status] += 1
        if status == "fail":
            retained.append(_retained_entry(module_relpath, gap, proposal, source))
    return retained, outcomes


def prove_coverage_repo(repo: Path, cap_per_module: int = 5, repair_rounds: int = 3,
                        timeout_seconds: float = 600.0, progress=None) -> dict:
    """Sweep the WHOLE crate: one coverage build, then every module with uncovered branches is
    proven (batched, with per-gap repair fallback). Retained proofs are aggregated across the
    codebase. `progress(relpath, n_gaps, running_retained)` is called before each module."""
    if not rust_trace._cargo():
        return {"retained": [], "attempted": 0, "detail": "needs a Rust toolchain (cargo) in PATH"}
    if not model_available():
        return {"retained": [], "attempted": 0, "detail": "needs OPENAI_API_KEY to generate coverage proofs"}
    cov = rust_trace.repo_uncovered_lines(repo, timeout_seconds)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    retained: list[dict] = []
    outcomes = {"fail": 0, "pass": 0, "error": 0}
    modules = 0
    for relpath, lines in sorted(cov["files"].items()):
        if not relpath.endswith(".rs"):
            continue
        try:
            functions = rust_facets.module_functions((repo / relpath).read_text(errors="ignore"))
        except OSError:
            continue
        gaps = rust_facets.uncovered_gaps(functions, lines)[:cap_per_module]
        if not gaps:
            continue
        modules += 1
        if progress:
            progress(relpath, len(gaps), len(retained))
        module_retained, module_outcomes = _prove_module(repo, relpath, gaps, repair_rounds, timeout_seconds)
        retained.extend(module_retained)
        for k in outcomes:
            outcomes[k] += module_outcomes[k]
    attempted = sum(outcomes.values())
    detail = (f"{len(retained)} coverage proofs retained across {modules} modules with uncovered branches. "
              f"Of {attempted} generated tests run in-crate: {outcomes['fail']} failed (bug proven), "
              f"{outcomes['pass']} passed (branch correct), {outcomes['error']} did not compile."
              ) if attempted else f"no proof-ready uncovered branches located across {modules} modules"
    return {"retained": retained, "attempted": attempted, "outcomes": outcomes, "modules": modules, "detail": detail}


def prove_coverage(repo: Path, module_relpath: str, cap: int = 3, timeout_seconds: float = 600.0,
                   repair_rounds: int = 3) -> dict:
    """Locate uncovered decision branches in one Rust module, prove each (propose -> run,
    then compiler-feedback repair up to repair_rounds), and retain the ones that fail.
    Returns the coverage_proofs shape the card consumes. Every not-run path carries a reason."""
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
    outcomes = {"fail": 0, "pass": 0, "error": 0}
    for gap in gaps:
        status, proposal, source = _prove_one(repo, module_relpath, gap, repair_rounds, timeout_seconds)
        if status == "skipped":
            continue
        outcomes[status] += 1
        if status == "fail":
            retained.append({
                "function": gap["function"], "language": "rust",
                "location": f"{module_relpath}:{gap['line']}",
                "explanation": proposal["explanation"],
                "test_source": source.strip(),
            })
    attempted = sum(outcomes.values())
    # The breakdown is the honest part: 0 retained means nothing without it. fail = a bug
    # proven (retained); pass = the uncovered branch is correct; error = the generated test
    # would not compile even after repair (located but not provable this way), never hidden.
    detail = (f"{len(retained)}/{attempted} coverage proofs retained. Of {attempted} generated tests run "
              f"in-crate: {outcomes['fail']} failed (bug proven), {outcomes['pass']} passed (branch correct), "
              f"{outcomes['error']} did not compile"
              f"{f' even after {repair_rounds} repair round(s)' if repair_rounds else ''}."
              ) if attempted else "no proof-ready uncovered branches located"
    return {"retained": retained, "attempted": attempted, "outcomes": outcomes,
            "repair_rounds": repair_rounds, "detail": detail}
