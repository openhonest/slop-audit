"""The boundary declaration, and the one thing it must not do.

Honest Code rule 4 puts I/O at the boundary. The clause that checks it INFERS the boundary
from the call graph, and that inference cannot tell a function which is only I/O from
business logic that has swallowed a read. This is how a function says which it is.

The declaration is honest only after the decision has been lifted out. In `c_trace` that
meant `make_target_in` deciding from text and `_read_makefile` doing nothing but obtaining
it. The split came first; the decorator records that it happened.
"""

import ast
import pathlib

from l1_analyzer import boundary, c_trace
from l1_analyzer import honest_code_rules as rules


def test_the_declaration_changes_nothing_at_runtime():
    """A declaration that altered behaviour would be a wrapper rather than a statement, and
    it would put a frame between a reader and the thing they came to read."""
    def read(path):
        return path

    assert boundary.boundary(read) is read


def test_a_declared_function_still_behaves_exactly_as_written():
    @boundary.boundary
    def double(n: int) -> int:
        return n * 2

    assert double(21) == 42
    assert double.__name__ == "double"


def _findings(module) -> list[dict]:
    source = pathlib.Path(module.__file__).read_text()
    return rules.io_below_the_boundary({
        "path": pathlib.Path(module.__file__).name, "language": "python", "text": source,
        "tree": ast.parse(source), "readable": True, "unreadable_reason": ""})


def test_the_makefile_reader_is_declared_and_the_clause_reads_it():
    assert [f["symbol"] for f in _findings(c_trace)] == []


def test_the_split_happened_before_the_declaration_was_added():
    """The decision lives in a function that touches nothing, which is what makes the
    declaration on the reader honest rather than a stamp."""
    assert c_trace.make_target_in("test:\n\t./t\n") == ("test", "")
    source = pathlib.Path(c_trace.__file__).read_text()
    decider = source.split("def make_target_in")[1].split("\ndef ")[0]
    assert "read_text" not in decider and "open(" not in decider


def test_an_undeclared_reader_is_still_reported():
    """The decorator has to be a declaration rather than a blanket. A second reader added
    without one still fires."""
    source = ("from l1_analyzer.boundary import boundary\n\n\n"
              "@boundary\ndef declared(path):\n    return path.read_text()\n\n\n"
              "def undeclared(path):\n    return path.read_text()\n\n\n"
              "def run(path):\n    return declared(path), undeclared(path)\n")
    found = rules.io_below_the_boundary({
        "path": "m.py", "language": "python", "text": source,
        "tree": ast.parse(source), "readable": True, "unreadable_reason": ""})
    assert [f["symbol"] for f in found] == ["undeclared"]
