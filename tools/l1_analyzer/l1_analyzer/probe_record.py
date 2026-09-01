"""How a plugin watching a suite from inside it hands its record back.

Two plugins do this. One records every file the suite opens, one records what the audited
module's functions did. They are different probes with nothing else in common, and the last
twenty lines of each were the same twenty lines.

Those twenty lines carried the same defect in both, found and fixed on the same day. Each
defaulted an absent record to empty, so a run whose configure never installed its hook wrote
an empty list, which says the suite opened no files or the module has no runtime properties.
Both readers treat a MISSING file as a run they could not watch. Opposite answers, and the
same bytes.

The distinction this module exists to keep is three-way, and it is the whole reading:

  no file          the run could not be watched
  an empty list    the run was watched and saw nothing
  a list           what it saw

The two probes differ in which environment variable names their destination and in whether
their record needs sorting before it is written. Both are arguments.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Iterable
from typing import TypeVar

from l1_analyzer.boundary import boundary

# What a probe recorded. One keeps paths in a set, the other keeps call records in a list,
# and neither is read here: this module counts nothing and looks inside nothing.
Recorded = TypeVar("Recorded")


def hand_back(config: object, stash: str, destination: str,
              prepare: Callable[[Collection[Recorded]], list[Recorded]]) -> bool:
    """Write what the run recorded, and say whether it wrote anything.

    Nothing at all when the record is absent, because the reader treats a missing file as a
    run it could not watch and a run whose configure never installed its hook watched
    nothing. Nothing when no destination was named either: both plugins are registered by
    name, so they load in runs that are not audits, and writing to a path left over from a
    previous run would overwrite one answer with another.

    `prepare` is how this record wants to be written. One probe keeps a set of paths and
    sorts them, so two runs over one suite give the same file and a comparison between them
    reports no changes nobody made. The other keeps calls in the order they happened."""
    seen = getattr(config, stash, None)
    if seen is None:
        return False
    return write_record(prepare(seen), destination)


@boundary
def write_record(record: Iterable[object], destination: str) -> bool:
    """Write a prepared record where the caller asked, and say whether it did.

    The one line of I/O the two plugins shared. An empty record still writes, because an
    empty list is a measured answer and it has to reach the reader as one."""
    if not destination:
        return False
    with open(destination, "w") as handle:
        json.dump(record, handle)
    return True
