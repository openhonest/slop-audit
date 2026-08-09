"""Deterministic retention gates for the coverage-gap prove loop.

A generated test is retained only when its failure is a real behavioural divergence:
the target function ran and returned a value the test's own assertion rejected. The
raw signal `the test failed` is too coarse, because a test can also fail by panicking
in a constructor, by targeting a branch the host never compiles, or by inspecting the
wrong output channel. Each of those is the tool's own noise, not a defect.

These gates separate the signal from that noise, and they are pure: they read the
generated test source, the function's return type, the host cfg set, and the cargo
output, and they return a verdict. No model call, no I/O. The prove loop runs the
tests and evaluates the gates; this module only decides. Nothing is dropped silently -
every non-retained candidate carries the bucket that names why.

The four gates, each removing one noise class measured on a real 176-module sweep:

  attribution   the observed panic is the test's own `assert!`, not a construction or
                arrange-step panic (message match). Kills invalid-input panics.
  invalid fixture   the test builds its inputs with `mem::zeroed`, a null pointer, or a
                out-of-range scalar a constructor rejects. Confirmed by a permutation:
                rebuild with a valid scalar and the panic disappears.
  host cfg      the targeted branch sits under a `#[cfg(...)]` that is false for the
                host target, so the host never compiles it. Filtered at enumeration.
  channel       the function returns a deferred handle (a Completion / Future) and the
                real result arrives by callback, so an assertion on the returned handle
                inspects the wrong channel.
"""

from __future__ import annotations

import re
from typing import TypedDict

from l1_analyzer.indicators import _get_parser

# --- attribution: is the panic the test's own assertion? -------------------

# `mem::zeroed` UB can abort the process before any message prints; a construction
# `assert!` prints the library's own message. Either way the message is not the test's.
_PANIC_AT = re.compile(r"panicked at\s+([^\n:]+:\d+:\d+):\s*\n?\s*([^\n]*)")
_PANIC_OLD = re.compile(r"panicked at\s+'([^']*)',\s+([^\n:]+:\d+:\d+)")


class Panic(TypedDict):
    location: str
    message: str


def _string_literals(body: str) -> list[str]:
    """Every string-literal value in a Rust test body, in source order. The assertion
    message is the last one: the render contract puts `assert!(<cond>, <message>)` at the
    end, and any string inside <cond> precedes the message."""
    src = f"fn _f() {{\n{body}\n}}".encode()
    root = _get_parser("rust").parse(src).root_node
    out: list[str] = []

    def walk(node) -> None:
        if node.type in ("string_literal", "raw_string_literal"):
            text = src[node.start_byte:node.end_byte].decode("utf8", errors="ignore")
            out.append(_string_content(text))
        for child in node.named_children:
            walk(child)

    walk(root)
    return out


def _string_content(literal: str) -> str:
    """The text inside a Rust string literal, quotes and the raw `r#"` fence removed."""
    inner = literal
    if inner.startswith("r"):
        inner = inner[1:].strip("#")
    return inner[1:-1] if len(inner) >= 2 and inner[0] == '"' and inner[-1] == '"' else inner


def assertion_message(body: str) -> str | None:
    """The message the test's own `assert!` prints when it fires, or None when the test
    carries no message (then a panic can never be attributed to the assertion)."""
    literals = _string_literals(body)
    return literals[-1] if literals else None


def parse_panic(output: str, proof_label: str) -> Panic | None:
    """The panic for one proof function from cargo test output. `proof_label` is `proof`
    for a single run or `proof_3` for one test of a batch; its stdout block is isolated
    first so a sibling test's panic is never misattributed. None when it did not panic
    (it passed, failed to compile, or was aborted without a message block)."""
    block = _proof_block(output, proof_label)
    if block is None:
        return None
    match = _PANIC_AT.search(block) or None
    if match:
        return {"location": match.group(1).strip(), "message": match.group(2).strip()}
    old = _PANIC_OLD.search(block)
    if old:
        return {"location": old.group(2).strip(), "message": old.group(1).strip()}
    return None


def _proof_block(output: str, proof_label: str) -> str | None:
    """The `---- <mod>::<label> stdout ----` failure block for one proof, or, for a single
    unlabelled run, the whole output. Isolating the block keeps a batch's panics separate."""
    marker = re.compile(rf"----\s+\S*::{re.escape(proof_label)}\s+stdout\s+----(.*?)"
                        rf"(?=----\s+\S+::proof|\n\nfailures:|\Z)", re.DOTALL)
    found = marker.search(output)
    if found:
        return found.group(1)
    return output if "panicked at" in output else None


def attribution(assert_msg: str | None, panic: Panic | None) -> str:
    """`assertion` when the panic is the test's own assert firing; `incidental` for a
    construction panic, an arrange-step `.expect()`, or a library assert - a failure that
    is not a statement about the target function's return value."""
    if panic is None or assert_msg is None:
        return "incidental"
    seen, want = panic["message"].strip(), assert_msg.strip()
    return "assertion" if want and (want in seen or seen in want) else "incidental"


# --- invalid fixture: inputs a constructor's own contract rejects ----------

_INVALID_MARKERS = ("mem::zeroed", "mem::uninitialized", "MaybeUninit",
                    "transmute", "ptr::null", "null_mut")


def invalid_fixture_marker(body: str) -> str | None:
    """The first uninitialised-or-null construction marker in the test, or None. A test
    that fabricates an input with `mem::zeroed()` or a null pointer feeds a constructor a
    value its contract forbids, so a resulting panic is the fixture, not a defect."""
    return next((m for m in _INVALID_MARKERS if m in body), None)


_INT_LITERAL = re.compile(r"\b(\d+)\b")


def permute_scalar_construction(body: str) -> str | None:
    """A copy of the test with every bare integer literal replaced by a larger, 64-aligned
    value, or None when there is none to permute. Re-running this is the permutation check:
    if a construction panic clears under a valid scalar, the original scalar - not the
    function - caused it, so the finding is an invalid fixture. Deterministic, no model."""
    if not _INT_LITERAL.search(body):
        return None
    permuted = _INT_LITERAL.sub(lambda m: str(max(int(m.group(1)), 1) * 64), body)
    return permuted if permuted != body else None


# --- host cfg: a branch the host target never compiles ---------------------

_EXHAUSTIVE_KEYS = ("target_os", "target_family", "target_arch", "target_env",
                    "target_pointer_width", "target_vendor", "target_endian", "target_abi")
_BARE_KNOWN = ("unix", "windows")


def _normalise_atom(atom: str) -> str:
    """`target_os = "linux"` and `target_os="linux"` are the same predicate; collapse the
    spacing so a source atom compares to a `rustc --print cfg` atom."""
    return re.sub(r"\s*=\s*", "=", atom.strip())


def host_cfg_atoms(rustc_print_cfg: str) -> frozenset[str]:
    """The host's cfg set from `rustc --print cfg` output, one normalised atom per line."""
    return frozenset(_normalise_atom(line) for line in rustc_print_cfg.splitlines() if line.strip())


def _atom_truth(atom: str, host: frozenset[str]) -> bool | None:
    """Three-valued: True/False when the host proves the atom, None when it cannot. Only a
    proven False lets a branch be excluded, so an unknown feature flag never hides a gap."""
    norm = _normalise_atom(atom)
    if norm in host:
        return True
    if "=" in norm:
        key = norm.split("=", 1)[0]
        if key in _EXHAUSTIVE_KEYS and any(h.startswith(key + "=") for h in host):
            return False  # the key is set to a different value; this value cannot also hold
        return None
    return False if norm in _BARE_KNOWN else None


def _split_top_level(inner: str) -> list[str]:
    """Comma-split one cfg predicate list, respecting nested parentheses."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(inner):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(inner[start:i])
            start = i + 1
    parts.append(inner[start:])
    return [p.strip() for p in parts if p.strip()]


def _eval_cfg(pred: str, host: frozenset[str]) -> bool | None:
    """Evaluate a cfg predicate against the host set in three-valued logic."""
    pred = pred.strip()
    for op in ("not", "all", "any"):
        if pred.startswith(op + "(") and pred.endswith(")"):
            terms = [_eval_cfg(t, host) for t in _split_top_level(pred[len(op) + 1:-1])]
            return _COMBINE[op](terms)
    return _atom_truth(pred, host)


def _not(terms: list[bool | None]) -> bool | None:
    inner = terms[0] if terms else None
    return None if inner is None else not inner


def _all(terms: list[bool | None]) -> bool | None:
    if any(t is False for t in terms):
        return False
    return True if all(t is True for t in terms) else None


def _any(terms: list[bool | None]) -> bool | None:
    if any(t is True for t in terms):
        return True
    return False if all(t is False for t in terms) else None


_COMBINE = {"not": _not, "all": _all, "any": _any}


def cfg_excluded(predicate: str | None, host: frozenset[str]) -> bool:
    """True when the host target provably does not compile this branch, so no test can
    exercise it. False for no cfg, or a predicate the host cannot disprove."""
    if not predicate:
        return False
    return _eval_cfg(predicate, host) is False


# --- channel: a deferred result the return value does not carry ------------

_DEFERRED_MARKERS = ("Completion", "Future", "JoinHandle", "Poll<", "BoxFuture",
                     "LocalBoxFuture", "Receiver<", "oneshot::")


def is_deferred_return(return_type: str | None) -> bool:
    """True when the function hands back a completion or future handle rather than the
    result itself, so the outcome arrives by callback. An assertion on such a return
    inspects the submission, not the value the branch produces."""
    if not return_type:
        return False
    return any(marker in return_type for marker in _DEFERRED_MARKERS)


# --- the combined verdict --------------------------------------------------

def classify_failure(body: str, return_type: str | None, panic: Panic | None) -> str:
    """One failing generated test -> its retention bucket.

      divergence       the assertion fired on the return value: a real signal, retained.
      wrong_channel    the assertion fired, but on a deferred handle, not the result.
      invalid_fixture  an incidental panic with a fabricated-invalid construction marker.
      incidental_panic any other panic outside the assertion (a constructor, an arrange
                       `.expect()`); a possible real crash, kept out of findings for review.

    A permutation re-run may later move an incidental_panic to invalid_fixture; this pure
    verdict uses only what one run shows."""
    if attribution(assertion_message(body), panic) == "assertion":
        return "wrong_channel" if is_deferred_return(return_type) else "divergence"
    return "invalid_fixture" if invalid_fixture_marker(body) else "incidental_panic"
