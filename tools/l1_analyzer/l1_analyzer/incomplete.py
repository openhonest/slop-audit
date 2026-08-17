"""INCOMPLETE CODE: the one way this analyzer is allowed to have no answer.

The bug category this eliminates is a measure that publishes a value it did not earn. Every
instance found in the 2026-08-16 stub sweep has the same shape: a denominator of zero, an
empty rule table, or a construct nobody wrote a row for, turned into `0.0` and banded
`Healthy`. Afterwards a reader cannot tell read-and-clean from not-looked-at, and the failure
runs the wrong way round, because the less the analyzer manages to read the cleaner the
verdict it issues.

The rule here is that a measure may not decide what to do about its own ignorance. It raises
and stops. Exactly one place decides, `indicators._measure`, and what it decides is `n/a`
with the reason printed, never a band. That is Typed Exceptions at the Boundary applied to
measurement: do not catch inside the business logic, let the function raise, and let the
boundary inspect the type and choose the output.

Why an exception rather than a sentinel return. A sentinel has to be checked, an unchecked
sentinel is indistinguishable from a value, and the sweep found four measures whose authors
had already written the check in the wrong direction. An exception cannot be ignored by
accident. Adding a new measure that forgets its zero case now fails loudly on the first
repository that trips it, instead of shipping a clean bill for eighteen months.

`IncompleteCode` means the analyzer's own code is missing, not that the audited repository is
empty. Both reach the boundary the same way and the boundary prints the basis, so a reader
sees which one happened.

This module was written, deleted and written again. The first version came before its tests,
which is why it was reverted in 82190a9: the tests that came after it had never been seen to
fail, so nothing had established that the raises fired for the reasons they claimed. This
version is written against those tests while they are red.
"""

from __future__ import annotations


class IncompleteCode(Exception):
    """Raised where the analyzer would otherwise publish a value it has no basis for.

    Carries the measure that could not answer and the basis it lacked, so the boundary can
    print both rather than a bare n/a. The message always opens `INCOMPLETE CODE: ` so the
    string is greppable in a log, a CI transcript and a bug report alike.
    """


def refuse(measure: str, basis: str) -> IncompleteCode:
    """Build the exception for `measure`, which could not answer because of `basis`.

    Returns rather than raises, so the call site reads `raise refuse(...)` and the raise stays
    visible at the point it happens. A helper that raised on the caller's behalf would hide
    the control flow inside a function call, which is the thing this module exists to stop.
    """
    return IncompleteCode(f"INCOMPLETE CODE: {measure} cannot answer: {basis}")


def ratio(numerator: int, denominator: int, measure: str, basis: str) -> float:
    """`numerator / denominator` as a percentage, or refuse when the denominator is zero.

    Zero over zero is the shape every empty-denominator stub took. It is not a percentage and
    it is not zero percent; it is the absence of a measurement, and the four sites that wrote
    `if total > 0 else 0.0` each published it as a clean score. Routing every ratio through
    here makes writing that line again impossible: there is no expression left that yields a
    number when nothing was counted.
    """
    if denominator == 0:
        raise refuse(measure, basis)
    return numerator / denominator * 100
