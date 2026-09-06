"""A sweep that was asked for and could not run must say so on the card.

The card read the proofs a sweep RETAINED and nothing else. A sweep whose precondition
failed retains nothing, so the card it produced was byte-identical to a run that never asked
for a sweep at all. A reader could not tell a suite with no gaps from a sweep that never
happened.

Reported on 2026-09-06 by the session auditing turso. They ran the whole repository with
--prove-coverage-repo for two hours, it exited 0, and the report matched the plain static
panel to the byte. No model was ever called. The only trace anywhere was one clause inside
the L1.19 footnote: "coverage produced no data (cargo exit 101)". One of that workspace's
test targets links a library with a relative path that cargo-llvm-cov's redirected target
directory breaks, and one unbuildable target fails the whole workspace build.

Their words for it, and they are right: a tool built to name silent failure failed silently.

Both prove loops have the shape. Each already returns its own sentence on the way out, and
neither sentence reached a reader.
"""

from __future__ import annotations

from l1_analyzer import card

_BAND = {"value": 0, "band": "Healthy", "details": "d"}
_PANEL = {k: _BAND for k in ("L1.18", "L1.17", "L1.15", "L1.10", "L1.11", "L1.9", "L1.16")}

# What each loop hands back when its precondition failed. Both are real: the first is the
# sentence turso's run produced, and the second is what the concurrency loop returns with no
# key in the environment.
_COVERAGE_REFUSED = {
    "retained": [],
    "attempted": 0,
    "detail": ("coverage not measured: coverage produced no data (cargo exit 101): "
               "error: cannot find -lturso_sqlite3"),
}
_CONCURRENCY_REFUSED = {
    "verdict": "not run",
    "detail": "no proofs generated: no ANTHROPIC_API_KEY in the environment",
}


def _markdown(panel: dict) -> str:
    return card.card_markdown(
        card.build_card("x", "rust", panel, ran_tests=True, analyzer_version="test"))


def test_a_coverage_sweep_that_could_not_run_is_named_on_the_card():
    """The reported case, at the surface a reader opens."""
    printed = _markdown({**_PANEL, "coverage_proofs": _COVERAGE_REFUSED})
    assert "cannot find -lturso_sqlite3" in printed, printed[-1500:]


def test_a_concurrency_sweep_that_could_not_run_is_named_on_the_card():
    """The same hole in the other loop. One rule for both, or the next one to grow a
    refusal path is silent again."""
    printed = _markdown({**_PANEL, "proofs": _CONCURRENCY_REFUSED})
    assert "no ANTHROPIC_API_KEY" in printed, printed[-1500:]


def test_a_run_that_never_asked_for_a_sweep_says_nothing_about_one():
    """The other direction, and the reason this is not simply a line printed always. A
    static run asked for no sweep, and a card announcing that a sweep it was never asked to
    do produced nothing would be noise wearing a finding's clothes."""
    printed = _markdown(dict(_PANEL))
    assert "prove loop" not in printed.lower()


def test_a_sweep_that_retained_nothing_and_hit_no_gaps_still_says_it_ran():
    """The quiet case between the two. A sweep that ran, found no proof-ready gaps and kept
    nothing is a real result and a different one from a sweep that never started. It was
    indistinguishable from both."""
    printed = _markdown({**_PANEL, "coverage_proofs": {
        "retained": [], "attempted": 0, "modules": 12,
        "detail": "no proof-ready uncovered branches located across 12 modules"}})
    assert "no proof-ready uncovered branches located across 12 modules" in printed


def test_the_card_renders_a_refused_concurrency_run_rather_than_falling_over():
    """Worse than silence, and found while fixing it. The concurrency loop's own record says
    its detail is present only on a run that refused and its records only on one that ran,
    and the card subscripted the records. So on any machine without a key in the
    environment, asking for the loop did not produce a quiet card: it raised KeyError and
    produced no card at all."""
    printed = _markdown({**_PANEL, "proofs": {"verdict": "not run", "detail": "no key"}})
    assert "concurrency" in printed
