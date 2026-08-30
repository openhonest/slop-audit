"""The denominator a reader sees is the number of clauses that ran.

It was the literal 19 while 22 clauses ran, so every report understated its own coverage by
three and no test noticed. The count had two owners, the sentence and the clause list, and
nothing checked they agreed. Reading `len(CLAUSES)` leaves one owner.

The same paragraph now names the principles no clause measures. A share over the clauses
that exist cannot see a principle nobody wrote a clause for, and a reader who is told the
denominator but not what is outside it will read a hundred per cent as covering the canon.
"""

import re

from l1_analyzer.honest_code import CLAUSES, assess_file_text
from l1_analyzer.honest_code_report import report

_QUIET = "def f(x: int) -> int:\n    return x + 1\n"


def _report():
    return report(assess_file_text(_QUIET, "m.py"))


def test_the_denominator_is_the_number_of_clauses_that_exist():
    assert f"of {len(CLAUSES)} clauses" in _report()


def test_no_report_states_a_clause_count_the_list_disagrees_with():
    stated = {int(n) for n in re.findall(r"of (\d+) clauses", _report())}
    assert stated == {len(CLAUSES)}, f"stated {stated}, and {len(CLAUSES)} clauses exist"


def test_the_reader_is_told_which_principles_no_clause_measures():
    text = _report()
    assert "Constrain AI with Data Shape Contracts" in text
    assert "Watch the Test Fail First" in text


def test_the_principles_with_no_clause_are_named_apart_from_the_share():
    """Named below the number, not folded into it. A principle nobody measured is not a
    principle that passed, and putting it in the same sentence as the score would read as
    one."""
    text = _report()
    assert text.index("Conformity:") < text.index("Watch the Test Fail First")
