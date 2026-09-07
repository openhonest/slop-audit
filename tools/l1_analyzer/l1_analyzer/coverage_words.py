"""What this sweep says to a model, and nothing else.

Three sets of words: ask for a first test that exercises one uncovered branch, ask for the
same for several branches at once, and ask for a fix when the compiler refused the last one.

They live apart from the code that sends them because they are the part a person edits by
reading, and because the module that sends them crossed the god-file line while they sat in
it. Nothing here decides anything.
"""

from __future__ import annotations

PROPOSE_INSTRUCTION = (
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

REPAIR_INSTRUCTION = (
    "The Rust test below does not compile. Here is the exact rustc error. Rewrite the test BODY so it "
    "compiles and still asserts the same intended behavior. Fix the arrange step: build the real argument "
    "values the signature requires (call constructors, `::new`, `Default::default()`, enum variants - "
    "anything in scope via `use super::*;`), not bare literals of the wrong type. Keep the final "
    "`let result = ...;` and the `assert!` on `result`. Return ONLY a JSON object with keys "
    '"body" (the corrected Rust statements, no fn/mod wrapper) and "explanation".'
)

PROPOSE_MANY_INSTRUCTION = (
    "You are given SEVERAL Rust functions, each with one decision branch that no test ever "
    "reached. Answer for every one of them. For each, infer the caller-facing behavior the "
    "branch SHOULD have from the function name, its signature, and the branch condition - do "
    "not just echo what the code visibly does. Write the BODY of a Rust test that exercises "
    "exactly that branch: construct the argument values (bindings are fine), call the "
    "function into a binding named `result`, then `assert!(<property>, <message>)` on "
    "`result`. Each proof is kept only if execution contradicts your assertion, so assert "
    "the behavior a correct implementation MUST have, not a prediction of the current "
    "output. `use super::*;` is already in scope in each case. Return ONLY a JSON object "
    'with one key, "proofs", holding a list of objects with keys: "index" (the integer index '
    'you were given for that function), "body" (the Rust statements, no fn/mod wrapper) and '
    '"explanation" (one plain sentence stating the behavior you assert). Answer every index '
    "you were given, and use each index exactly once."
)
