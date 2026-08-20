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


def allowance(cap: int, ceiling: int, spent: int) -> int:
    """What the next unit gets: its own cap, or whatever the run has left, whichever is
    smaller, and never negative.

    Two bounds because they answer different questions. The cap is how much any one unit
    may take, which stops a single large module or repository consuming everything. The
    ceiling is what the whole run may spend, which is what an operator authorises. Five per
    unit over forty units is two hundred attempts, and only the ceiling stops that."""
    return max(0, min(cap, ceiling - spent))
