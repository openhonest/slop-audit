"""One request carries as many gaps as fit, rather than one gap each.

The sweep batched the expensive part and left the cheap part alone. `render_batch`'s own
docstring says why the compile is batched: N tests, one compile, which is what makes a
whole-codebase sweep cost about one build per module instead of one per gap. The ask stayed
at one gap per request, so a 176-module sweep sent 425 requests before a single line was
compiled.

Named on 2026-09-06. It is the same move one step earlier, and it removes rather than manages
the rate-limit problem a worker pool would have created.

The budget is derived rather than picked. The session auditing turso measured every
proof-ready function in turso/core with this package's own reader: 6,136 functions across 257
modules, median 376 characters, p90 2,750, p99 12,955, largest 145,605. Packed per module,
the three largest functions of the median module come to 4,904 characters and of the worst
module to 167,712. Every module at once is 3.5 million, which is about five times what fits.

So the tail is the design problem rather than the average, and the rule for the gap that does
not fit is the part worth testing. It goes alone rather than being dropped: a sweep that
silently skipped its largest functions would report the same number over a smaller question.

Characters, not tokens. Counting tokens needs the model's own tokenizer and we do not have
one, so a token budget here would be a guess wearing a measurement's name. The ratio in
turso's corpus was about 3.5 characters per token.
"""

from __future__ import annotations

import pytest
from l1_analyzer import coverage_prove


def _gap(name: str, size: int) -> dict:
    return {"function": name, "function_source": "x" * size, "kind": "if",
            "line": 1, "return_type": "bool"}


def test_several_small_gaps_travel_in_one_request():
    packs = coverage_prove.pack_gaps([_gap(f"f{i}", 100) for i in range(20)], budget=10_000)
    assert len(packs) == 1
    assert len(packs[0]) == 20


def test_a_pack_stops_at_the_budget_rather_than_running_over():
    packs = coverage_prove.pack_gaps([_gap(f"f{i}", 400) for i in range(10)], budget=1_000)
    assert [len(p) for p in packs] == [2, 2, 2, 2, 2]


def test_every_gap_reaches_a_pack():
    """The property that matters more than the packing. A gap that fell out of the packing
    would be a gap nobody attempted while the ceiling counted it as spent."""
    gaps = [_gap(f"f{i}", size) for i, size in enumerate([10, 5_000, 30, 900_000, 70])]
    packed = [g for pack in coverage_prove.pack_gaps(gaps, budget=1_000) for g in pack]
    assert [g["function"] for g in packed] == [g["function"] for g in gaps]


def test_a_gap_larger_than_the_whole_budget_travels_alone():
    """The tail. turso's largest proof-ready function is 145,605 characters, which is over
    any budget that leaves room for answers. It is sent by itself rather than dropped,
    because a sweep that skipped its largest functions would report the same number over a
    smaller question."""
    gaps = [_gap("small", 10), _gap("enormous", 900_000), _gap("also_small", 10)]
    packs = coverage_prove.pack_gaps(gaps, budget=1_000)
    alone = [p for p in packs if len(p) == 1 and p[0]["function"] == "enormous"]
    assert alone, [[g["function"] for g in p] for p in packs]


def test_an_empty_list_packs_into_nothing():
    assert coverage_prove.pack_gaps([], budget=1_000) == []


@pytest.mark.parametrize("budget", [0, -1])
def test_a_budget_of_nothing_is_refused_rather_than_packing_every_gap_alone(budget):
    """A budget of zero would put every gap in its own request, which is the shape this
    replaces, arrived at silently. It raises instead."""
    with pytest.raises(ValueError):
        coverage_prove.pack_gaps([_gap("f", 10)], budget=budget)


def test_the_sweep_asks_once_per_pack_rather_than_once_per_gap():
    """The wall-clock claim, at the function that spends it. Forty gaps across four modules
    are one request, not forty.

    Driven through `_proposals_for` rather than the whole sweep, because the sweep needs
    cargo, a coverage build and a key, and the thing under test here is only how many times
    the model is asked. The proposer is handed in rather than replaced inside the module,
    which is what this package requires of every collaborator and has its own test for."""
    asked: list[int] = []

    def fake_propose_many(gaps):
        asked.append(len(gaps))
        return [{"body": "let result = f();\nassert!(result, \"m\");",
                 "explanation": "e"} for _ in gaps]

    work = [(f"src/m{m}.rs", [_gap(f"f{m}_{i}", 200) for i in range(10)]) for m in range(4)]
    answers = coverage_prove._proposals_for(work, fake_propose_many)
    assert asked == [40], asked
    assert len(answers) == 40
    assert all(a is not None for a in answers.values())


def test_every_gap_gets_its_own_answer_back():
    """The property the packing must not break. Two gaps in one function can carry equal
    contents, so the map is keyed by identity and each gap must find the answer written for
    it rather than a neighbour's."""
    def fake_propose_many(gaps):
        return [{"body": "let result = f();\nassert!(result, \"m\");",
                 "explanation": g["function"]} for g in gaps]

    work = [("src/m.rs", [_gap("same", 10), _gap("same", 10)])]
    gaps = work[0][1]
    answers = coverage_prove._proposals_for(work, fake_propose_many)
    assert len(answers) == 2, "two gaps with equal contents collapsed into one entry"
    assert all(answers[id(g)] is not None for g in gaps)
