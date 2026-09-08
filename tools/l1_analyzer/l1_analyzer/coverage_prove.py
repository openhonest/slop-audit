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
import shutil
import tempfile
from collections.abc import Callable
from concurrent import futures
from pathlib import Path
from typing import TypedDict

from l1_analyzer import budget, coverage_gates, prove_gap, rust_facets, rust_trace
from l1_analyzer import model_call as llm
from l1_analyzer.boundary import boundary
from l1_analyzer.coverage_words import (
    PROPOSE_INSTRUCTION,
    PROPOSE_MANY_INSTRUCTION,
    REPAIR_INSTRUCTION,
)
from l1_analyzer.rust_facets import CoverageGap
from l1_analyzer.sweep_pool import (
    checkouts_for,
    pool_detail,
    share_out,
    workers_for,
)
from l1_analyzer.sweep_pool import discard_checkouts as _discard_checkouts

# The retention buckets, in report order. Only `divergence` is a proven bug and retained;
# the rest name why a failing test is the tool's own noise, surfaced and never hidden.
_FAIL_BUCKETS = ("divergence", "wrong_channel", "invalid_fixture", "incidental_panic")
# `unreported` is its own bucket and deliberately not folded into `error`. A compile
# error is something the runner TOLD us; an unreported index is something it did not, so
# the test was generated and run and the analyzer then lost track of it. Counting one as
# the other made a run whose totals do not add up look like a run with noise in it.
# `unrun` is its own bucket for the same reason `unreported` is. A compile error is
# something the toolchain TOLD us, rustc printing error[E0308] or cargo saying it could not
# compile; a run that printed neither and no test line either never reached a compiler at
# all. That is a fact about this tool's ability to run rather than about the generated test,
# and the two send a reader to different places. A sweep on 2026-09-07 filed 181 of them as
# compile errors while sampling found zero cargo and zero rustc processes across the whole
# module loop.
_OUTCOMES = (*_FAIL_BUCKETS, "pass", "error", "unrun", "unreported", "declined")
# The empty tally, named once so a reader and a test can ask what buckets exist.
EMPTY_OUTCOMES = {k: 0 for k in _OUTCOMES}

_PROOF_MOD = "l1_coverage_proof"

# Why the last model call produced nothing, for the sweep's report. A single cell rather
# than a return-value change because every caller of _call_model wants the parsed dict and
# only the sweep wants the reason; threading it through four signatures to reach one reader
# would be the wrong trade. It is written on every call, so it is never stale by more than
# one, and the sweep reads it once at the end.
LAST_REFUSAL = {"reason": "", "cause": ""}


# What this module passes around. A gap is one uncovered decision the sweep found; an answer
# is what a model handed back for it, or nothing. Both were written `dict`, which means
# dict[Any, Any] and is the least precise mapping the language has.
#
# The key is pinned and the value left open, because a gap carries whatever the locator put
# in it and an answer carries whatever the model returned. `dict[str, object]` says that
# honestly; `dict` said nothing at all and scored better for saying it.
# A gap already had a name. `rust_facets.CoverageGap` has described one since before this
# module was written, and a bulk rename yesterday invented a second name for the same thing:
# the rename matched a pattern rather than a meaning, and nothing could see two names for one
# shape until a type checker ran. This module reads the one that exists.


class Sweep(TypedDict, total=False):
    """What a whole-repository sweep hands back: the proofs it kept, what it tried, and why
    it stopped where it did.

    Its own record. A bulk rename put the name of a model's answer on this, on the tally
    below, and on a gap, because the rename matched a spelling rather than a meaning. Nothing
    could see that a summary and an answer were being called one thing until a type checker
    ran, and by then three shapes wore two names.

    `total=False` because a sweep that refuses early carries no tally and no module count:
    there is nothing to count. The refusal always carries its own sentence."""

    retained: list[CoverageProof]
    attempted: int
    outcomes: Outcomes
    modules: int
    repair_rounds: int
    detail: str


# What each generated test became, one count per bucket, keyed by the names in `_OUTCOMES`.
#
# NOT a written-out record. I wrote one and it was a hand copy of that tuple, missing four
# of its buckets on the day I wrote it, which is the drift a second copy always produces.
# The tuple is where the buckets are declared and the tally is built from it by name, so a
# mapping of those names to counts is what this actually is.
Outcomes = dict[str, int]


class Answer(TypedDict, total=False):
    """What a model returned for one gap, or as much of it as arrived.

    Not total, because the model may answer partly or not at all, and a missing field is the
    honest record of that. Reading one as a string is what every caller did, and nothing
    checked it until now."""

    function: str
    explanation: str
    test_source: str
    module: str
    # A refinement answers with a narrowed body, and the caller reads it back. Added by
    # reading what the code does rather than by guessing which record a key belongs to,
    # which is how the first split of these two put `body` on the wrong one.
    body: str



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


def _live_gaps(gaps: list[CoverageGap], host: frozenset[str]) -> list[CoverageGap]:
    """Drop gaps whose branch the host target never compiles: a proof there can only ever
    assert a premise about a platform the run is not on."""
    return [g for g in gaps if not coverage_gates.cfg_excluded(g.get("cfg"), host)]


def read_json_object(text: str) -> dict[str, object] | None:
    """The JSON object a reply carries, or nothing when it carries none.

    Models wrap JSON in a markdown fence routinely, so the fence comes off before the reader
    sees it. This existed for the single-gap path and NOT for the packed one, which handed
    the fenced text straight to the JSON reader. Every answer in every pack was refused, and
    nothing recorded it, because a refusal is written down when the model says nothing and
    this model said 300 KB. Eighty-seven minutes of asking produced a run that reported the
    model had replied with nothing usable for zero gaps.

    The record is written here either way. A reply nobody can read is a fact about the reply
    rather than about the model's willingness, and a sweep that cannot tell them apart
    reports a refusal that did not happen."""
    try:
        data = json.loads(re.sub(r"^```(?:json)?\n|```$", "", text.strip(), flags=re.MULTILINE))
    except Exception as failure:  # noqa: BLE001 - an unreadable reply never becomes a proof
        LAST_REFUSAL["reason"] = llm.DECLINED
        LAST_REFUSAL["cause"] = f"the reply is not JSON: {type(failure).__name__}"
        return None
    if not isinstance(data, dict):
        LAST_REFUSAL["reason"] = llm.DECLINED
        LAST_REFUSAL["cause"] = f"the reply parsed as {type(data).__name__} and not an object"
        return None
    LAST_REFUSAL["reason"] = llm.ANSWERED
    LAST_REFUSAL["cause"] = ""
    return data


def _call_model(instruction: str, payload: str) -> Answer | None:
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
    data = read_json_object(reply["text"])
    if data is None:
        return None
    # Built field by field from what parsed, rather than handed back whole. The record says
    # it holds "as much of it as arrived", and returning the parse made that a hope: a reply
    # carrying a number where a body belongs went straight to a caller that renders it.
    # Each field is taken only when it is the string this record says it is, so a partial
    # answer is a partial record rather than a wrong one, which is what "not total" means.
    # Each read bound to a name first, then narrowed, then assigned. Read twice and the
    # checker asks about the second read rather than the first.
    answer: Answer = {}
    function, explanation = data.get("function"), data.get("explanation")
    source, module, body = data.get("test_source"), data.get("module"), data.get("body")
    if isinstance(function, str):
        answer["function"] = function
    if isinstance(explanation, str):
        answer["explanation"] = explanation
    if isinstance(source, str):
        answer["test_source"] = source
    if isinstance(module, str):
        answer["module"] = module
    if isinstance(body, str):
        answer["body"] = body
    return answer


def _signature(gap: CoverageGap) -> str:
    params = ", ".join(f"{p['name']}: {p['type']}" for p in gap["parameters"])
    return f"fn {gap['function']}({params}) -> {gap['return_type']}"


def _valid(data: Answer | None, asserts: Callable[[str], bool]) -> Answer | None:
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


# How much source one request may carry, in characters.
#
# Characters rather than tokens, because counting tokens needs the model's own tokenizer and
# this package does not have one. A token budget here would be a guess wearing a
# measurement's name. In the corpus this was derived from, the ratio was about 3.5
# characters per token.
#
# Derived rather than picked. The session auditing turso measured every proof-ready function
# in turso/core with this package's own reader on 2026-09-06: 6,136 functions across 257
# modules, median 376 characters, p90 2,750, p99 12,955, largest 145,605. Every module at
# once is 3.5 million characters, about five times what fits, so packing is the shape rather
# than a compromise on the way to one request. 200,000 characters is roughly 57,000 tokens,
# which leaves a 200,000-token context most of its room for the instruction and for the N
# answers coming back.
PACK_BUDGET_CHARS = 200_000


def pack_gaps(gaps: list[CoverageGap], budget: int) -> list[list[CoverageGap]]:
    """The gaps of one sweep, grouped into the requests that will carry them.

    One gap per request was the shape until 2026-09-06, which is 425 requests for a
    176-module sweep before a single line is compiled. The compile was batched long before
    the ask was, and `render_batch`'s docstring says why: N tests, one build. This is the
    same move one step earlier.

    In source order and greedy, which is deliberate on both counts. Order, because a reader
    following the run's progress should see it move through the codebase rather than through
    a sort nobody asked for. Greedy, because a packing that reordered gaps to fill requests
    more tightly would buy a few per cent and cost the ability to say which request a gap was
    in.

    A gap whose own source is over the budget travels alone rather than being dropped. It is
    the case that matters: turso's largest proof-ready function is 145,605 characters, and a
    sweep that quietly skipped its largest functions would report the same number over a
    smaller question. Whether the model can answer about it is the model's to say, and it
    says so by answering or not.

    A budget of nothing raises. Zero would put every gap in its own request, which is exactly
    the shape this replaces, arrived at silently."""
    if budget <= 0:
        raise ValueError(f"a pack budget of {budget} would send every gap on its own, "
                         "which is the shape packing replaces")
    packs: list[list[CoverageGap]] = []
    current: list[CoverageGap] = []
    used = 0
    for gap in gaps:
        size = len(gap["function_source"])
        if current and used + size > budget:
            packs.append(current)
            current, used = [], 0
        current.append(gap)
        used += size
    if current:
        packs.append(current)
    return packs


# What one answer is allowed to cost, in output tokens. The single ask has always allowed
# 2,048 for one answer; a pack of twenty needs twenty times the room or its reply is cut off
# mid-list. A truncated reply is not valid JSON, so the whole pack goes unanswered rather
# than half of it landing on the wrong gaps, which is the safe way to fail and still a
# failure worth not having.
_TOKENS_PER_ANSWER = 2048
# The API's own ceiling on one reply. A pack whose answers would not fit under it is still
# sent: the model decides what it can answer, and the validation below drops whatever did not
# arrive rather than guessing at it.
_MAX_OUTPUT_TOKENS = 64_000


def answers_for(gaps: list[CoverageGap], reply: llm.ModelReply) -> list[Answer | None]:
    """One answer per gap, in the order the gaps were sent, or None where there is none.

    A batched ask has one failure the single ask cannot have: the answers arrive together and
    something has to say which is which. An answer compiled against the wrong function would
    either fail to build or, worse, build and assert the wrong thing about code nobody read.

    So the model keys each answer by the index it was given, and an index that is missing,
    repeated or outside the pack is dropped rather than guessed at. A dropped answer is a gap
    nobody proposed for, which the sweep already counts; a misplaced one would be a finding
    about a function nobody read.

    The first answer for an index wins. Two answers for one gap is the model contradicting
    itself, something has to be kept, and letting the second overwrite the first would be a
    silent choice rather than a stated one."""
    if reply["text"] is None:
        LAST_REFUSAL["reason"] = reply["reason"]
        LAST_REFUSAL["cause"] = reply["cause"]
        return [None] * len(gaps)
    data = read_json_object(reply["text"])
    if data is None:
        return [None] * len(gaps)
    proofs = data.get("proofs")
    if not isinstance(proofs, list):
        # A model that answered in a shape nobody asked for is not a model that declined,
        # and the sweep has to be able to say which it met.
        LAST_REFUSAL["reason"] = llm.DECLINED
        LAST_REFUSAL["cause"] = ("the reply carries no proofs list; its keys are "
                                 f"{sorted(data)[:5]}")
        return [None] * len(gaps)
    out: list[Answer | None] = [None] * len(gaps)
    # Which indices the reply has already spoken for, valid or not. Tracked apart from the
    # answers themselves so that a second entry for one index is always dropped: an index
    # answered badly and then answered again is the model contradicting itself, and quietly
    # taking the second reading would be a choice made rather than stated.
    spoken: set[int] = set()
    for entry in proofs:
        if not isinstance(entry, dict) or not isinstance(entry.get("index"), int):
            continue
        at = entry["index"]
        if not 0 <= at < len(gaps) or at in spoken:
            continue
        spoken.add(at)
        body = entry.get("body")
        if not isinstance(body, str):
            continue
        # Rebuilt field by field rather than handed on whole, so the index the model was
        # keying by cannot travel any further than this loop.
        out[at] = _valid({"body": body, "explanation": str(entry.get("explanation", ""))},
                         body_asserts)
    return out


def propose_many(gaps: list[CoverageGap]) -> list[Answer | None]:
    """First calling test for every gap in one pack, in one request.

    One request per gap was the shape until 2026-09-06: 425 requests for a 176-module sweep,
    every one of them a round trip taken before any code was compiled. The compile had been
    batched long before the ask was."""
    payload = json.dumps([
        {"index": i, "function_source": gap["function_source"], "signature": _signature(gap),
         "uncovered_branch": f"the `{gap['kind']}` branch at line {gap['line']} is never exercised"}
        for i, gap in enumerate(gaps)
    ])
    room = min(_TOKENS_PER_ANSWER * max(1, len(gaps)), _MAX_OUTPUT_TOKENS)
    return answers_for(gaps, llm.call(PROPOSE_MANY_INSTRUCTION, payload, room, llm.anthropic_sdk))


def propose(gap: CoverageGap) -> Answer | None:
    """First calling test for the located gap: {body, explanation} or None."""
    payload = json.dumps({
        "function_source": gap["function_source"], "signature": _signature(gap),
        "uncovered_branch": f"the `{gap['kind']}` branch at line {gap['line']} is never exercised",
    })
    return _valid(_call_model(PROPOSE_INSTRUCTION, payload), body_asserts)


def repair(gap: CoverageGap, test_source: str, compiler_error: str) -> Answer | None:
    """Ask the model to fix a test that did not compile, given rustc's own diagnostic."""
    payload = json.dumps({
        "signature": _signature(gap), "function_source": gap["function_source"],
        "test_that_failed_to_compile": test_source, "rustc_error": compiler_error[-4000:],
    })
    return _valid(_call_model(REPAIR_INSTRUCTION, payload), body_asserts)



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

    # An explicit stack, because this walk refuses to enter a nested function rather than
    # reading every node, which is the one thing `ts_nodes.descendants` cannot be asked for.
    # It recursed until 2026-09-05, and parse-tree depth is set by the body being read.
    stack = [root]
    while stack:
        node = stack.pop()
        for child in node.children:
            if child.type == "function_item":
                continue
            if child.type == "macro_invocation":
                name = child.child_by_field_name("macro")
                text = name.text.decode("utf8", errors="ignore") if name is not None and name.text else ""
                if text in _ASSERT_MACROS:
                    return True
            stack.append(child)
    return False


_ASSERT_MACROS = frozenset({
    "assert", "assert_eq", "assert_ne",
    "debug_assert", "debug_assert_eq", "debug_assert_ne",
})


# honest-code-allow: L1.21.1 - render_module and _outcome_detail both build one f-string and share nothing else: one wraps a Rust test in a proof module, the other counts what generated tests became. A table of two rows whose only column is the whole body is the body written twice with a lookup in front
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
        # Nothing ran and the compiler said nothing, so nothing we can see compiled
        # anything. Called `error` until 2026-09-07, which named every way of failing to
        # reach cargo after the event cargo would have reported.
        return "fail" if ran else "unrun"
    return "pass"


def _fail_bucket(output: str, proof_label: str, body: str, return_type: str | None) -> str:
    """A failing run's retention bucket, from the gates: parse this proof's panic, then
    classify it as a divergence (retained) or one of the noise classes."""
    panic = coverage_gates.parse_panic(output, proof_label)
    return coverage_gates.classify_failure(body, return_type, panic)


@boundary
def _append_and_run(repo: Path, module_relpath: str, test_source: str, test_filter: str, timeout_seconds: float) -> tuple[int, str]:
    """Append a proof module to the file, run `cargo test <filter>`, and restore the file
    byte-for-byte. Returns (returncode, combined output). The file is always restored."""
    cargo = rust_trace._cargo()
    if cargo is None:
        # Said in cargo's own vocabulary of nothing: no test line and no compiler error, so
        # the classifier reads it as a run that never happened rather than as a test the
        # compiler rejected.
        return 1, "cargo is not on PATH, so nothing was compiled and nothing was run"
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
    open-input default Honest Code's No Implicit Defaults refuses: it answered a question about a test
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
    # What happened when the proof ran. Without it a reader met a test, a sentence saying
    # what it asserts, and a claim that it failed, with nothing saying how, so checking one
    # meant re-running it by hand against the checkout the run was still using.
    failure: str


def _retained_entry(module_relpath: str, gap: CoverageGap, explanation: str, source: str,
                    failure: str) -> CoverageProof:
    """One retained proof, built here for both loops. The batch loop called this and the
    per-module loop wrote the same six keys inline, so a field added to one was missing from
    the other and the report showed it on some proofs and not others."""
    return {
        "function": gap["function"], "language": "rust",
        "location": f"{module_relpath}:{gap['line']}",
        "explanation": explanation, "test_source": source.strip(),
        "failure": failure.strip(),
    }


def _refine_incidental(repo: Path, module_relpath: str, gap: CoverageGap, body: str, timeout_seconds: float) -> str:
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


# THE BATCH IS RUST'S OWN. THE LOOP UNDER IT IS SHARED, since 2026-09-02.
#
# This said the two provers were not the same shape, and gave a measurement: compared
# statement for statement with every string blanked on 2026-08-19, `_prove_one` was 21 lines
# here against 18 there with 8 identical, and `_prove_module` 26 against 11 with 4.
#
# The measurement compared whole FUNCTIONS and the duplication is path to path. This module's
# `_prove_module` has two: batch every proposal into one crate and compile once, or, when the
# batch does not compile, fall back to proving each gap on its own. That fallback was the
# Python prover's whole loop, sitting inside the twenty-six lines that got measured against
# it, so the shared half was averaged away by the batch path beside it.
#
# What the note got right stays true. The batch is a structural difference: compiling a crate
# once for twenty proofs is worth a path of its own, and pytest has no equivalent, so there
# is nothing there for Python to share. It is an addition in front of the loop rather than a
# different loop.
#
# Three rules live in the shared part and none of them may drift: repair at most the rounds
# the caller allowed, count every outcome including a decline, retain only a divergence.
# They are in `prove_gap` now.

def _prove_one(repo: Path, module_relpath: str, gap: CoverageGap, repair_rounds: int, timeout_seconds: float,
               propose_fn: Callable[..., Answer | None], repair_fn: Callable[..., Answer | None],
               run_fn: Callable[..., tuple[str, str]],
               refine_fn: Callable[..., str]) -> tuple[str, str, str, str]:
    """One gap, proven or not. The loop is `prove_gap.prove_one`, shared with the Python
    prover since 2026-09-02; what is here is Rust's own steps and its gate.

    The collaborators are parameters, as in `prove.prove` and the Python prover. They were
    module-level lookups, so testing this orchestration meant patching the module's own
    globals, and those tests went in the 2026-08-17 sweep for exactly that reason.
    Required rather than defaulted: a default puts a real cargo invocation one forgotten
    argument away from a test.

    The runner settles the verdict, which is where Rust's gate lives: a failing test is
    resolved into one of the fail buckets, and an incidental panic is re-run through the
    fifth collaborator to tell a proof from a fixture that blew up. Every fail routes
    through here, so leaving that a module-level lookup would have kept the gating path
    untestable however many of the other four were injected."""
    def run(g: CoverageGap, proposal: prove_gap.Answer, source: str) -> tuple[str, str]:
        status, output = run_fn(repo, module_relpath, source, timeout_seconds)
        if status != "fail":
            return status, output
        bucket = _fail_bucket(output, "proof", proposal["body"], g["return_type"])
        if bucket == "incidental_panic":
            bucket = refine_fn(repo, module_relpath, g, proposal["body"], timeout_seconds)
        return bucket, output

    return prove_gap.prove_one(
        gap,
        propose=propose_fn,
        render=render_module,
        run=run,
        repair=lambda g, source, output: repair_fn(g, source, output),
        # A crate that would not compile is the one verdict worth another call: the compiler
        # said what was wrong and the model can read it.
        repairable="error",
        rounds=repair_rounds,
    )


def _proposals_for(work: list[tuple[str, list[CoverageGap]]],
                   propose_pack: Callable[[list[CoverageGap]], list[Answer | None]],
                   ) -> dict[int, Answer | None]:
    """Every gap's first proposal, keyed by the gap's own identity.

    `propose_pack` is required and named by the caller, like every other collaborator here.
    Reaching for this module's own `propose_many` would make the only way to ask this
    function how it packs be to replace a name inside the module under test, which this
    package forbids and has a test for. Fifth appearance of one lesson.

    Asked for in packs across the whole sweep rather than one gap at a time inside each
    module, which is where the wall-clock went: 425 requests for a 176-module sweep, every
    one a round trip taken before a single line was compiled, and every one of them pure
    waiting.

    Keyed by `id`, because a gap is a plain mapping with no identifier of its own and two
    gaps in one function can carry equal contents. Identity is what the caller has and what
    the caller will look up with, and the map lives only as long as the sweep."""
    everything = [gap for _relpath, gaps in work for gap in gaps]
    answers: dict[int, Answer | None] = {}
    for pack in pack_gaps(everything, PACK_BUDGET_CHARS):
        for gap, answer in zip(pack, propose_pack(pack)):
            answers[id(gap)] = answer
    return answers


def _prove_module(repo: Path, module_relpath: str, gaps: list[CoverageGap], repair_rounds: int,
                  timeout_seconds: float, propose_fn: Callable[..., Answer | None],
                  repair_fn: Callable[..., Answer | None], batch_run_fn: Callable[..., tuple[int, str]],
                  run_fn: Callable[..., tuple[str, str]],
                  refine_fn: Callable[..., str]) -> tuple[list[CoverageProof], Outcomes]:
    """Prove all of one module's gaps. Fast path: batch every proposal into one compile and
    run once, then gate each failing test. If the batch does not compile (one bad test
    poisons it), fall back to per-gap with compiler-feedback repair. Returns (retained,
    outcomes). Only a `divergence` is retained; the noise buckets are counted, never hidden.

    `propose_fn` answers for one gap and says nothing about where the answer came from. The
    whole-repository sweep hands in a lookup over proposals it asked for in packs before any
    module was compiled; the single-module entry point hands in the model. Both satisfy the
    same one-line contract, which is why this function did not have to change when the ask
    was batched."""
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
                # The batch's own output, which is what this proof failed with. One build
                # carried every test, so the whole transcript is handed over rather than a
                # slice of it somebody would have to trust was cut in the right place.
                retained.append(_retained_entry(module_relpath, gap, proposal["explanation"],
                                                render_module(proposal["body"]), output))
        return retained, outcomes
    # The batch did not compile: isolate, repair, and gate each gap individually. This
    # fallback is the Python prover's whole loop, which is why both now ask for it.
    return prove_gap.prove_each(
        gaps,
        lambda gap: _prove_one(repo, module_relpath, gap, repair_rounds, timeout_seconds,
                               propose_fn, repair_fn, run_fn, refine_fn),
        lambda gap, explanation, source, failure: _retained_entry(
            module_relpath, gap, explanation, source, failure),
        outcomes=outcomes,
    )


def ceiling_detail(attempted: int, located: int, ceiling: int) -> str:
    """What a truncated sweep owes its reader, or nothing when it was not truncated.

    A result reading "attempted 5, retained 1" with no further word reads as a codebase
    with five uncovered branches, when it may have had five hundred. That is the
    unmeasured-read-as-clean shape this instrument exists to refuse, wearing a budget for a
    disguise. So a sweep that stopped at its ceiling names both numbers.

    It speaks only when a bound bit. Saying so on every sweep would train a reader to skip
    the sentence on the one sweep where it matters.

    Two bounds can truncate a sweep and this used to name only the ceiling, so a reader
    stopped by the per-module cap was sent to raise the wrong number. It reports the gap
    between found and tried, and names the ceiling as the bound only when the ceiling is
    what the run ran into."""
    if located <= attempted or ceiling <= 0:
        return ""
    stopped = "STOPPED AT THE CEILING" if attempted >= ceiling else "STOPPED SHORT"
    bound = f" (ceiling {ceiling})" if attempted >= ceiling else " (the per-module cap)"
    return (f" {stopped}: {attempted} of {located} located gaps were attempted"
            f"{bound}. The rest were not measured and are not counted clean.")


# A sweep reports its progress through this, once per module, before that module is
# proven. Typed, and it was `progress=None` untyped: a public parameter naming no shape at
# all, so the three arguments it is called with lived only in a docstring and a caller that
# read them differently would fail inside the sweep rather than at the call.
SweepProgress = Callable[[str, int, int], None]


@boundary
def _rust_sources(repo: Path, measured: dict[str, frozenset[int]]) -> dict[str, str]:
    """The text of every Rust file coverage measured, keyed the way coverage keys them.

    The one read the sweep's choosing needs, done at the edge so the choosing has none. A
    file that will not open is left out rather than given back empty: an empty module has no
    functions and no gaps, which reads as a file with nothing to prove instead of a file
    nobody could read."""
    read: dict[str, str] = {}
    for relpath in measured:
        if not relpath.endswith(".rs"):
            continue
        try:
            read[relpath] = (repo / relpath).read_text(errors="ignore")
        except OSError:
            continue
    return read


# honest-code-allow: L1.21.13 - the writer and both readers are one unit. `_call_model` writes LAST_REFUSAL and it is the single model boundary BOTH sweeps import, so there is no second source and no cross-module surprise. Threading the reason back would change the injected propose_fn signature, its repair counterpart and every test fake, to reach one reader at the end of one sweep. The sweeps are sequential, so the value is never stale by more than one call.
def prove_coverage_repo(repo: Path, cap_per_module: int, repair_rounds: int,
                        timeout_seconds: float, progress: SweepProgress | None,
                        max_attempts: int, cargo_args: tuple[str, ...],
                        workers: int) -> Sweep:
    """Sweep the WHOLE crate: one coverage build, then every module with uncovered branches is
    proven (batched, with per-gap repair fallback). Retained proofs are aggregated across the
    codebase. `progress(relpath, n_gaps, running_retained)` is called before each module.

    `workers` is how many modules are proven at once, and it has no default. A module is
    proven by appending a test to its own source file, compiling, and putting the file back,
    so each worker needs its own checkout; a default of eight would spend eight copies of
    somebody's disk without being asked, which is the same defect as a ratchet with a
    default. What the pool cost is said in the report rather than left to the reader to
    infer from the number."""
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
    cov = rust_trace.repo_uncovered_lines(repo, timeout_seconds, cargo_args)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    host = host_cfg()

    def gaps_of(source: str, lines: frozenset[int]) -> list[CoverageGap]:
        return _live_gaps(rust_facets.uncovered_gaps(rust_facets.module_functions(source), lines), host)

    work, located, attempted_gaps = budget.gaps_to_attempt(
        cov["files"], _rust_sources(repo, cov["files"]), gaps_of, cap_per_module, max_attempts)
    # Every gap's first proposal, asked for before any of them is compiled, packed into as
    # few requests as the budget allows. The whole work list is known here and was already
    # settled deterministically by `gaps_to_attempt`, so the ceiling is spent before a single
    # request goes out and no amount of packing can overspend it.
    answers = _proposals_for(work, propose_many)
    retained: list[CoverageProof] = []
    outcomes = {k: 0 for k in _OUTCOMES}
    modules = len(work)
    hands = workers_for(workers, modules)
    # Named for the run, so a directory left behind after a crash says which sweep made it.
    # Three empty ones were found on a box on 2026-09-07 and cost somebody a minute working
    # out they were not worker copies.
    work_root = Path(tempfile.mkdtemp(prefix=f"l1-sweep-{os.getpid()}-"))
    checkouts = checkouts_for(repo, hands, work_root)
    hands = len(checkouts["paths"])

    def prove_share(where: Path, share: list[tuple[str, list[CoverageGap]]]) -> tuple[
            list[CoverageProof], Outcomes]:
        """One worker's modules, proven in one checkout, start to finish.

        The checkout is the worker's own, so the source file it edits and puts back is
        nobody else's. Everything else it needs was settled before the pool started: the
        coverage build ran once, and every proposal was asked for and answered."""
        kept: list[CoverageProof] = []
        tally = {k: 0 for k in _OUTCOMES}
        for relpath, gaps in share:
            if progress:
                progress(relpath, len(gaps), len(kept))
            # The real four, named at the one place that knows which they are. The first is
            # a lookup rather than a request: the proposals were asked for above, in packs.
            module_kept, module_tally = _prove_module(
                where, relpath, gaps, repair_rounds, timeout_seconds,
                lambda gap: answers.get(id(gap)), repair, _append_and_run, _run_in_crate,
                _refine_incidental)
            kept.extend(module_kept)
            for k in tally:
                tally[k] += module_tally[k]
        return kept, tally

    shares = share_out(work, hands)
    # Threads rather than processes. Every worker spends its time waiting on cargo, which is
    # a subprocess and holds no interpreter lock, and threads let the answers come back
    # without any of this being picklable.
    with futures.ThreadPoolExecutor(max_workers=max(1, len(shares))) as pool:
        for kept, tally in pool.map(prove_share, checkouts["paths"], shares):
            retained.extend(kept)
            for k in outcomes:
                outcomes[k] += tally[k]
    _discard_checkouts(checkouts)
    # The root as well as the copies inside it. Removing only the copies left an empty
    # directory per run, which leaks nothing and still sends the next person looking.
    shutil.rmtree(work_root, ignore_errors=True)
    # `attempted` is every gap handed to a model, declines included: that is the unit that
    # cost money, and a budget that did not count the declines could not be reconciled.
    attempted = sum(outcomes.values())
    detail = sweep_detail(len(retained), modules, located, outcomes, "cargo",
                          LAST_REFUSAL["reason"], LAST_REFUSAL["cause"])
    if attempted - outcomes["declined"]:
        detail += _outcome_detail(outcomes)
    detail += ceiling_detail(attempted_gaps, located, max_attempts)
    # The scope, where one was given. A coverage figure over part of a workspace is a
    # different number from one over all of it, and a reader cannot tell them apart from
    # the figure.
    if cargo_args:
        detail += f" (cargo scoped by {' '.join(cargo_args)})"
    detail += pool_detail(hands, checkouts["copies"], checkouts["how"], checkouts["asked"])
    return {"retained": retained, "attempted": attempted, "outcomes": outcomes, "modules": modules, "detail": detail}


def sweep_detail(retained: int, modules: int, located: int, outcomes: Outcomes, provenance: str,
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
        # Three ways to locate gaps and prove none, and this said two of them. A sweep that
        # bought answers, received them, and lost every one between the reply and the
        # proposal printed "nothing usable for 0 of them", which is a count of declines that
        # never happened. Zero declines beside zero proven is arithmetic on an empty set and
        # a reader given it has nowhere to go. Met on 2026-09-07 after 87 minutes of asking.
        if reason in (llm.DECLINED, "") and not declined:
            why = ("every answer was bought and none reached a module, so no proposal was "
                   "ever compiled: the gaps were located and the replies arrived")
        elif reason in (llm.DECLINED, ""):
            why = f"the model replied with nothing usable for {declined} of them"
        else:
            why = llm.WHY[reason]
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


def _outcome_detail(outcomes: Outcomes) -> str:
    """The honest breakdown: what each generated test became. Only `divergence` is a proven
    bug; the noise buckets are named so a zero-retained result still says what happened."""
    return (f"Of {sum(outcomes.values())} generated tests run in-crate: {outcomes['divergence']} "
            f"retained as behavioural divergences (bug proven), {outcomes['pass']} passed (branch correct), "
            f"{outcomes['wrong_channel']} inspected the wrong output channel, "
            f"{outcomes['invalid_fixture']} were invalid fixtures (construction the code rejects), "
            f"{outcomes['incidental_panic']} panicked outside the assertion (kept for review), "
            f"{outcomes['error']} did not compile."
            + (f" {outcomes['unrun']} never ran: no compiler output at all, which is this "
               "tool failing to reach cargo rather than cargo rejecting a test."
               if outcomes.get("unrun") else ""))


def prove_coverage(repo: Path, module_relpath: str, cap: int, timeout_seconds: float,
                   repair_rounds: int, cargo_args: tuple[str, ...]) -> Sweep:
    """Locate uncovered decision branches in one Rust module, prove each (propose -> run,
    then compiler-feedback repair up to repair_rounds), and retain the ones that fail.
    Returns the coverage_proofs shape the card consumes. Every not-run path carries a reason."""
    if not rust_trace._cargo():
        return {"retained": [], "attempted": 0, "detail": "needs a Rust toolchain (cargo) in PATH"}
    if not model_available():
        return {"retained": [], "attempted": 0,
                "detail": f"no coverage proofs generated: {llm.WHY[llm.unavailable_reason(llm.anthropic_sdk)]}"}

    cov = rust_trace.module_uncovered_lines(repo, module_relpath, timeout_seconds, cargo_args)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    module = repo / module_relpath
    functions = rust_facets.module_functions(module.read_text(errors="ignore"))
    gaps = _live_gaps(rust_facets.uncovered_gaps(functions, cov["uncovered_lines"]), host_cfg())[:cap]
    if not gaps:
        return {"retained": [], "attempted": 0, "detail": "no proof-ready uncovered branches located in this module"}

    retained: list[CoverageProof] = []
    outcomes = {k: 0 for k in _OUTCOMES}
    for gap in gaps:
        # The four collaborators, named here as the repository sweep names them. The loop
        # requires them rather than defaulting them, for the reason its own docstring gives:
        # a default puts a real cargo invocation one forgotten argument away from a test.
        # This call site was never updated when they became required, so the whole
        # per-module path raised before it proved anything, and every test of the loop
        # passes its own collaborators, which is what left this one call unexercised.
        bucket, explanation, source, failure = _prove_one(
            repo, module_relpath, gap, repair_rounds, timeout_seconds, propose, repair,
            _run_in_crate, _refine_incidental)
        outcomes[bucket] += 1
        if bucket == "divergence":
            retained.append(_retained_entry(module_relpath, gap, explanation, source, failure))
    attempted = sum(outcomes.values())
    # The breakdown is the honest part: 0 retained means nothing without it. Each generated
    # test lands in a named bucket; only a behavioural divergence is a proven bug and retained.
    detail = (f"{len(retained)}/{attempted} coverage proofs retained. " + _outcome_detail(outcomes)
              ) if attempted else "no proof-ready uncovered branches located"
    return {"retained": retained, "attempted": attempted, "outcomes": outcomes,
            "repair_rounds": repair_rounds, "detail": detail}
