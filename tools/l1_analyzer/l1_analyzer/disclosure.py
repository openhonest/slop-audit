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


def timeout_note(seconds: float) -> str:
    """Name the time a run was given and the flag that gives it more.

    Every refusal in this package names its repair: a missing C compiler says which
    commands it looks for, a missing sanitizer says which rustup command installs it, Ruby
    with no branch data says the line to add to the spec_helper. Fifteen timeout refusals
    said only that something timed out. Not how long it was given, not that the caller
    chooses that number, not which flag raises it.

    It is the refusal an adopter is most likely to meet, because the default is three
    hundred seconds for one execution of their whole suite. It cost this repository its own
    two runtime indicators: our suite takes about five minutes, so every audit we ever ran
    reported branch coverage and determinism as not measured, and both are real numbers
    behind that sentence.

    It closes the sentence it is joined to. Every refusal it appends to ends without
    punctuation, so the note supplies the full stop and starts a new sentence rather than
    running two together.

    Seconds without a decimal point where there is nothing after it. The flag takes seconds
    and a reader types the number back, so the point is noise in a sentence about a
    stopwatch."""
    shown = f"{seconds:g}"
    return f". It was allowed {shown}s; raise it with --timeout."
