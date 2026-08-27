"""Seven bare numbers where a reason belongs.

Running the check on a JavaScript file reports "Not decided (7): L1.21.10, L1.21.11, ...".
It is true and a reader cannot act on it. Those seven read Python's own parser, so on any
other language they cannot reach the code at all, and the report never says so. A reader is
left to guess between a clause that found nothing, a clause that could not be applied to
their language, and a clause that is not written yet.

The bound is the claim's other half, and this one had only the claim. It also names the
clauses by number, which is the citation this project refuses everywhere else: a number
tells a reader nothing about what was not checked.
"""

from pathlib import Path

from l1_analyzer import honest_code

_JS = ("class Store {\n  constructor() { this.items = [] }\n"
       "  add(x) { this.items.push(x) }\n}\n"
       "function build(a) { return a + 1 }\n")


def _js_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.js").write_text(_JS)
    return tmp_path


def test_the_undecided_clauses_are_named_not_numbered(tmp_path):
    details = honest_code.analyze(_js_repo(tmp_path), "javascript")["details"]
    assert "Trust the Contract in the Interior" in details


def test_the_reason_they_were_not_decided_is_given(tmp_path):
    details = honest_code.analyze(_js_repo(tmp_path), "javascript")["details"]
    assert "Python" in details
    assert "javascript" in details.lower()


def test_a_python_repository_is_told_no_such_thing(tmp_path):
    """The reason holds only where the reader cannot reach the language. On Python those
    seven decide, so a note about them would be furniture."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "app.py").write_text("def build(a):\n    return a + 1\n")
    details = honest_code.analyze(tmp_path, "python")["details"]
    assert "Python's own parser" not in details, details


def test_a_ported_clause_the_language_cannot_raise_is_explained_too(tmp_path):
    """The second reason a clause goes undecided, and it appeared the moment the port
    started. Trust the Contract in the Interior reads the shared vocabulary now, so it is
    not unported, and JavaScript declares no parameter types, so the question it asks cannot
    arise. A reader was shown six names, five explained and one left bare, which is the
    shape of an answer that stopped halfway."""
    details = honest_code.analyze(_js_repo(tmp_path), "javascript")["details"]
    assert "cannot arise" in details


def test_the_two_reasons_are_not_run_together(tmp_path):
    """They send a reader to different places. An unported clause is work for us; a clause
    the language cannot raise is nothing to do at all, and counting them as one number would
    make our backlog look like their problem."""
    details = honest_code.analyze(_js_repo(tmp_path), "javascript")["details"]
    unported = details.split("read Python's own parser")[0].split(". ")[-1].strip()
    inapplicable = details.split("cannot arise")[0].split(". ")[-1].strip()
    assert unported.split()[0] != inapplicable.split()[0]


def test_the_score_counts_only_the_clauses_that_decided(tmp_path):
    """A sentence is added to the prose and nothing is added to the measurement. An
    undecided clause stays undecided, and it stays out of the denominator.

    The count falls as clauses are ported. It was seven when this file was written and is
    six now that Context Managers Over Instance State reads the shared vocabulary, so the
    assertion is that every undecided clause is one that reads Python's parser, not that
    there are still exactly seven of them."""
    result = honest_code.analyze(_js_repo(tmp_path), "javascript")
    assert result["undecided"], "a JavaScript repository still has undecided clauses"
    assert 0 < result["value"] <= 100
