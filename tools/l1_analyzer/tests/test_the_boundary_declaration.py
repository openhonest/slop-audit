"""The boundary declaration, and the one thing it must not do.

Honest Code rule 4 puts I/O at the boundary. The clause that checks it INFERS the boundary
from the call graph, and that inference cannot tell a function which is only I/O from
business logic that has swallowed a read. This is how a function says which it is.

The declaration is honest only after the decision has been lifted out. In `c_trace` that
meant `make_target_in` deciding from text and `_read_makefile` doing nothing but obtaining
it. The split came first; the decorator records that it happened.
"""

import pathlib

from l1_analyzer import boundary, c_trace
from l1_analyzer import honest_code_edges as edges
from l1_analyzer import honest_code_read as read


def test_the_declaration_changes_nothing_at_runtime():
    """A declaration that altered behaviour would be a wrapper rather than a statement, and
    it would put a frame between a reader and the thing they came to read."""
    def read(path):
        return path

    assert boundary.boundary(read) is read


def test_a_declared_function_still_behaves_exactly_as_written():
    """Applied as a call rather than with decorator syntax, deliberately.

    Clause 4 reports a declaration on a function that obtains nothing, because such a
    declaration states an edge that is not there. This fixture doubles a number, so written
    with `@boundary` it was exactly that, and the clause found it here first."""
    def double(n: int) -> int:
        return n * 2

    declared = boundary.boundary(double)
    assert declared(21) == 42
    assert declared.__name__ == "double"


def _findings(module) -> list[dict]:
    """The findings that survive as violations. A declared boundary is emitted and marked
    withheld rather than dropped, so a consumer can count real suppressions."""
    source = pathlib.Path(module.__file__).read_text()
    found = edges.io_below_the_boundary(read.read_tree(source, "python")) or []
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
    found = edges.io_below_the_boundary(read.read_tree(source, "python")) or []
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
    """A declaration says "this function is an edge". A function reaching nothing outside
    the process is not one, and the decorator on it states an edge that is not there.

    This walked the tree itself until the check moved into clause 4, where it belongs: it
    is a finding about anyone's code, not a fact about this repository. What is left here
    asserts the clause covers this repository and reports nothing, so the invariant stays
    named in the suite without a second implementation of it drifting from the first."""


    repo = pathlib.Path(boundary.__file__).parent.parent.parent.parent
    stamps = []
    for path in sorted(repo.rglob("*.py")):
        if any(part in (".venv", "node_modules", "__pycache__") for part in path.parts):
            continue
        text = path.read_text(errors="replace")
        if "@boundary" not in text:
            continue
        # No guard around the parse. tree-sitter accepts anything and reports the trouble
        # as error nodes rather than raising, so the guard here caught nothing and cost a
        # second parse of every file that has a declaration.
        found = edges.io_below_the_boundary(read.read_tree(text, "python")) or []
        stamps += [f"{path.name}:{f['symbol']}" for f in found
                   if "states an edge that is not there" in f["detail"]]
    assert stamps == [], f"declared as edges and reach nothing outside the process: {stamps}"


# ---------------------------------------------------------------------------
# Reaching an edge through one that already said so
#
# An adopter measured 14 clause-4 sites and eight had one cause: a function whose whole job
# is catching what a boundary raised. It calls a function carrying the decorator, and this
# reader looked only at its own body, saw no I/O, and reported it.
#
# That was a real conflict between two checkers rather than a preference. honest-check
# grants a boundary three privileges, one of them catching exceptions, and refuses to let a
# non-boundary catch at all. So a function that only catches must carry the marker there and
# must not carry it here, and no marking satisfies both. The adopter left all fourteen alone
# rather than trade one complaint for the other, which was the right call.
#
# Following the call closes it without loosening what counts as I/O, because the callee is
# exactly the thing that made the claim.
# ---------------------------------------------------------------------------

CATCHES_FOR_AN_EDGE = '''
from l1_analyzer.boundary import boundary


@boundary
def _read_rows(path):
    return path.read_text().splitlines()


@boundary
def rows_or_none(path):
    try:
        return _read_rows(path)
    except OSError:
        return None


def run(path):
    return rows_or_none(path)
'''


def test_a_function_that_calls_a_declared_boundary_is_reaching_an_edge():
    """The eight. Its own body holds no I/O and the function it calls said it is an edge."""
    found = [f for f in _findings_of(CATCHES_FOR_AN_EDGE)
             if "states an edge that is not there" in f["detail"]]
    assert found == [], found


def test_a_function_calling_an_undeclared_helper_is_not_reaching_an_edge_through_it():
    """The other direction. Only a declaration carries the claim: following any call would
    make every caller of anything an edge."""
    source = CATCHES_FOR_AN_EDGE.replace("@boundary\ndef _read_rows", "def _read_rows")
    found = [f["symbol"] for f in _findings_of(source)
             if "states an edge that is not there" in f["detail"]]
    assert found == ["rows_or_none"], found


def test_the_call_is_followed_one_step_and_not_transitively():
    """One step, because a declaration is a claim about the function carrying it. Following
    further would let a declaration three calls away excuse a function that reaches nothing,
    which is the suppression this check exists to catch."""
    source = ("from l1_analyzer.boundary import boundary\n\n\n"
              "@boundary\ndef _edge(p):\n    return p.read_text()\n\n\n"
              "def _middle(p):\n    return _edge(p)\n\n\n"
              "@boundary\ndef outer(p):\n    return _middle(p)\n\n\n"
              "def run(p):\n    return outer(p)\n")
    found = [f["symbol"] for f in _findings_of(source)
             if "states an edge that is not there" in f["detail"]]
    assert found == ["outer"], found


def _findings_of(source: str) -> list[dict]:


    return edges.io_below_the_boundary(read.read_tree(source, "python")) or []


# ---------------------------------------------------------------------------
# A function a table holds is called
#
# The adopter's second finding, and the sharper of the two. Clause 4 builds its call graph
# from calls by name, so a function that is only ever a value in a dispatch table is reached
# by nothing as far as this reader can see. It was silent in both directions on such a
# function: not reported for the I/O it performs, and not reported for the declaration it
# was missing.
#
# The irony is the point. This instrument tells people to replace if/elif chains with
# dispatch tables, and that adopter did it deliberately, so a large share of their functions
# are reached exactly this way. A reader following named calls only is blind to most of the
# interior of a codebase written the way clause 1 asks for.
#
# A name appearing as a value in a map literal is a reference to that function. It is the
# same static fact as a named call, spelled differently, and nothing dynamic is followed.
# ---------------------------------------------------------------------------

THROUGH_A_TABLE = '''
def _deliver(db, now):
    logger.info("delivering")
    return db


def _nothing(db, now):
    return db


ON_SHUTDOWN = {True: _deliver, False: _nothing}


def shutdown(db, now):
    return ON_SHUTDOWN[bool(db)](db, now)
'''


def test_a_function_a_table_holds_counts_as_called():
    """It performs I/O and something reaches it, so the clause has both halves it needs."""
    found = [f["symbol"] for f in _findings_of(THROUGH_A_TABLE) if f["withheld_by"] == ""]
    assert found == ["_deliver"], found


def test_a_function_nothing_reaches_at_all_is_still_left_alone():
    """The exemption that makes the clause usable stays. A function no call and no table
    reaches may be the entry point, and clause 4 says so."""
    source = THROUGH_A_TABLE.replace("ON_SHUTDOWN = {True: _deliver, False: _nothing}", "")
    assert [f for f in _findings_of(source) if f["withheld_by"] == ""] == []


def test_a_table_holding_a_string_names_no_function():
    """Only a bare name is a reference. A table of strings is data about names, not a call
    graph edge, and reading it as one would reach anything a table happens to mention."""
    source = ("def _deliver(db, now):\n    logger.info('x')\n    return db\n\n\n"
              "LABELS = {True: '_deliver'}\n\n\ndef shutdown(db, now):\n    return LABELS\n")
    assert [f for f in _findings_of(source) if f["withheld_by"] == ""] == []
