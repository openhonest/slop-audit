"""Every principle this instrument names is a principle that exists, by its current number.

The Honest Code principles lived in twelve copies holding twenty-two entries between them.
No copy held them all, four numbered them and the rest used headings, and the numbering
differed between the numbered ones. So a citation like "rule 4" resolved to different
principles depending on which copy a reader had, and this package cited eight of them that
way.

They became one repository, this package moved its citations to names, and the names moved
too: three were improved on 2026-08-25 and every citation of them broke at once. The canon
answered that. Each principle now carries a number that never changes, a withdrawn number
is retired rather than reused, and the document says in its own words to cite the number
and not the title.

So each clause carries the number of the principle it measures, and this file checks the
number and the title against the canonical document. The number has to be one the document
defines. The title has to be the one the document currently gives that number, so a
retitling upstream fails here and gets carried into the clause, rather than quietly
unhooking the clause from the principle.

Skipped rather than failed when the document is absent. A checkout without the sibling
repository is an ordinary state, and failing there would report a missing neighbour as a
defect in this code.
"""

import pathlib
import re

import pytest
from l1_analyzer.honest_code import CLAUSES

_CANON = (pathlib.Path(__file__).resolve().parents[4]
          / "honest-code-principles" / "honest-code-principles.md")
_PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "l1_analyzer"

_HEADING = re.compile(r"^## (P\d+) (.+)$")


def boundary(fn):
    """Mark this file's one edge, and change nothing about it.

    Spelled here rather than imported. This is a test module, and its edge is its own."""
    return fn


@boundary
def _canon_text() -> str:
    return _CANON.read_text()


def _principles(document: str) -> dict[str, str]:
    """Number to title, as the canonical document gives them today."""
    found = (_HEADING.match(line) for line in document.splitlines())
    return {m.group(1): m.group(2).strip() for m in found if m}


_canon_is_missing = pytest.mark.skipif(
    not _CANON.is_file(), reason="the principles repository is not checked out here")


@pytest.fixture
def principles() -> dict[str, str]:
    """The document, read once per test. The fixture is where the disk is touched."""
    return _principles(_canon_text())


@_canon_is_missing
def test_the_document_still_numbers_its_principles(principles):
    """The parse this whole file rests on. Without it every other test here reads an empty
    document and passes, which is the failure this instrument reports in other people's
    code."""
    assert len(principles) >= 23


@_canon_is_missing
@pytest.mark.parametrize("clause", CLAUSES, ids=lambda c: c["code"])
def test_every_clause_cites_a_principle_the_document_defines(clause, principles):
    assert clause["principle"] in principles, (
        f"{clause['code']} measures {clause['principle']}, which the canonical document does "
        "not define; the principle was withdrawn and its number retired")


@_canon_is_missing
@pytest.mark.parametrize("clause", CLAUSES, ids=lambda c: c["code"])
def test_every_clause_carries_the_title_that_number_has_today(clause, principles):
    """A clause's name is what a reader compares against the document, so it has to be the
    document's words for the number the clause cites.

    Two clauses measure halves of one principle and say so in a parenthetical after the
    title, which is why a name may be the title plus a bracket and nothing else. Typed Dicts
    Over Classes was folded into Pure Functions Over Methods upstream; this instrument still
    measures the two halves separately, because a class that only holds data and a method
    that should be a function are different findings with different remedies."""
    title = principles[clause["principle"]]
    assert clause["name"] == title or clause["name"].startswith(title + " ("), (
        f"{clause['code']} calls {clause['principle']} {clause['name']!r} and the document "
        f"calls it {title!r}; carry the new title over")


@_canon_is_missing
def test_the_principles_no_clause_measures_are_named_here(principles):
    """Four principles have no clause. Naming them in a test rather than leaving the gap
    silent, so the next person to read this knows what the instrument does not cover.

    It was three on 2026-08-28 and is two. References Resolve Statically and Type
    Declarations Over Imperative Validation both got clauses that day, which is why the
    conformity share stopped being a share of twenty rules over twenty-two principles.

    Both are left deliberately, and the canon says why for each.

    P19, Constrain AI with Data Shape Contracts, is marked as mitigating a failure rather
    than eliminating one, so a clause here would report a repository for declining a
    mitigation, which is a different thing from breaking a rule.

    P21, Watch the Test Fail First, was added to the canon on 2026-08-30 and this test
    caught it the same day, which is what reading the document rather than a copy of it is
    for. It cannot be checked at all, and the canon says so in its own words: the evidence
    is destroyed by the act of passing. A test that failed and now passes is byte-identical
    to a test that never failed, so nothing reading the final state can tell the two apart.
    It is the ordering rule that makes One Gherkin Per Function worth having: clause 15
    proves a scenario exists for every function, and the red run proves the scenario would
    notice the function breaking. Neither is enough alone.

    The list moves because the document moves, which is why this reads the document.

    P24, A Fault Travels in the Return Value, and P25, A Fault Says What To Do Differently,
    arrived on 2026-09-07 and this test caught them the same day, which is the third time
    the document has moved under this file in two days and the third time reading it rather
    than a copy of it is what said so.

    P24 is partly reachable and the reachable part is already clause 8, which refuses a
    caught exception in a function that is not an edge. What makes P24 more than clause 8 is
    the chain: a caller's return type has to carry a fault its callee can produce, all the
    way out to the boundary. Nothing here follows that chain, and the canon says nothing
    anywhere does.

    P25 cannot be checked by anything and the canon says so in its own words. Whether a
    message names an action the reader can take is a judgment about the reader rather than a
    property of the text. A rule that guessed at it would report a fault message as slop for
    being short.

    A conformity share over the clauses that exist cannot see a principle nobody wrote a
    clause for, which is the same failure this instrument reports in other people's code."""
    measured = {c["principle"] for c in CLAUSES}
    assert set(principles) - measured == {"P19", "P21", "P24", "P25"}


@_canon_is_missing
def test_no_source_file_cites_a_principle_by_a_number_without_its_letter():
    """"Rule 4" is the citation form that broke, and it still resolves to nothing: the canon
    numbers its principles P01 through P23 and this package numbers its own clauses L1.21.1
    through L1.21.22. A bare number belongs to neither scheme and reads as both."""
    cited = []
    for path in sorted(_PACKAGE.glob("*.py")):
        for n, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(r"\b[Rr]ules? \d+\b", line):
                cited.append(f"{path.name}:{n}")
    assert cited == [], f"cite the principle as Pnn: {cited}"


@_canon_is_missing
def test_every_principle_number_written_anywhere_in_the_package_exists(principles):
    """The clause table is not the only place a principle gets cited. Prose cites them too,
    and prose is where the eight broken citations of 2026-08-25 were sitting."""
    known = set(principles)
    unknown = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        for n, line in enumerate(path.read_text().splitlines(), start=1):
            for number in re.findall(r"\bP\d\d\b", line):
                if number not in known:
                    unknown.append(f"{path.name}:{n}: {number}")
    assert unknown == [], f"these principle numbers are not in the document: {unknown}"
