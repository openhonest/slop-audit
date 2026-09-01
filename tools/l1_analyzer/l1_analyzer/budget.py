"""How much the next unit of work may spend.

One rule, and it was two spellings. `live_sweep.share` wrote it as
`max(0, min(cap, ceiling - spent))` and `prove_coverage_repo` wrote it as a slice,
`module_gaps[:max(0, max_attempts - attempted)]` after an earlier `[:cap_per_module]`.

The package's duplicate-rule guard compares parse trees and cannot see that: a slice and a
`min` are different trees for the same arithmetic. It was still two places for a budget to
drift, and this budget is what decides how much money a run spends.

Extracting it also reaches it. `prove_coverage_repo` runs a coverage build and walks a
tree, so it is a boundary and most of its lines are untested by construction; the ceiling
logic was sitting inside them. This rule is pure, so it belongs outside.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TypeVar

# The gap a sweep hands to a model. This rule counts them and never looks inside one, so
# the two sweeps' different gap records stay their own business.
G = TypeVar("G")


def allowance(cap: int, ceiling: int, spent: int) -> int:
    """What the next unit gets: its own cap, or whatever the run has left, whichever is
    smaller, and never negative.

    Two bounds because they answer different questions. The cap is how much any one unit
    may take, which stops a single large module or repository consuming everything. The
    ceiling is what the whole run may spend, which is what an operator authorises. Five per
    unit over forty units is two hundred attempts, and only the ceiling stops that."""
    return max(0, min(cap, ceiling - spent))


def gaps_to_attempt(measured: Mapping[str, frozenset[int]], sources: Mapping[str, str],
                    gaps_of: Callable[[str, frozenset[int]], list[G]],
                    cap_per_module: int, ceiling: int
                    ) -> tuple[list[tuple[str, list[G]]], int, int]:
    """Which gaps a sweep will spend on, how many it found, and how many it will try.

    The second half of the same question the allowance above answers, and it was written
    twice for the same reason that one was: the Rust sweep and the Python sweep each had a
    copy. On 2026-08-31 the copy showed what a copy does. The per-module cap truncated
    before the count of what was found, in both, so a sweep with a cap of one over forty
    modules reported forty gaps located and forty attempted when it had found six hundred.
    That is the unmeasured-read-as-clean shape wearing a budget for a disguise, and fixing
    it in one module left it standing in the other.

    What the two sweeps do WITH a gap genuinely differs and stays unmerged, with the
    measurement recorded in `coverage_prove`. Choosing which gaps to hand over is not that.

    A gap is located whether or not either bound lets the sweep try it, because the report
    says how many were found as well as how many were attempted, and a sweep reporting three
    of three attempted looks complete when it found forty. A module the bounds left nothing
    for is not in the work, since counting it would report work on a file the sweep walked
    past. The order is settled, so a run that stops at its ceiling stops where the run
    before it stopped and the two reports compare.

    The sources are handed in as text and the gap reader is a parameter, so this never learns
    which language it is choosing for and does no I/O of its own. A file the edge did not
    read is one the caller decided not to hand over."""
    work: list[tuple[str, list[G]]] = []
    located = 0
    attempted = 0
    for relpath, lines in sorted(measured.items()):
        source = sources.get(relpath)
        if source is None:
            continue
        module_gaps = gaps_of(source, lines)
        located += len(module_gaps)
        gaps = module_gaps[:allowance(cap_per_module, ceiling, attempted)]
        attempted += len(gaps)
        if gaps:
            work.append((relpath, gaps))
    return work, located, attempted
