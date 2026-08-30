"""What a reading of a repository's state looks like when it comes back.

Three records, split out of the reader that produces them when that file crossed a thousand
lines and this tool's own god-file rule failed the commit. They are the shapes a caller
holds rather than the walk that fills them, and the card reads eight of their fields.

Every one of those reads was an assumption until these were written down: the reading was
handed over as a mapping of anything to anything, so nothing could say whether the findings
were a list or the counts a table.
"""

from typing import TYPE_CHECKING, TypedDict

from l1_analyzer.state_sites import Site

if TYPE_CHECKING:
    from l1_analyzer.state_bounds import Finding


class Bucketed(TypedDict):
    """What was scoped out of the state reading, and why. Counts by reason, plus the paths
    a reader most needs to see."""

    counts: dict[str, int]
    paths: list[dict[str, str]]


class StateReading(TypedDict):
    """L1.18b's whole reading of a repository's state.

    Written out because the card reads eight of these fields and every read was an
    assumption: the result was handed over as a mapping of anything to anything, so nothing
    could say whether `findings` was a list or `counts` a table."""

    value: float | int | str
    band: str
    counts: dict[str, int]
    coverage: object
    resolvable_fraction: float
    silence: dict[str, object]
    partition: dict[str, object]
    census: dict[str, object]
    findings: list["Finding"]
    bucketed: Bucketed
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
