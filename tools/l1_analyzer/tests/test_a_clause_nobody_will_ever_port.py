"""A clause we owe nobody, counted among the ones we owe.

Strangler Pattern for Migration decides nothing, by its nature rather than by the reach of
this reader: it is a property of how a migration is sequenced over weeks, and no file carries
the sequence of the work that produced it. The table already says so, marking what it decides
as nothing, and its checker raises rather than returning a quiet None.

What it also says, because every unported clause said it, is that it reads Python's own
parser. So a JavaScript repository was told this clause "is unported, not silent", which
promises work that will never be done and cannot be. The two sentences are about different
things and only one of them is true here.
"""

from pathlib import Path

from l1_analyzer import honest_code

_NOTHING = "nothing"


def _js_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.js").write_text("function build(a) { return a + 1 }\n")
    return tmp_path


def _clause(rule: int) -> dict:
    return next(c for c in honest_code.CLAUSES if c["rule"] == rule)


def test_a_clause_that_decides_nothing_does_not_claim_to_read_a_parser():
    """It reads no file at all, so naming a reader states a capability it never uses."""
    assert _clause(17)["decides"] == _NOTHING
    assert _clause(17)["reads"] == _NOTHING


def test_it_is_not_counted_among_the_clauses_we_owe_a_port(tmp_path):
    """The port finished on 2026-08-27 and no clause reads Python's parser any more, so the
    sentence about unported clauses is absent rather than wrong. The assertion is the rule
    behind it: this clause is never one of them, whatever that count becomes."""
    details = honest_code.analyze(_js_repo(tmp_path), "javascript")["details"]
    unported = [c for c in honest_code.CLAUSES if c["reads"] == "python-ast"]
    assert _clause(17) not in unported
    if not unported:
        assert "read Python's own parser" not in details, details


def test_the_report_says_why_it_will_never_be_decided(tmp_path):
    """A reader seeing it listed and never explained learns nothing. It is named as a
    clause nothing can decide, which is a different answer from one we have not written."""
    details = honest_code.analyze(_js_repo(tmp_path), "javascript")["details"]
    assert "Strangler Pattern for Migration" in details
    assert "no file carries" in details


def test_every_clause_declaring_nothing_says_the_same_thing():
    """The rule rather than the instance, so a second such clause cannot be added with a
    reader named that it will never use."""
    for clause in honest_code.CLAUSES:
        if clause["decides"] == _NOTHING:
            assert clause["reads"] == _NOTHING, clause["code"]
