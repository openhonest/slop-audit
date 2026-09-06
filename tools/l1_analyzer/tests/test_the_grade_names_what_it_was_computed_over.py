"""The quoted percentage must carry its own denominator.

The grade sentence is the one line that leaves the report. It said "95% of its state is
finitely testable" and the share is over the state that reached a verdict, with everything
undecided dropped from both halves. That is the right arithmetic and it makes the sentence
unable to tell two very different readings apart.

Demonstrated on 2026-09-06 by the session auditing turso, on one codebase read by two builds
of this tool:

                        finitely testable   unbounded   undecided   quoted
  before the fixes                    973          53       2,187      95%
  after them                        1,659          88       1,479      95%

708 locations moved out of silence, the testable count rose by seventy per cent, the unbounded
count rose from 53 to 88, and the figure a reader quotes did not move to the percentage point:
973 over 1,026 is 94.83, and 1,659 over 1,747 is 94.96.

The arithmetic stays. State nobody read is not evidence about the code, so folding it into
the denominator would punish a repository for this instrument's blindness. What changes is
that the sentence now says what it was computed over, so the denominator travels with the
number instead of sitting three paragraphs below it where a quotation leaves it behind.
"""

from __future__ import annotations

from l1_analyzer import card

_BAND = {"value": 0, "band": "Healthy", "details": "d"}
_PANEL = {k: _BAND for k in ("L1.18", "L1.17", "L1.15", "L1.10", "L1.11", "L1.9", "L1.16")}


def _state(neutral: int, promiscuous: int, unresolved: int) -> dict:
    total = neutral + promiscuous + unresolved
    return {
        "verdict": "promiscuous" if promiscuous else "neutral",
        "counts": {"neutral": neutral, "promiscuous": promiscuous, "unresolved": unresolved},
        "coverage": {v: {"observe_only": 0, "drives_decision": 0}
                     for v in ("neutral", "promiscuous", "unresolved")},
        "silence": {"count": 0, "fraction": 0.0, "sites": []},
        "resolvable_fraction": 0.5, "findings": [],
        "bucketed": {"counts": {}, "paths": []},
        "census": {"declared": total, "visited": total, "unread_kinds": {}},
    }


def _markdown(state: dict) -> str:
    return card.card_markdown(card.build_card(
        "x", "rust", {**_PANEL, "L1.18b": state}, ran_tests=False, analyzer_version="test"))


def test_the_grade_sentence_says_how_much_state_reached_a_verdict():
    printed = _markdown(_state(neutral=1659, promiscuous=88, unresolved=1479))
    grade_line = next(line for line in printed.splitlines() if line.startswith("**Grade:"))
    assert "1,747" in grade_line and "3,226" in grade_line, grade_line


def test_two_readings_that_quote_the_same_percentage_do_not_read_alike():
    """The whole argument. Both of these quote 95 per cent and one of them read twice as
    much of the codebase."""
    before = _markdown(_state(neutral=973, promiscuous=53, unresolved=2187))
    after = _markdown(_state(neutral=1659, promiscuous=88, unresolved=1479))
    line_of = lambda md: next(x for x in md.splitlines() if x.startswith("**Grade:"))
    assert line_of(before) != line_of(after), line_of(before)


def test_a_reading_with_nothing_undecided_says_nothing_extra():
    """The other direction. A repository this instrument read all of has one number and no
    denominator worth printing, and a clause about undecided state that is always there
    stops being read."""
    grade_line = next(line for line in _markdown(_state(40, 10, 0)).splitlines()
                      if line.startswith("**Grade:"))
    assert "reached a verdict" not in grade_line, grade_line
