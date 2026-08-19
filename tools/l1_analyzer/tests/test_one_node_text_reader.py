"""Reading a node's text is one function, not five.

Five modules defined `_text`. Three were byte-identical to ts_nodes.text, which already
existed and which most of the package already imports. A fourth differed only by declaring
a narrower parameter type over the same body. The remaining two, in python_facets and
rust_facets, are identical to each other and are a different function: they slice the
source bytes rather than reading node.text, and return nothing for an absent node.

Decoding a tree-sitter node is a grammar fact, not a judgement, so copies of it cannot
disagree honestly, only drift. The two distinct readers now live in ts_nodes and everyone
asks for the one they mean by name.
"""

import pathlib
import re

from l1_analyzer import (
    dead_code_defs,
    mutable_state,
    python_facets,
    rust_facets,
    thread_surface,
    ts_nodes,
)

_PKG = pathlib.Path(ts_nodes.__file__).parent


def test_the_package_defines_node_text_once_per_distinct_question():
    defs = re.findall(r"^def _?(?:text|slice_text)\(", "\n".join(p.read_text() for p in _PKG.glob("*.py")),
                      re.MULTILINE)
    assert len(defs) == 2, f"{len(defs)} node-text readers; two questions, so two functions"


def test_every_reader_of_a_nodes_own_text_asks_the_same_function():
    for module in (dead_code_defs, mutable_state, thread_surface):
        assert module._text is ts_nodes.text, f"{module.__name__} holds a separate copy"


def test_both_facet_readers_ask_the_same_slicing_function():
    assert python_facets._text is ts_nodes.slice_text
    assert rust_facets._text is ts_nodes.slice_text


def test_the_two_readers_answer_differently_for_an_absent_node():
    """Why they are two functions and not one. The node reader says no text; the slicing
    reader says no node, which its callers test for."""
    assert ts_nodes.text(None) == ""
    assert ts_nodes.slice_text(b"anything", None) is None
