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

Opt-in and CLI-only (it runs code): needs ANTHROPIC_API_KEY, cargo, and cargo-llvm-cov. Repair
trades wall-clock for reach - each round is another in-crate compile - so it is bounded by a
round cap per gap and can be switched off (repair_rounds=0).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from l1_analyzer import budget, coverage_gates, rust_facets, rust_trace
from l1_analyzer import model_call as llm

# The retention buckets, in report order. Only `divergence` is a proven bug and retained;
# the rest name why a failing test is the tool's own noise, surfaced and never hidden.
_FAIL_BUCKETS = ("divergence", "wrong_channel", "invalid_fixture", "incidental_panic")
# `unreported` is its own bucket and deliberately not folded into `error`. A compile
# error is something the runner TOLD us; an unreported index is something it did not, so
# the test was generated and run and the analyzer then lost track of it. Counting one as
# the other made a run whose totals do not add up look like a run with noise in it.
_OUTCOMES = (*_FAIL_BUCKETS, "pass", "error", "unreported", "declined")
# The empty tally, named once so a reader and a test can ask what buckets exist.
EMPTY_OUTCOMES = {k: 0 for k in _OUTCOMES}

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

# Why the last model call produced nothing, for the sweep's report. A single cell rather
# than a return-value change because every caller of _call_model wants the parsed dict and
# only the sweep wants the reason; threading it through four signatures to reach one reader
# would be the wrong trade. It is written on every call, so it is never stale by more than
# one, and the sweep reads it once at the end.
LAST_REFUSAL = {"reason": "", "cause": ""}


def model_available() -> bool:
    """Re-exported from the one reader of the variable's NAME, so a rename cannot
    leave a second copy checking the old one."""
    return llm.model_available(llm.anthropic_sdk)


def host_cfg() -> frozenset[str]:
    """The host target's cfg set from `rustc --print cfg` - the I/O the cfg gate needs to
    prove a branch is host-dead. An empty set (no rustc) excludes nothing, never guesses."""
    cargo = rust_trace._cargo()
    if cargo is None:
        return frozenset()
    rustc = os.path.join(os.path.dirname(cargo), "rustc")
    probe = rust_trace._run_untrusted([rustc, "--print", "cfg"], cwd=Path.cwd(), env={}, timeout_seconds=30)
    return coverage_gates.host_cfg_atoms(probe.stdout or "") if probe.returncode == 0 else frozenset()


def _live_gaps(gaps: list[dict], host: frozenset[str]) -> list[dict]:
    """Drop gaps whose branch the host target never compiles: a proof there can only ever
    assert a premise about a platform the run is not on."""
    return [g for g in gaps if not coverage_gates.cfg_excluded(g.get("cfg"), host)]


def _call_model(instruction: str, payload: str) -> dict | None:
    """One structured model call. Returns the parsed JSON object, or None on any failure -
    an unusable reply never becomes a false proof."""
    # Through the one boundary. Only the TAIL differed between this and prove.generate:
    # that one wants the text with its fences stripped, this one wants it parsed as JSON,
    # and the preamble they shared had already drifted on the token limit.
    reply = llm.call(instruction, payload, 2048, llm.anthropic_sdk)
    if reply["text"] is None:
        # The reason travels on the module so a sweep can say WHICH refusal it hit. Folding
        # a missing SDK into "the model declined" is how the first live sweep reported a
        # model answering twice when no request had gone out.
        LAST_REFUSAL["reason"] = reply["reason"]
        LAST_REFUSAL["cause"] = reply["cause"]
        return None
    try:
        data = json.loads(re.sub(r"^```(?:json)?\n|```$", "", reply["text"].strip(), flags=re.MULTILINE))
    except Exception:  # noqa: BLE001 - a malformed reply yields no proposal, never a false claim
        LAST_REFUSAL["reason"] = llm.DECLINED
        LAST_REFUSAL["cause"] = ""
        return None
    if not isinstance(data, dict):
        LAST_REFUSAL["reason"] = llm.DECLINED
        return None
    LAST_REFUSAL["reason"] = llm.ANSWERED
    return data


def _signature(gap: dict) -> str:
    params = ", ".join(f"{p['name']}: {p['type']}" for p in gap["parameters"])
    return f"fn {gap['function']}({params}) -> {gap['return_type']}"


def _valid(data: dict | None, asserts: Callable[[str], bool]) -> dict | None:
    """A usable proposal, or nothing.

    `asserts` is the language's reachable-assertion rule, and refusing here rather than
    classifying after the run is the point: a body that evaluates no assertion cannot
    produce evidence either way, so running it spends a subprocess to learn nothing and
    then files the nothing under `pass`, whose report reads "branch correct".

    Required, not defaulted. Defaulting it to this module's rule was written first and was
    wrong in the way this repository refuses everywhere else: `_valid` is shared, so the
    Python caller that forgot the argument would have had its Python source checked by
    Rust's rule, silently and with a plausible answer."""
    if data is None or not isinstance(data.get("body"), str) or not data["body"].strip():
        return None
    body = data["body"].strip()
    if not asserts(body):
        return None
    return {"body": body, "explanation": str(data.get("explanation", ""))}


def propose(gap: dict) -> dict | None:
    """First calling test for the located gap: {body, explanation} or None."""
    payload = json.dumps({
        "function_source": gap["function_source"], "signature": _signature(gap),
        "uncovered_branch": f"the `{gap['kind']}` branch at line {gap['line']} is never exercised",
    })
    return _valid(_call_model(_PROPOSE_INSTRUCTION, payload), body_asserts)


def repair(gap: dict, test_source: str, compiler_error: str) -> dict | None:
    """Ask the model to fix a test that did not compile, given rustc's own diagnostic."""
    payload = json.dumps({
        "signature": _signature(gap), "function_source": gap["function_source"],
        "test_that_failed_to_compile": test_source, "rustc_error": compiler_error[-4000:],
    })
    return _valid(_call_model(_REPAIR_INSTRUCTION, payload), body_asserts)



def body_asserts(body: str) -> bool:
    """Whether this proof body will evaluate an assertion when it runs.

    The same hole as Python's, in the language the concurrency sweep runs on: a body
    defining an `fn` nobody calls compiles, the test passes, and cargo reports nothing
    wrong. A proof that measured nothing then published a clean bill for its branch.

    An assertion is a macro invocation named assert, assert_eq, assert_ne, or one of their
    debug_ forms, or a bare `panic!` guarded by a branch. Anything inside a nested
    `function_item` does not count, because nothing calls it."""
    from l1_analyzer import (
        rust_trace,  # noqa: F401 - keeps the tree-sitter import local
    )
    from l1_analyzer.indicators import _get_parser

    root = _get_parser("rust").parse(body.encode()).root_node

    def reachable(node) -> bool:
        for child in node.children:
            if child.type == "function_item":
                continue
            if child.type == "macro_invocation":
                name = child.child_by_field_name("macro")
                text = name.text.decode("utf8", errors="ignore") if name is not None and name.text else ""
                if text in _ASSERT_MACROS:
                    return True
            if reachable(child):
                return True
        return False

    return reachable(root)


_ASSERT_MACROS = frozenset({
    "assert", "assert_eq", "assert_ne",
    "debug_assert", "debug_assert_eq", "debug_assert_ne",
})


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
    # A construction that aborts (mem::zeroed UB) prints no `panicked`, but the crate did
    # compile and run: a non-zero exit after the test harness started is a failure, not a
    # build error, so it reaches the gates rather than being counted as did-not-compile.
    ran = "running " in output or "test result:" in output
    if returncode != 0:
        return "fail" if ran else "error"
    return "pass"


def _fail_bucket(output: str, proof_label: str, body: str, return_type: str | None) -> str:
    """A failing run's retention bucket, from the gates: parse this proof's panic, then
    classify it as a divergence (retained) or one of the noise classes."""
    panic = coverage_gates.parse_panic(output, proof_label)
    return coverage_gates.classify_failure(body, return_type, panic)


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


def _batch_status(batch: dict[int, str], index: int) -> str:
    """This test's verdict, or `unreported` when the classifier never mentioned it.

    Read by subscript with a NAMED miss rather than by `.get(i, "error")`, which is the
    open-input default Honest Code rule 14 refuses: it answered a question about a test
    the runner said nothing about with the answer written for a test that failed to
    compile.

    A named miss rather than a raise, because the caller is a counting loop that has to
    finish the batch. One silent test does not justify abandoning the other forty, and a
    bucket nobody can confuse with a compile error is what keeps the count readable."""

    # Ruff's SIM401 offers `batch.get(index, "unreported")`, which is the exact
    # shape this function exists to remove. The subscript and the explicit miss are the
    # point, and collapsing them back into a default puts the open input one keyword away
    # from returning whatever the next reader thinks is a reasonable answer.
    return batch[index] if index in batch else "unreported"  # noqa: SIM401


class CoverageProof(TypedDict):
    """One retained coverage proof, as the card renders it.

    Both producers, this one for Rust and python_coverage_prove for Python, built the
    entry by hand from five keys. They agreed, and nothing held them to it."""
    function: str
    language: str
    location: str
    explanation: str
    test_source: str


def _retained_entry(module_relpath: str, gap: dict, proposal: dict, source: str) -> CoverageProof:
    return {
        "function": gap["function"], "language": "rust",
        "location": f"{module_relpath}:{gap['line']}",
        "explanation": proposal["explanation"], "test_source": source.strip(),
    }


def _refine_incidental(repo: Path, module_relpath: str, gap: dict, body: str, timeout_seconds: float) -> str:
    """The permutation check on an incidental panic: rebuild the fixture with a valid,
    64-aligned scalar and re-run. If the panic clears, the original scalar - not the
    function - caused it, so this is an invalid fixture. If it persists, it is a real panic
    on valid construction, kept for review. Deterministic, one extra compile, no model."""
    permuted = coverage_gates.permute_scalar_construction(body)
    if permuted is None:
        return "incidental_panic"
    status, output = _run_in_crate(repo, module_relpath, render_module(permuted), timeout_seconds)
    if status != "fail":
        return "invalid_fixture"   # the panic is gone under a valid scalar
    return "invalid_fixture" if _fail_bucket(output, "proof", permuted, gap["return_type"]) != "incidental_panic" else "incidental_panic"


# THE TWO PROVE LOOPS ARE NOT MERGED, and that was measured rather than assumed.
#
# L1.13 flags this module and python_coverage_prove as the largest cross-file clone class
# in the package, 56 overlapping windows. Six things they genuinely shared have already
# moved out: `_valid`, `_call_model`, `ceiling_detail`, `sweep_detail`, `SweepProgress` and
# `budget.allowance`. What is left is the loop structure, and it is less alike than the
# clone count suggests.
#
# Compared statement for statement with every string blanked, on 2026-08-19: `_prove_one`
# is 21 lines here against 18 there with 8 identical, and `_prove_module` is 26 against 11
# with 4. The Rust side batches every gap into one crate, compiles once, and falls back to
# proving each gap in isolation when the batch does not build; the Python side runs each
# proof on its own because pytest has no equivalent of a single crate compile. That is a
# structural difference, not a vocabulary one.
#
# Merging them would take a callback per divergence, which is the machinery the determinism
# tallies were left unmerged to avoid. Two implementations that differ in what they DO are
# not a duplication to remove; the shared RULES were, and those are gone.

def _prove_one(repo: Path, module_relpath: str, gap: dict, repair_rounds: int, timeout_seconds: float,
               propose_fn: Callable[..., dict | None], repair_fn: Callable[..., dict | None],
               run_fn: Callable[..., tuple[str, str]],
               refine_fn: Callable[..., str]) -> tuple[str, dict | None, str]:
    """Propose -> run -> (repair -> run)* -> gate for one gap. Returns (bucket, proposal,
    test_source): a fail is resolved to one of _FAIL_BUCKETS (only `divergence` is retained);
    a clean run is `pass`; `error` is did-not-compile even after repair; `declined` is no reply, and it is COUNTED: a model call that produced nothing still cost money.

    The collaborators are parameters, as in `prove.prove` and the Python loop. They were
    module-level lookups, so testing this orchestration meant patching the module's own
    globals, and those tests went in the 2026-08-17 sweep for exactly that reason.
    Required rather than defaulted: a default puts a real cargo invocation one forgotten
    argument away from a test."""
    proposal = propose_fn(gap)
    if proposal is None:
        return "declined", None, ""
    source = render_module(proposal["body"])
    status, output = run_fn(repo, module_relpath, source, timeout_seconds)
    rounds = 0
    while status == "error" and rounds < repair_rounds:
        rounds += 1
        fixed = repair_fn(gap, source, output)
        if fixed is None:
            break
        proposal = fixed
        source = render_module(fixed["body"])
        status, output = run_fn(repo, module_relpath, source, timeout_seconds)
    if status != "fail":
        return status, proposal, source
    bucket = _fail_bucket(output, "proof", proposal["body"], gap["return_type"])
    if bucket == "incidental_panic":
        # The fifth collaborator, and it re-runs the crate. Every fail output routes through
        # here, so leaving it a module-level lookup would have kept the gating path
        # untestable however many of the other four were injected.
        bucket = refine_fn(repo, module_relpath, gap, proposal["body"], timeout_seconds)
    return bucket, proposal, source


def _prove_module(repo: Path, module_relpath: str, gaps: list[dict], repair_rounds: int,
                  timeout_seconds: float, propose_fn: Callable[..., dict | None],
                  repair_fn: Callable[..., dict | None], batch_run_fn: Callable[..., tuple[int, str]],
                  run_fn: Callable[..., tuple[str, str]],
                  refine_fn: Callable[..., str]) -> tuple[list[dict], dict]:
    """Prove all of one module's gaps. Fast path: batch every proposal into one compile and
    run once, then gate each failing test. If the batch does not compile (one bad test
    poisons it), fall back to per-gap with compiler-feedback repair. Returns (retained,
    outcomes). Only a `divergence` is retained; the noise buckets are counted, never hidden."""
    outcomes = {k: 0 for k in _OUTCOMES}
    ready = [(g, p) for g in gaps for p in (propose_fn(g),) if p is not None]
    if not ready:
        return [], outcomes
    rc, output = batch_run_fn(repo, module_relpath, render_batch([p["body"] for _g, p in ready]),
                              _PROOF_MOD, timeout_seconds)
    batch = {} if rc == 124 else _classify_batch(output)
    if batch:  # the module compiled: read each test's verdict, then gate the failures.
        retained = []
        for i, (gap, proposal) in enumerate(ready):
            status = _batch_status(batch, i)
            if status != "fail":
                outcomes[status] += 1
                continue
            bucket = _fail_bucket(output, f"proof_{i}", proposal["body"], gap["return_type"])
            outcomes[bucket] += 1
            if bucket == "divergence":
                retained.append(_retained_entry(module_relpath, gap, proposal, render_module(proposal["body"])))
        return retained, outcomes
    # The batch did not compile: isolate, repair, and gate each gap individually.
    retained = []
    for gap in gaps:
        bucket, proposal, source = _prove_one(repo, module_relpath, gap, repair_rounds,
                                              timeout_seconds, propose_fn, repair_fn, run_fn,
                                              refine_fn)
        outcomes[bucket] += 1
        if bucket == "divergence":
            retained.append(_retained_entry(module_relpath, gap, proposal, source))
    return retained, outcomes


def ceiling_detail(attempted: int, located: int, ceiling: int) -> str:
    """What a truncated sweep owes its reader, or nothing when it was not truncated.

    A result reading "attempted 5, retained 1" with no further word reads as a codebase
    with five uncovered branches, when it may have had five hundred. That is the
    unmeasured-read-as-clean shape this instrument exists to refuse, wearing a budget for a
    disguise. So a sweep that stopped at its ceiling names both numbers.

    It speaks only when the ceiling bit. Saying so on every sweep would train a reader to
    skip the sentence on the one sweep where it matters."""
    if located <= attempted or ceiling <= 0:
        return ""
    return (f" STOPPED AT THE CEILING: {attempted} of {located} located gaps were attempted "
            f"(ceiling {ceiling}). The rest were not measured and are not counted clean.")


# A sweep reports its progress through this, once per module, before that module is
# proven. Typed, and it was `progress=None` untyped: a public parameter naming no shape at
# all, so the three arguments it is called with lived only in a docstring and a caller that
# read them differently would fail inside the sweep rather than at the call.
SweepProgress = Callable[[str, int, int], None]


# honest-code-allow: L1.21.13 - the writer and both readers are one unit. `_call_model` writes LAST_REFUSAL and it is the single model boundary BOTH sweeps import, so there is no second source and no cross-module surprise. Threading the reason back would change the injected propose_fn signature, its repair counterpart and every test fake, to reach one reader at the end of one sweep. The sweeps are sequential, so the value is never stale by more than one call.
def prove_coverage_repo(repo: Path, cap_per_module: int, repair_rounds: int,
                        timeout_seconds: float, progress: SweepProgress | None,
                        max_attempts: int) -> dict:
    """Sweep the WHOLE crate: one coverage build, then every module with uncovered branches is
    proven (batched, with per-gap repair fallback). Retained proofs are aggregated across the
    codebase. `progress(relpath, n_gaps, running_retained)` is called before each module."""
    # Read before anything else, so a ceiling of zero costs nothing: no toolchain probe, no
    # coverage build, no key, no network. A budget of nothing must be free to honour.
    if max_attempts <= 0:
        return {"retained": [], "attempted": 0, "outcomes": {k: 0 for k in _OUTCOMES}, "modules": 0,
                "detail": f"attempted nothing: the ceiling is {max_attempts}"}
    if not rust_trace._cargo():
        return {"retained": [], "attempted": 0, "detail": "needs a Rust toolchain (cargo) in PATH"}
    if not model_available():
        return {"retained": [], "attempted": 0,
                "detail": f"no coverage proofs generated: {llm.WHY[llm.unavailable_reason(llm.anthropic_sdk)]}"}
    cov = rust_trace.repo_uncovered_lines(repo, timeout_seconds)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    host = host_cfg()
    retained: list[dict] = []
    outcomes = {k: 0 for k in _OUTCOMES}
    modules = 0
    located = 0            # every gap the sweep found, whether or not the ceiling let it try
    attempted_gaps = 0     # every gap the sweep handed to a model
    for relpath, lines in sorted(cov["files"].items()):
        if not relpath.endswith(".rs"):
            continue
        try:
            functions = rust_facets.module_functions((repo / relpath).read_text(errors="ignore"))
        except OSError:
            continue
        module_gaps = _live_gaps(rust_facets.uncovered_gaps(functions, lines), host)[:cap_per_module]
        located += len(module_gaps)
        # The repo-wide ceiling, applied after `located` counts the whole gap so the report
        # can say what was left. Truncating before counting would hide the size of the miss.
        # One rule, in `budget`: the module's own cap or what the run has left,
        # whichever is smaller. The cap is already applied above, so what this
        # adds is the run ceiling.
        gaps = module_gaps[:budget.allowance(len(module_gaps), max_attempts, attempted_gaps)]
        attempted_gaps += len(gaps)
        if not gaps:
            continue
        modules += 1
        if progress:
            progress(relpath, len(gaps), len(retained))
        # The real four, named at the one place that knows which they are.
        module_retained, module_outcomes = _prove_module(
            repo, relpath, gaps, repair_rounds, timeout_seconds,
            propose, repair, _append_and_run, _run_in_crate, _refine_incidental)
        retained.extend(module_retained)
        for k in outcomes:
            outcomes[k] += module_outcomes[k]
    # `attempted` is every gap handed to a model, declines included: that is the unit that
    # cost money, and a budget that did not count the declines could not be reconciled.
    attempted = sum(outcomes.values())
    detail = sweep_detail(len(retained), modules, located, outcomes, "cargo",
                          LAST_REFUSAL["reason"], LAST_REFUSAL["cause"])
    if attempted - outcomes["declined"]:
        detail += _outcome_detail(outcomes)
    detail += ceiling_detail(attempted_gaps, located, max_attempts)
    return {"retained": retained, "attempted": attempted, "outcomes": outcomes, "modules": modules, "detail": detail}


def sweep_detail(retained: int, modules: int, located: int, outcomes: dict, provenance: str,
                 reason: str, cause: str) -> str:
    """What a finished sweep says, in the three cases it can be in.

    The middle case was missing. A sweep that located gaps, handed some to a model and got
    nothing usable back fell through to the sentence it prints when it found nothing at
    all. The first live run, on 2026-08-19, printed "no proof-ready uncovered branches
    located across 1 modules" beside "2 of 154 located gaps were attempted": both halves of
    one report contradicting each other. A measure that located 154 uncovered branches and
    told a reader there were none is publishing a claim it never earned."""
    ran = sum(v for k, v in outcomes.items() if k != "declined")
    declined = outcomes.get("declined", 0)
    if not located:
        return f"no proof-ready uncovered branches located across {modules} modules"
    if not ran:
        # Which refusal, not just that there was one. "The model returned nothing usable"
        # over a run that never reached a model is the claim this function was built to stop.
        # Only the decline carries a count: it is the one reason where HOW MANY the model
        # was asked is a fact about the model. A missing SDK declined nothing; it was never
        # asked, and printing a number beside it would invent an interaction.
        why = (f"the model replied with nothing usable for {declined} of them"
               if reason in (llm.DECLINED, "") else llm.WHY[reason])
        if cause:
            why += f" [{cause}]"
        return (f"{located} uncovered branches located across {modules} modules and none was proven: "
                f"{why} (ran under {provenance})")
    # The declines are named here too, not only when nothing ran. A sweep of 20 attempts
    # printed "Of 15 generated tests" and said nothing about the other five, so a reader
    # reconciling the run against its bill was five short with nothing to explain the gap.
    # It speaks only when there were any: a zero in every report is noise a reader learns to
    # skip, which is how the one report that mattered would be missed.
    aside = (f"The model declined {declined} further gap(s), which cost the same and produced "
             f"no test. " if declined else "")
    return (f"{retained} coverage proofs retained across {modules} modules with uncovered branches "
            f"(ran under {provenance}). {aside}")


def _outcome_detail(outcomes: dict) -> str:
    """The honest breakdown: what each generated test became. Only `divergence` is a proven
    bug; the noise buckets are named so a zero-retained result still says what happened."""
    return (f"Of {sum(outcomes.values())} generated tests run in-crate: {outcomes['divergence']} "
            f"retained as behavioural divergences (bug proven), {outcomes['pass']} passed (branch correct), "
            f"{outcomes['wrong_channel']} inspected the wrong output channel, "
            f"{outcomes['invalid_fixture']} were invalid fixtures (construction the code rejects), "
            f"{outcomes['incidental_panic']} panicked outside the assertion (kept for review), "
            f"{outcomes['error']} did not compile.")


def prove_coverage(repo: Path, module_relpath: str, cap: int, timeout_seconds: float,
                   repair_rounds: int) -> dict:
    """Locate uncovered decision branches in one Rust module, prove each (propose -> run,
    then compiler-feedback repair up to repair_rounds), and retain the ones that fail.
    Returns the coverage_proofs shape the card consumes. Every not-run path carries a reason."""
    if not rust_trace._cargo():
        return {"retained": [], "attempted": 0, "detail": "needs a Rust toolchain (cargo) in PATH"}
    if not model_available():
        return {"retained": [], "attempted": 0,
                "detail": f"no coverage proofs generated: {llm.WHY[llm.unavailable_reason(llm.anthropic_sdk)]}"}

    cov = rust_trace.module_uncovered_lines(repo, module_relpath, timeout_seconds)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    module = repo / module_relpath
    functions = rust_facets.module_functions(module.read_text(errors="ignore"))
    gaps = _live_gaps(rust_facets.uncovered_gaps(functions, cov["uncovered_lines"]), host_cfg())[:cap]
    if not gaps:
        return {"retained": [], "attempted": 0, "detail": "no proof-ready uncovered branches located in this module"}

    retained: list[dict] = []
    outcomes = {k: 0 for k in _OUTCOMES}
    for gap in gaps:
        bucket, proposal, source = _prove_one(repo, module_relpath, gap, repair_rounds, timeout_seconds)
        outcomes[bucket] += 1
        if bucket == "divergence":
            retained.append({
                "function": gap["function"], "language": "rust",
                "location": f"{module_relpath}:{gap['line']}",
                "explanation": proposal["explanation"],
                "test_source": source.strip(),
            })
    attempted = sum(outcomes.values())
    # The breakdown is the honest part: 0 retained means nothing without it. Each generated
    # test lands in a named bucket; only a behavioural divergence is a proven bug and retained.
    detail = (f"{len(retained)}/{attempted} coverage proofs retained. " + _outcome_detail(outcomes)
              ) if attempted else "no proof-ready uncovered branches located"
    return {"retained": retained, "attempted": attempted, "outcomes": outcomes,
            "repair_rounds": repair_rounds, "detail": detail}
