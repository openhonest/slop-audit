"""This repository carries no unreferenced definition (L1.12, dogfood).

The instrument found five in our own tree and nothing acted on them for three days. A
tool that measures dead code and keeps its own is not credible, and the accumulation
indicators say the same thing from the other side: 64,783 lines added against 9,780
deleted across this repository's history.

This asserts the invariant rather than the five names, so it holds after the next
deletion and fails on the next accumulation. It is the deletion counterpart to
`scripts/self_audit.py`, which ratchets the panel: that one stops the reading getting
worse, this one keeps one indicator at zero.

`test_only` is deliberately NOT asserted. A definition reached only from the test tree
is reported separately by design, and this repository has two, both in `vacuity.py`.
That is its own debt with its own bead, and folding it in here would let a real finding
hide behind an argument about categories.
"""

import pathlib

from l1_analyzer import dead_code

REPO = pathlib.Path(__file__).resolve().parents[3]


def test_no_definition_in_this_repository_is_unreferenced():
    r = dead_code.analyze(REPO, "python")
    named = [f"{f['file']}:{f['line']} {f['name']}" for f in (r.get("findings") or [])]
    assert not named, "dead code in our own tree:\n  " + "\n  ".join(named)


def test_the_indicator_can_still_see_this_repository():
    """The guard. A band of n/a would make the assertion above vacuous, and n/a is what
    the indicator returns when it cannot read a repository at all."""
    r = dead_code.analyze(REPO, "python")
    assert r["band"] != "n/a", r.get("details")
    assert r["counts"]["definitions"] > 100, "too few definitions read to be measuring this repo"
