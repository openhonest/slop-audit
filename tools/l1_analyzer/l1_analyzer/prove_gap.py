"""How one located gap becomes a retained proof, for both coverage provers.

A prover finds a branch no test reaches, asks a model for one test, runs it, and keeps the
test only if it fails against the code as written. Two provers exist, one for Rust and one
for Python, and this is the part they share.

A note in the source said they were compared statement for statement in August and are not
the same shape. The measurement compared whole FUNCTIONS and the duplication is path to
path. Rust's module loop has two paths: batch every proposal into one crate and compile
once, or, when the batch does not compile, fall back to proving each gap on its own. That
fallback is Python's whole loop, and it was inside the bigger function that got measured.

The batch stays Rust's own. Compiling a crate once for twenty proofs is worth a path of its
own, and pytest has no equivalent, so there is nothing there for Python to share.

Three rules live here and none of them may drift. Repair at most the number of times the
caller allowed, which is a budget, and the second budget rule this package has had two
copies of. Count every outcome including a decline, because a model call that produced
nothing still cost money. Retain only a divergence, which is the whole discipline: a test
that passes against the code as written has proven nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict, TypeVar

Gap = TypeVar("Gap")
Proof = TypeVar("Proof")


class Answer(TypedDict, total=False):
    """What the model returned for one gap, as this loop reads it.

    Two keys, because two are all this loop touches: the body it renders and runs, and the
    sentence it hands back beside the verdict. Each prover's own answer record carries more
    and is compatible with this one.

    Not `Any`. The type-escape gate refused that on the commit that introduced it, and it
    was right to: a mapping of anything to anything has no keys to be wrong about, so both
    reads below would have been assumptions nothing could check."""

    body: str
    explanation: str


def prove_one(gap: Gap, *,
              propose: Callable[[Gap], Answer | None],
              render: Callable[[str], str],
              run: Callable[[Gap, Answer, str], tuple[str, str]],
              repair: Callable[[Gap, str, str], Answer | None],
              repairable: str,
              rounds: int) -> tuple[str, str, str]:
    """Propose, run, repair while it is repairable, and report what happened.

    Returns the verdict, the explanation of the proposal that actually ran, and its source.

    A model that declined is a named outcome and nothing is run: the call still cost money,
    and a prover that passed over it would report a hit rate over calls it did not admit
    making.

    `run` settles the verdict as well as executing, so a language that reads its verdict out
    of a second pass over the output does that inside its own runner. That is what keeps the
    parameter list to what genuinely differs.

    It is handed the proposal as well as the rendered source, because Rust's gate reads the
    body the model wrote rather than the crate built around it. Recovering one from the
    other would mean unwrapping the rendering, which is a second place that has to agree
    with how the rendering was done.

    `repairable` is the one verdict worth another call. Rust waits for a crate that would
    not compile and Python for a test that errored in setup, and asking again on any other
    verdict spends a call to be told the same thing."""
    proposal = propose(gap)
    if proposal is None:
        return "declined", "", ""
    source = render(proposal["body"])
    status, output = run(gap, proposal, source)
    for _ in range(rounds):
        if status != repairable:
            break
        fixed = repair(gap, source, output)
        if fixed is None:
            break
        proposal = fixed
        source = render(fixed["body"])
        status, output = run(gap, proposal, source)
    return status, proposal["explanation"], source


def prove_each(gaps: list[Gap],
               attempt: Callable[[Gap], tuple[str, str, str]],
               retain: Callable[[Gap, str, str], Proof],
               *, outcomes: dict[str, int]) -> tuple[list[Proof], dict[str, int]]:
    """Every gap in one module: each outcome counted, only a divergence retained.

    A test that passes against the code as written has proven nothing, so it is counted and
    dropped. Keeping it would report a hit rate of one on a prover that proved nothing.

    The tally is the caller's, because each language names its own verdicts, and a verdict
    missing from it raises rather than being filed under a name written for a different one.
    A prover and a report that disagree about what can happen is the shape this instrument
    exists to name."""
    retained: list[Proof] = []
    for gap in gaps:
        bucket, explanation, source = attempt(gap)
        outcomes[bucket] += 1
        if bucket == "divergence":
            retained.append(retain(gap, explanation, source))
    return retained, outcomes
