"""One list of what reaches outside the process, and this reader agrees with it.

Two standards score the same clause, P03, I/O at the Boundary, and each kept its own
hand-written list of call names. The lists disagreed and both were wrong. Ours named socket,
tempfile and logging as whole modules, so it demanded a boundary declaration on functions
that convert an address, ask where the temporary directory is, or fetch a logger, none of
which reach anything. Theirs was missing print, input and three database connect calls, so
it called true declarations false.

Each side found the other's fault by reading the other's source in conversation. That worked
twice and detects nothing on its own, which is why the list now lives in the principles
repository as reaches-outside-the-process.json, with test vectors, and each tool proves it
passes them. Neither tool imports the other.

This file is our proof. Every vector is rendered as a function that declares itself an edge
and makes that one call, and the clause has to agree: a call that reaches outside leaves a
true declaration alone, and a call that reaches nothing makes the declaration false and gets
reported.

Skipped rather than failed when the document is absent. A checkout without the sibling
repository is an ordinary state.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from l1_analyzer import honest_code_edges as edges
from l1_analyzer import honest_code_read as read

_CANON = (pathlib.Path(__file__).resolve().parents[4]
          / "honest-code-principles" / "reaches-outside-the-process.json")

_canon_is_missing = pytest.mark.skipif(
    not _CANON.is_file(), reason="the principles repository is not checked out here")


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _document() -> dict[str, object]:
    return dict(json.loads(_CANON.read_text()))


def _vectors() -> list[dict[str, object]]:
    return list(_document()["vectors"]) if _CANON.is_file() else []


def _names(question: str) -> list[str]:
    """One of the document's two name lists, or nothing at all where the document is absent.

    Read at collection time, which is why the absent case answers with a list rather than
    letting the skip mark handle it: a parametrize argument is evaluated before any mark
    is."""
    return list(_document()["python"][question]) if _CANON.is_file() else []


# How each vector is spelled as Python. The list names calls; a reader reads source, and
# somebody has to write one as the other. Kept as a table rather than generated from the
# name, because generating it would be guessing at the receiver, and the receiver is what
# the last vector turns on.
_AS_SOURCE = {
    "pathlib.Path.read_text": "pathlib.Path(name).read_text()",
    "socket.socket": "socket.socket()",
    "socket.gethostbyname": "socket.gethostbyname(name)",
    "asyncpg.connect": "asyncpg.connect(name)",
    "aiosqlite.connect": "aiosqlite.connect(name)",
    "print": "print(name)",
    "input": "input()",
    "logging.info": "logging.info(name)",
    "tempfile.NamedTemporaryFile": "tempfile.NamedTemporaryFile()",
    "subprocess.run": "subprocess.run(name)",
    "requests.get": "requests.get(name)",
    "socket.inet_aton": "socket.inet_aton(name)",
    "tempfile.gettempdir": "tempfile.gettempdir()",
    "logging.getLogger": "logging.getLogger(name)",
    "os.path.join": "os.path.join(name, name)",
    "os.getenv": "os.getenv(name)",
    "TABLE.get": "TABLE.get(name)",
}

_DECORATOR = "from l1_analyzer.boundary import boundary\n\n\n"


def _read(call: str):
    source = _DECORATOR + f"@boundary\ndef edge(name, TABLE):\n    return {call}\n"
    return read.read_tree(source, "python", "")


# The document asks two questions about a name and this reader answers each with its own
# function. One row per question, because the two were written as two functions that differed
# only in which reader they called, and this file's own clause 1 said so.
_ASKS = {
    "reaches_outside": read.io_calls_in,
    "nondeterministic": read.non_deterministic_in,
}


def _says(question: str, call: str) -> bool:
    """What this reader answers about one call, for one of the document's two questions."""
    parsed = _read(call)
    return bool(_ASKS[question](parsed["root"], parsed["spec"], parsed["raw"]))


def _declaration_called_false(call: str) -> list[dict[str, object]]:
    """Every finding saying the declaration on this function is not true.

    A different question from the two above, and keeping them apart matters. Reading an
    environment variable does not leave the process, and a boundary declaration on a
    function that reads one is still not false, because the other checker in this family
    requires the marker exactly there."""
    return [f for f in (edges.io_below_the_boundary(_read(call)) or [])
            if "states an edge that is not there" in f["detail"]]


@_canon_is_missing
def test_every_vector_in_the_document_is_spelled_as_source_here():
    """The table above has to cover the document, not a copy of it made on some earlier day.
    A vector added upstream fails here until somebody writes it as Python, which is the
    point: a list nobody renders is a list nobody checks."""
    unrendered = sorted({str(v["call"]) for v in _vectors()} - set(_AS_SOURCE))
    assert unrendered == [], f"these vectors have no Python spelling here: {unrendered}"


@_canon_is_missing
@pytest.mark.parametrize("vector", _vectors(), ids=lambda v: str(v["id"]))
def test_this_reader_gives_the_documents_answer(vector):
    call = _AS_SOURCE[str(vector["call"])]
    assert _says("reaches_outside", call) == vector["reaches_outside"], (
        f"{vector['call']}: the document says reaches_outside is {vector['reaches_outside']} "
        f"and this reader disagrees. {vector.get('note', '')}")


@_canon_is_missing
@pytest.mark.parametrize("vector", [v for v in _vectors() if not v["reaches_outside"]],
                         ids=lambda v: str(v["id"]))
def test_a_declaration_on_a_call_that_reaches_nothing_is_reported(vector):
    """The other half, and the half an author feels. A call that reaches nothing outside
    the process makes a boundary declaration on it a false statement.

    Except where the call is also on the non-determinism list. Reading an environment
    variable reaches nothing and still earns the marker, because the other checker in this
    family requires it there, and an author told to delete it would satisfy one gate by
    failing the other."""
    call = _AS_SOURCE[str(vector["call"])]
    if _says("nondeterministic", call):
        pytest.skip("also on the non-determinism list, which earns the marker on its own")
    assert _declaration_called_false(call), vector["call"]


def _as_python(name: str) -> str:
    """One name from the document, spelled as a call.

    The document writes a name, sometimes with a wildcard. A reader reads source, so the
    wildcards have to become something: `requests.*` becomes a call on requests that this
    file invented, which is the point of a wildcard, and `os.spawn*` becomes one of the eight
    the standard library actually has."""
    if name.endswith(".*"):
        return name[:-2] + ".some_call(name)"
    if name.endswith("*"):
        return name[:-1] + "l(name)"
    if name.startswith("pathlib.Path."):
        return "pathlib.Path(name)." + name.rsplit(".", 1)[-1] + "()"
    return name + "(name)"


def _every_name() -> list[tuple[str, str]]:
    """Both of the document's lists, each name paired with the question it answers."""
    return [(question, name) for question in _ASKS for name in _names(question)]


@_canon_is_missing
@pytest.mark.parametrize("question,name", _every_name(), ids=lambda v: v)
def test_this_reader_answers_the_document_for_every_name_it_lists(question, name):
    """The whole of both lists, one name at a time, not only the seventeen vectors. Sixteen
    of the seventy-seven outward names and thirty of the thirty-nine non-deterministic ones
    were names this reader had never heard of on 2026-09-05, and every one of them is a true
    boundary declaration this reader would have called false.

    The two questions are different and the answer to each is yes for its own list. Reaching
    outside the process is what the clause reports on. Non-determinism is not, and this
    clause is not becoming a rule about it: the names are known so that a declaration on a
    function reading one is not called false, because the other checker in this family
    requires the marker exactly there and an author told to delete it would satisfy one gate
    by failing the other.

    Four of the non-deterministic names are read rather than called: os.environ, sys.argv,
    sys.path and sys.version. They are matched on the dotted text as written, so the call
    this test spells them as is read the same way an ordinary attribute access is."""
    assert _says(question, _as_python(name)), f"{question}: {name}"
