"""Three guarded divisions that substitute a flattering constant (dogfood).

`vacuity.check` names ten paths in this package. THREE LOOKED LIKE the shape fixed for
L1.4, L1.5, L1.16, L1.17, L1.18 and absolute_paths on 2026-08-18. One was:

    dead_code.analyze      percent = ... if production_loc else 0.0     -> 0.0 Healthy

It divides by a line count that can be zero and answers "no dead code" over a
measurement that never happened. Fixed: it returns n/a naming the reason.

The other two are FALSE POSITIVES and this file records why, because the reason is not
obvious and I changed both before finding out:

    state_bounds.classify  resolvable = ... if total else 1.0
    silence_summary        "fraction": ... if total else 0.0

Zero state is not an unread repository. A codebase with no mutable state by design IS
fully resolved and has nothing unread, vacuously and correctly, and `report._meter_ran`
reads a numeric resolvable fraction as its signal that the meter ran at all. The failure
those constants appear to permit, a repository the classifier never read, is caught by
the CENSUS, which compares what was declared against what was admitted. Replacing either
constant with None broke three census tests that say exactly that.

So the fix for two of the three findings is a comment on the line explaining why the
constant is right, and this test asserting the behaviour those census tests depend on.
"""

import pathlib
import tempfile

from l1_analyzer import dead_code, state_bounds, state_partition


def test_dead_code_over_zero_production_lines_does_not_publish_healthy():
    """A tree of empty source files: parseable, in scope, and no lines to measure."""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "a.py").write_text("")
        (p / "b.py").write_text("")
        r = dead_code.analyze(p, "python")
    assert not (r["value"] == 0.0 and r["band"] == "Healthy"), \
        "0.0 Healthy over a tree with no production lines to measure"
    assert r["band"] == "n/a", r.get("details")


def test_zero_state_still_reads_as_fully_resolved_and_fully_read():
    """The two false positives, asserted so a later reader does not 'fix' them as I did.
    Both constants are what the census tests depend on."""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "a.py").write_text("def f(x):\n    return x + 1\n")   # no state at all
        r = state_bounds.classify(p, "python")
    assert r["counts"] == {"neutral": 0, "promiscuous": 0, "unresolved": 0}
    assert r["resolvable_fraction"] == 1.0, "report._meter_ran needs a number here"
    assert state_partition.silence_summary([], 0)["fraction"] == 0.0
