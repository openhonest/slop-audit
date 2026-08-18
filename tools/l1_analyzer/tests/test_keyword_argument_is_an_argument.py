"""A keyword argument is an argument (L1.18b, Python).

`f(self.url)` and `f(url=self.url)` hand the same value to the same callee. The first
reached the argument row; the second did not, because Python's grammar puts a
`keyword_argument` node between the value and the argument list, and the row tests the
reference's immediate parent. So the keyword spelling fell to the unmodeled-construct
terminal and was reported as a shape nobody had taught.

C# already solves the identical problem the same way. Its grammar wraps EVERY argument
in an `argument` node, and `argument` sits in its `passthrough_types`, so the flow
walker steps through the wrapper and reaches the argument row above. Python's
`keyword_argument` was simply missing from that list.

The assertions here are at the REFERENCE level rather than on the finding's verdict,
which is deliberate. On a small fixture the attribute-level false-positive filter clears
`self.url` to neutral for an unrelated reason, so a finding-level assertion would pass
whether or not the row works and would be measuring the filter. The first draft of this
file did exactly that and looked green before the fix.

Eleven of psf/requests' forty-five silent states are this one shape.
"""

import pathlib
import tempfile

from tree_sitter import Parser

from l1_analyzer import state_bounds
from l1_analyzer.indicators import LANG_CFG


def _reach(src: str, line: int) -> dict:
    parser = Parser()
    parser.language = LANG_CFG["python"]["language"]
    root = parser.parse(src.encode()).root_node
    spec = state_bounds.LANG_SPEC["python"]
    closed = state_bounds._collect_closed_sets(root)
    found = []

    def walk(node):
        if node.type == "attribute" and state_bounds._text(node) == "self.url" \
                and node.start_point[0] + 1 == line:
            found.append(state_bounds._categorize(node, spec, closed, None))
        for child in node.children:
            walk(child)

    walk(root)
    assert found, f"no self.url reference on line {line}"
    return found[0]


_HEAD = "class S:\n    def __init__(self):\n        self.url = ''\n    def go(self, p):\n"


def test_a_keyword_argument_reaches_the_same_row_as_a_positional_one():
    positional = _reach(_HEAD + "        p.prepare(self.url)\n", 5)
    keyword = _reach(_HEAD + "        p.prepare(url=self.url)\n", 5)
    # Both are undecided here, and honestly so: `p.prepare` is a method on a parameter and
    # nobody has modelled it. What must match is HOW they are read. Before the fix the
    # keyword form said `unmodeled_construct`, which is our missing rule; now both say
    # `external_boundary`, which is their unknown callee. An earlier draft asserted no
    # silence at all and would have demanded the analyzer resolve an arbitrary callee.
    assert positional["silence"] == "external_boundary"
    assert keyword["silence"] == positional["silence"]
    assert keyword["construct"] == ""


def test_the_same_holds_when_the_call_spans_lines():
    keyword = _reach(_HEAD + "        p.prepare(\n            url=self.url,\n        )\n", 6)
    assert keyword["construct"] == ""


def test_a_default_value_in_a_signature_is_not_swept_up():
    """The guard. `keyword_argument` is a call site. A default in a DEFINITION is a
    `default_parameter`, a different node, and must not start passing through."""
    src = "class S:\n    def __init__(self):\n        self.url = ''\n    def go(self, u=1):\n        return u\n"
    parser = Parser()
    parser.language = LANG_CFG["python"]["language"]
    root = parser.parse(src.encode()).root_node
    assert "default_parameter" not in state_bounds.LANG_SPEC["python"]["passthrough_types"]
