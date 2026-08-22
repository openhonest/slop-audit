"""What a boundary declaration suppressed, reported rather than left to be inferred.

An adopter added 82 boundary markers across ten modules. A consumer counting every file
that gained one reported that a third of measured units had been silenced rather than
fixed. Measured instead of sampled, 20 of the 82 sit on a function that does any I/O at
all: the other 62 are dispatch pairs where one arm reaches the database and the other
deliberately does not, so marking both keeps the pair symmetric and silences nothing.

The inference was wrong three times in four, and it could not be right from outside,
because a suppression that suppresses nothing is invisible unless the analyzer says so.

It matters beyond tidiness. A conformance rate carries a suppression column precisely
because silencing is the cheap route to a clean score, one decorator against a rewrite. If
that column counts markers that withheld nothing, it punishes the architectural declaration
the marker exists to encourage, and a package scores worse for correctly declaring its
database layer than for leaving it undeclared.
"""

import ast

from l1_analyzer import honest_code


def _module(text: str) -> dict:
    return {"path": "m.py", "language": "python", "text": text,
            "tree": ast.parse(text), "readable": True, "unreadable_reason": ""}


WITHHELD = ("from l1_analyzer.boundary import boundary\n\n\n"
            "@boundary\ndef load(path):\n    return path.read_text()\n\n\n"
            "def total(path):\n    return load(path)\n")

# A marker on a function the clause would never have spoken about. Both arms of a dispatch
# pair, one of which deliberately touches nothing, is the shape that produced the wrong
# count in the field.
WITHHELD_NOTHING = ("from l1_analyzer.boundary import boundary\n\n\n"
                    "@boundary\ndef copy_the_rows(db):\n    return db.execute('...')\n\n\n"
                    "@boundary\ndef copy_no_rows(db):\n    return 0\n")


def test_a_declaration_that_withheld_a_finding_says_so():
    assessed = honest_code.assess(honest_code.read_source_text(WITHHELD, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.4")
    assert clause["findings"] == []
    assert len(clause["declared"]) == 1
    assert clause["declared"][0]["symbol"] == "load"
    assert clause["declared"][0]["line"] == 5


def test_the_record_says_a_declaration_rather_than_a_comment_withheld_it():
    """The two suppressions are different acts and a reader has to be able to tell them
    apart. A comment carries a written reason; a declaration carries an architectural
    claim."""
    assessed = honest_code.assess(honest_code.read_source_text(WITHHELD, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.4")
    assert "declaration" in clause["declared"][0]["reason"].lower()
    assert clause["allowed"] == []


def test_a_declaration_on_a_function_with_no_io_withholds_nothing():
    """The 62. Nothing was suppressed, so nothing is reported, and the marker costs the
    package nothing on a suppression count."""
    assessed = honest_code.assess(honest_code.read_source_text(WITHHELD_NOTHING, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.4")
    assert [d["symbol"] for d in clause["declared"]] == []


def test_a_declaration_on_an_entry_point_withholds_nothing():
    """The declaration agrees with the inference here: nothing in the module calls it, so
    the clause would have said nothing either way. Confirmatory rather than a suppression."""
    source = ("from l1_analyzer.boundary import boundary\n\n\n"
              "@boundary\ndef load(path):\n    return path.read_text()\n")
    assessed = honest_code.assess(honest_code.read_source_text(source, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.4")
    assert clause["declared"] == []


def test_the_record_says_the_declaration_overrode_the_inference():
    """Only the overriding case is ever emitted, because only it withholds anything. The
    record says which, so the difference between declaring a genuine edge and overruling
    the analyzer is readable rather than a matter of trust."""
    assessed = honest_code.assess(honest_code.read_source_text(WITHHELD, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.4")
    assert "call graph" in clause["declared"][0]["reason"]


def test_the_clause_still_reports_an_undeclared_violation():
    """The mechanism has to keep the clause working. A reader without a declaration fires
    as before."""
    source = WITHHELD.replace("@boundary\ndef load", "def load")
    assessed = honest_code.assess(honest_code.read_source_text(source, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.4")
    assert [f["symbol"] for f in clause["findings"]] == ["load"]
    assert clause["declared"] == []


def test_the_repository_measure_counts_the_declarations(tmp_path):
    (tmp_path / "edges.py").write_text(WITHHELD)
    result = honest_code.analyze(tmp_path, "python")
    assert len(result["declared"]) == 1
    assert "1 boundary declaration" in result["details"]


def test_the_count_is_stated_at_zero(tmp_path):
    """No conditional in the sentence, the same as the declared-exception count: a clause
    written only when the number is non-zero leaves a reader unable to tell none from
    not-reported."""
    (tmp_path / "clean.py").write_text("def f(n: int) -> int:\n    return n\n")
    assert "0 boundary declarations" in honest_code.analyze(tmp_path, "python")["details"]


def test_the_report_lists_them_apart_from_the_violations():
    printed = honest_code.report(honest_code.assess_file_text(WITHHELD, "m.py"))
    assert "boundary declaration" in printed.lower()
    assert "load" in printed
