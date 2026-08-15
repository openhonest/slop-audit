"""Coverage of the census: how many declaration sites the classifier's reader actually reached.

The number this file exists to pin used to be `admitted_fraction`, and it divided two counts
of different things. `declared` is DECLARATION SITES, counted by the census walk. `admitted`
is `len(findings)`, which counts pieces of state that reached a verdict. One TypedDict of five
fields beside one module-level `cache = {}` reported `declared 6, admitted 1, fraction 0.167`,
and nothing had been missed: the reader walked all six declarations and correctly concluded
that five of them hold no mutable state. A codebase that uses more typed records scored worse
for being no less well read, and the figure was published on every card and quoted as coverage.

Two numbers replace it, because there were always two questions:

  visited_fraction  - of the sites declared here, how many did the reader reach
  judged_fraction   - of the sites it reached, how many carried state that got a verdict

A site the reader reached and declined is not a gap. A site it never reached is. Only the
first number can be outrun by nothing: it asks about one declaration rather than about a
category, so a new code shape cannot answer it by construction the way `reachable` can.
"""

from __future__ import annotations

from l1_analyzer import state_bounds

# Five record fields and one module binding. Every one of the six is a declaration the
# Python reader walks: the class-body rule visits each TypedDict field and declines it
# because nothing references it, and the module scan visits `cache` and admits it.
FIVE_FIELD_RECORD = (
    "from typing import TypedDict\n"
    "\n"
    "\n"
    "class Row(TypedDict):\n"
    "    name: str\n"
    "    count: int\n"
    "    total: int\n"
    "    label: str\n"
    "    flag: bool\n"
    "\n"
    "\n"
    "cache = {}\n"
    "\n"
    "\n"
    "def put(k, v):\n"
    "    cache[k] = v\n"
)


def test_a_record_the_reader_read_in_full_does_not_score_as_unread(tmp_path):
    """The measured defect, pinned. Six sites declared, six sites walked, one verdict."""
    (tmp_path / "m.py").write_text(FIVE_FIELD_RECORD)
    census = state_bounds.classify(tmp_path, "python")["census"]
    assert census["declared"] == 6
    assert census["visited"] == 6, "the reader walked every one of the six declarations"
    assert census["visited_fraction"] == 1.0
    # And the second question, kept separate rather than folded into the first: one of the
    # six sites carried state that reached a verdict, and five held nothing to judge.
    assert census["judged"] == 1
    assert census["judged_fraction"] == round(1 / 6, 3)


def test_the_fraction_that_compared_unlike_counts_is_gone(tmp_path):
    """`admitted_fraction` divided findings by declaration sites. A repaired-looking name
    over the same mismatch would be worse than no number, so the key is removed rather than
    recomputed, and `admitted` stays beside it as the raw count it always was."""
    (tmp_path / "m.py").write_text(FIVE_FIELD_RECORD)
    census = state_bounds.classify(tmp_path, "python")["census"]
    assert "admitted_fraction" not in census
    assert census["admitted"] == 1
