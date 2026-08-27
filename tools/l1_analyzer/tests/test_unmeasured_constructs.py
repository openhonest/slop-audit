"""A construct the categoriser has no rule for must be reported unmeasured, never clean.

`_categorize` used to end by falling off the bottom of its own table into `_flow`, and
`_flow` used to end by falling off the bottom of its table into `output()`. `output()` is a
VERDICT: it says the value is compositional, reaches no decision, and costs no tests. So a
construct nobody had written a rule for was not merely unhandled, it was cleared. A walrus
in a condition, a `match` subject, a comprehension source and a starred unpack all came out
neutral with an empty silence field, which reads to an adopter as "we looked and there is
nothing here" rather than "we have no rule for this".

Measured before the change, over eleven repositories, the terminal arm decided 55 percent of
all references (Python 56, Java 52, C# 62, C 31) and touched at least one reference of
53 to 100 percent of the state that reached a published verdict. So it was not a corner.

Three properties are asserted here, and they are the design:

  1. NO PATH OFF THE END OF THE TABLE. The last row is a handler, so an unhandled construct
     is unmeasured by construction rather than by whoever remembered to check.
  2. THE HANDLER CANNOT REACH A VERDICT. It takes two node types and returns undecided. It
     is given nothing it could conclude from, which is the apophatic rule enforced at the
     dispatch instead of at the renderer.
  3. THE SILENCE IS OURS, NOT THE ADOPTER'S. A construct we have not taught the reader is
     our backlog, the same class of fact as an unmodeled callee, and it is reported under
     its own reason so the backlog can be read off the by_reason counts.

Pure assertions over fixtures written to tmp_path, no mocks (Honest Code Rule 10).
"""

from __future__ import annotations

import pytest
from l1_analyzer import state_bounds, state_partition

# Four constructs the table has no row for, each holding one piece of instance state that
# a reader would call obviously benign. Every one of them came back neutral before.
WALRUS = (
    "class Gate:\n"
    "    def __init__(self):\n"
    "        self.token = None\n"
    "    def issue(self, t):\n"
    "        self.token = t\n"
    "    def check(self):\n"
    "        if (found := self.token) is not None:\n"
    "            return found\n"
    "        return None\n"
)
MATCH = (
    "class Router:\n"
    "    def __init__(self):\n"
    "        self.mode = 'fast'\n"
    "    def flip(self, m):\n"
    "        self.mode = m\n"
    "    def route(self):\n"
    "        match self.mode:\n"
    "            case 'fast':\n"
    "                return 1\n"
    "            case _:\n"
    "                return 0\n"
)
COMPREHENSION = (
    "class Bag:\n"
    "    def __init__(self):\n"
    "        self.items = []\n"
    "    def add(self, x):\n"
    "        self.items.append(x)\n"
    "    def big(self):\n"
    "        return [x for x in self.items if x > 3]\n"
)
STARRED_UNPACK = (
    "class Head:\n"
    "    def __init__(self):\n"
    "        self.row = []\n"
    "    def fill(self, r):\n"
    "        self.row = r\n"
    "    def tail(self):\n"
    "        first, *rest = self.row\n"
    "        return rest\n"
)


def _classify(tmp_path, src: str) -> dict:
    (tmp_path / "app.py").write_text(src)
    return state_bounds.classify(tmp_path, "python")


@pytest.mark.parametrize("name,source", [
    ("walrus", WALRUS),
    ("comprehension", COMPREHENSION), ("starred_unpack", STARRED_UNPACK),
])
def test_a_construct_with_no_dispatch_row_is_unmeasured_rather_than_clean(tmp_path, name, source):
    """Property one. The verdict is unresolved and the reason names the construct, because
    the reader has no rule for how this shape consumes the value. Reporting neutral here is
    the exact failure the silence index exists to stop, moved one layer earlier."""
    result = _classify(tmp_path, source)
    assert result["counts"][state_bounds.UNRESOLVED] == 1, f"{name} was decided by something"
    assert result["counts"][state_bounds.NEUTRAL] == 0
    site = result["silence"]["sites"][0]
    assert site["reason"] == state_partition.UNMODELED_CONSTRUCT
    assert site["construct"], "the site must name the construct that has no rule"


def test_the_handler_is_given_nothing_it_could_conclude_from():
    """Property two. It takes two node-type strings, so there is no tree, no spec and no
    closed-set table in scope: no verdict is reachable from what it holds. A handler that
    could see the value would eventually be asked to guess about it."""
    reach = state_partition.unmeasured("named_expression", "if_statement")
    assert reach["kind"] == state_partition.UNDECIDED
    assert reach["silence"] == state_partition.UNMODELED_CONSTRUCT
    assert reach["construct"] == "named_expression in if_statement"
    assert reach["classes"] == 0


def test_the_unmeasured_construct_is_our_backlog_and_counts_under_its_own_reason(tmp_path):
    """Property three. `by_reason` carries every reason key whether or not it fired, so a
    reader can tell a zero from an omission; the new reason has to be in that set or the
    count would be invisible to anyone reading the JSON."""
    # WALRUS rather than MATCH. The match statement had no rule when this was written and
    # has one now, so it stopped being an example of the backlog and became an example of
    # the backlog shrinking. The property is about a construct nobody has taught the reader,
    # and the walrus is still one.
    result = _classify(tmp_path, WALRUS)
    by_reason = result["silence"]["by_reason"]
    assert state_partition.UNMODELED_CONSTRUCT in by_reason
    assert by_reason[state_partition.UNMODELED_CONSTRUCT] == 1
    assert by_reason[state_partition.EXTERNAL_BOUNDARY] == 0


def test_a_construct_that_does_have_a_rule_is_still_decided_by_it(tmp_path):
    """The guard on the change. Making the last row a handler must not swallow the rows
    above it: `if self.flag:` is a two-class truthiness split and stays one, and a state
    only ever written stays a write. A total table that reported everything unmeasured
    would satisfy the three properties above and measure nothing."""
    result = _classify(tmp_path, (
        "class Flags:\n"
        "    def __init__(self):\n"
        "        self.flag = False\n"
        "    def arm(self):\n"
        "        self.flag = True\n"
        "    def act(self):\n"
        "        if self.flag:\n"
        "            return 1\n"
        "        return 0\n"
    ))
    assert result["counts"][state_bounds.NEUTRAL] == 1
    assert result["counts"][state_bounds.UNRESOLVED] == 0
    finding = result["findings"][0]
    assert finding["drives_decision"] is True
    assert finding["partition"]["classes"] == 2


def test_the_match_statement_has_a_rule_now_and_is_no_longer_backlog(tmp_path):
    """`match` was in this list until the switch vocabulary was filled for Python.

    It is the one row here that produces CLASSES rather than merely reading a construct: a
    state value used as a match subject selects one arm, and the arms are countable from the
    tree. Java, C#, Go and Rust have had that rule since it was written; Python and
    JavaScript were left empty, so the modern spelling went unmeasured in both readers that
    consume the table.

    Kept as a test rather than a deletion, because a construct leaving the backlog is the
    thing this file is about and the count moving the other way is worth failing on."""
    result = _classify(tmp_path, MATCH)
    assert result["counts"][state_bounds.UNRESOLVED] == 0, "match is measured now"
    finding = result["findings"][0]
    # Three: the two literal cases and the fall-through, which is a class of its own.
    assert finding["partition"]["classes"] == 3, finding["partition"]
    assert finding["partition"]["counted"] is True
    assert finding["silence"] == ""
