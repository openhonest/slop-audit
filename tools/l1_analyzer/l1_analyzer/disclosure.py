"""The notes a result owes its reader when it did less than it looks like it did.

Two of them, and they were in two places: `_with_skipped` in indicators and `_listed_note`
in absolute_paths, which is a module about hardcoded paths and no home for a general
reporting rule. They are the same kind of sentence and they answer the same question, so
they sit together.

Both are silent when there is nothing to say, and that is the rule they share. A note on
every result is one a reader learns to skip, which is how the one that mattered would be
missed. They speak only when the thing they disclose actually happened.

This module imports nothing from the package. A disclosure that needed the analyzer to
compute it would be a measurement, and a measurement can be wrong; these only restate
numbers their caller already has.
"""

from __future__ import annotations


def with_skipped(details: str, skipped: int) -> str:
    """Name the files a scan could not read, so a count over a subset is not read as a
    count over the tree."""
    return details if skipped == 0 else f"{details}; {skipped} file(s) unreadable and excluded"


def listed_note(shown: int, total: int) -> str:
    """Name a finding list that was cut, so it stops disagreeing with the count beside it.

    The count was always honest and the LIST was short, so two fields of one result said
    different things: a reader counting the findings got the cap where the value said the
    total. The only way to notice was to compare the two, which is what nobody does when
    one of them is a list they are iterating."""
    return "" if total <= shown else f"; {shown} of them listed below"
