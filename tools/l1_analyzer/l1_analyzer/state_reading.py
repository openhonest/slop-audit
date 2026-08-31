"""What a reading of a repository's state looks like when it comes back.

Three records, split out of the reader that produces them when that file crossed a thousand
lines and this tool's own god-file rule failed the commit. They are the shapes a caller
holds rather than the walk that fills them, and the card reads eight of their fields.

Every one of those reads was an assumption until these were written down: the reading was
handed over as a mapping of anything to anything, so nothing could say whether the findings
were a list or the counts a table.
"""

from typing import TYPE_CHECKING, NotRequired, TypedDict

from l1_analyzer.scope import BucketedPaths
from l1_analyzer.state_partition import Silence
from l1_analyzer.state_sites import Site

if TYPE_CHECKING:
    from l1_analyzer.state_bounds import Finding


class StateReading(TypedDict):
    """L1.18b's whole reading of a repository's state.

    Written out because the card reads eight of these fields and every read was an
    assumption: the result was handed over as a mapping of anything to anything, so nothing
    could say whether `findings` was a list or `counts` a table."""

    # The word a card prints beside the number. It was written on every reading and named
    # nowhere, so the field the card reads first was the field nothing described.
    verdict: str
    value: float | int | str
    band: str
    counts: dict[str, int]
    coverage: object
    # A number when the meter ran, and ABSENT when it did not. It was declared a number and
    # the refusal wrote the string "n/a" into it, so the one field that says whether this
    # reading happened at all held two types and the reader had to ask which it got. The
    # reader's own docstring said so: "may be absent or n/a, which is a fact about the data
    # rather than about the contract." It is a fact about the contract, and this is it.
    resolvable_fraction: NotRequired[float]
    silence: Silence
    partition: dict[str, object]
    census: dict[str, object]
    findings: list["Finding"]
    # The scope module's own record, not a second copy of it. This file declared the
    # same two fields under another name, and the copy typed each scoped-out path as a
    # mapping of strings to strings where the original names its two fields.
    bucketed: BucketedPaths
    details: str


class FileRead(TypedDict):
    """What the classifier made of one file, and what it walked to get there.

    `visited` and `judged` are the two halves the old coverage number could not separate.
    `visited` is every declaration the enumerators reached, admitted or declined; `judged` is
    the subset that yielded a state key which then reached a verdict. A declaration in neither
    is one nothing looked at, and only that is a gap in the reading.

    They are sets of census-vocabulary sites, not counts, because the comparison happens
    against the census's own per-file site set and a count cannot be intersected."""
    findings: list["Finding"]
    visited: set[Site]
    judged: set[Site]
