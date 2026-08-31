"""A declared edge obtains data or emits it. One that does both is business logic.

The decorator says a function is where this package meets the world. Nothing held it to
that: a function performing any I/O at all satisfied the existing half of the clause, so the
decorator on a two-hundred-line orchestrator carrying fifteen branches and one `open()` read
as clean. Its own module docstring names the gap: "applying it to a function that still
decides things is a suppression wearing a declaration's name, and nothing here can tell the
two apart."

The signature tells them apart, which is the thing that needed noticing. An edge that
obtains takes locators, which is to say where to look and how long to wait, and hands back
what it found. An edge that emits takes the data and hands back whether it landed. A
function taking domain data and handing back different domain data is neither: it received
something, decided about it, and returned the decision.

No framework list and no threshold. Two rules that were tried first and are recorded here
because they look right and are not: "a boundary that decides" convicts half of this package,
including a function choosing between two places one file lives, and "an edge is a leaf of the
call graph" convicts the same half, including an edge that asks two small questions before
reading. Both measure size. This measures direction.
"""

from l1_analyzer import honest_code

_OBTAINS = '''
from pathlib import Path


@boundary
def config_text(path: Path, timeout: float) -> str:
    return path.read_text()
'''

_EMITS = '''
from pathlib import Path


@boundary
def write_report(rows: list[Row], path: str) -> bool:
    Path(path).write_text("\\n".join(rows))
    return True
'''

_TRANSFORMS = '''
from pathlib import Path


@boundary
def live_rows(rows: list[Row], path: Path) -> list[Row]:
    known = set(path.read_text().split())
    return [r for r in rows if r.name in known]
'''


def _clause_four(source: str) -> list[dict]:
    assessed = honest_code.assess_file_text(source, "m.py")
    return next(c for c in assessed["clauses"] if c["code"] == "L1.21.4")["findings"]


def test_an_edge_that_obtains_is_clean():
    assert _clause_four(_OBTAINS) == []


def test_an_edge_that_emits_is_clean():
    """It takes the data and hands back whether it landed. A status is not domain data, and
    reading it as such would report every writer in every repository."""
    assert _clause_four(_EMITS) == []


def test_an_edge_that_takes_data_and_returns_data_is_reported():
    found = _clause_four(_TRANSFORMS)
    assert [f["symbol"] for f in found] == ["live_rows"], found


def test_the_finding_says_which_half_of_the_signature_is_wrong():
    """A reader has to know whether to split the function or take the declaration off, and
    the two are different repairs."""
    detail = _clause_four(_TRANSFORMS)[0]
    assert "obtain" in detail["detail"] or "emit" in detail["detail"]
    assert detail["instead"].strip()


def test_a_function_with_no_declaration_is_not_judged_on_its_signature():
    """The rule is about a claim, so it applies only where a claim was made. Every other
    function in a repository takes data and returns data, which is what a function is."""
    assert _clause_four(_TRANSFORMS.replace("@boundary\n", "")) == []
