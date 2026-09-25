"""What a finished proof run MEANT: pass, fail, error, or one of the noise classes.

Three questions, and none of them is about locating a gap or asking a model. Does this body
evaluate an assertion at all. Did this run pass, fail, or never reach a compiler. If it failed,
is the failure a divergence worth keeping or one of the ways this tool's own generated test can
be wrong.

Its own module because the prove loop crossed this project's own god-file line, and these are
the part of it that decides rather than the part that drives. They are also the part with no
I/O: text in, a verdict out, so every one can be asserted without a model, a network or a
toolchain.

A FAILING TEST IS THE RESULT WORTH KEEPING, which is the thing that reads backwards until you
have seen it. An uncovered branch that a generated test can make fail is a branch that is both
untested and wrong, so the failing test closes the gap and documents the expectation at once.
Everything here exists to tell that failure from the three ways a generated test fails for
reasons of its own.
"""

from __future__ import annotations

import re

from l1_analyzer import coverage_gates

_ASSERT_MACROS = frozenset({
    "assert", "assert_eq", "assert_ne",
    "debug_assert", "debug_assert_eq", "debug_assert_ne",
})


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
