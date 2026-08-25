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
from l1_analyzer import honest_code_python_rules as python_rules


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
    """The findings that survive as violations. A declared boundary is emitted and marked
    withheld rather than dropped, so a consumer can count real suppressions."""
    source = pathlib.Path(module.__file__).read_text()
    found = python_rules.io_below_the_boundary({
        "path": pathlib.Path(module.__file__).name, "language": "python", "text": source,
        "tree": ast.parse(source), "readable": True, "unreadable_reason": ""}) or []
    return [f for f in found if f["withheld_by"] == ""]


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
    found = python_rules.io_below_the_boundary({
        "path": "m.py", "language": "python", "text": source,
        "tree": ast.parse(source), "readable": True, "unreadable_reason": ""}) or []
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == ["undeclared"]
    assert [f["symbol"] for f in found if f["withheld_by"] == "declaration"] == ["declared"]


# ---------------------------------------------------------------------------
# The shared edge
#
# Three tracers each read one small file and decided something from what it said. Splitting
# them one at a time was producing the same declared reader three times, which is the shape
# clause 1 names: three functions that are one function. It is one function here, in the
# module that declares what a boundary is.
# ---------------------------------------------------------------------------

def test_the_shared_reader_hands_back_text():
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "f"
        path.write_text("18.17.0\n")
        assert boundary.text_or_empty(path) == "18.17.0\n"


def test_an_absent_or_unreadable_file_is_the_same_answer():
    """Both mean the caller has nothing to read, and none of the three callers has anything
    different to do about the two."""
    assert boundary.text_or_empty(pathlib.Path("/no/such/file")) == ""


def test_the_shared_reader_is_declared():
    source = pathlib.Path(boundary.__file__).read_text()
    declared = source.split("def text_or_empty")[0]
    assert declared.rstrip().endswith("@boundary")


# ---------------------------------------------------------------------------
# Every declaration in the package, checked against what a declaration claims
# ---------------------------------------------------------------------------

def test_every_declared_boundary_actually_obtains_something():
    """A declaration says "this function is an edge". A function that reaches nothing
    outside the process is not an edge, and the decorator on it is a stamp.

    This cannot tell a declaration from a suppression in general, which the module's own
    docstring says. It can tell one thing: whether the function under the decorator touches
    the world at all. Every one that does not is a suppression by construction."""
    import re

    # The whole repository, not this package. Three scripts outside it spell `boundary`
    # themselves, because they sit beside this package rather than inside it, and the first
    # version of this check globbed the package alone so it never saw them. A check narrower
    # than its subject reports on what nobody wrote.
    repo = pathlib.Path(boundary.__file__).parent.parent.parent.parent
    reaches = ("read_text", "read_bytes", "write_text", "write_bytes", "open(",
               "subprocess", "Popen", "rglob", "which(", "stat(", "is_file", "is_dir",
               "exists(", "iterdir", "TemporaryDirectory")
    stamps = []
    for path in sorted(repo.rglob("*.py")):
        if any(part in (".venv", "node_modules", "__pycache__") for part in path.parts):
            continue
        source = path.read_text(errors="replace")
        for match in re.finditer(r"@boundary\n(?:@[\w.()=]+\n)*def (\w+)", source):
            body = source[match.end():].split("\ndef ")[0]
            if not any(reach in body for reach in reaches):
                stamps.append(f"{path.name}:{match.group(1)}")
    assert stamps == [], f"declared as edges and reach nothing outside the process: {stamps}"
