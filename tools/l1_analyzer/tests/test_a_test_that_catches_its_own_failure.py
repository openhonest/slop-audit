"""A test that catches its own failure, and tells it from a real one by reading words.

Reported by a peer, from the only test in their suite of a constraint surviving a database
rebuild. It had been that way long enough that nobody remembered.

    try:
        insert_a_duplicate()
        pytest.fail(f"Should have failed UNIQUE constraint on '{column}'")
    except Exception as e:
        if "Should have failed" in str(e):
            raise
        # Expected - UNIQUE constraint is working
        rollback()

`pytest.fail` raises. The handler catches its own failure alongside the database's refusal,
and tells them apart by asking whether the exception's text contains "Should have failed".
Reword that message and the test passes while the constraint is broken.

It is worse than one wrong branch. Every other exception lands in the same handler and is
read as the constraint working: a typo in the SQL, a closed connection, a missing column, a
bug in the package under test.

Two things here are decidable and this file asserts both.

A deliberate failure inside a try whose handler can catch it. That is exact, because the
raise and the catch are in one function and a handler for every exception catches the failure
too. It is wrong whatever the handler does next.

A handler that branches on the exception's TEXT rather than its type. Also exact, and the
wider rule. This package hit the same shape in a different room: a contention check retried a
KeyError because the word matched, and the cause was ours.

What is not decidable is whether the text being matched is one the same function wrote, which
is what makes this instance circular. In general the string can come from anywhere, so
nothing here tries to decide it.
"""

import pytest
from l1_analyzer import honest_code_edges as edges
from l1_analyzer import honest_code_read as read


def _found(source: str, lang: str = "python") -> list[dict]:
    return [f for f in (edges.self_caught_failures(read.read_tree(source, lang)) or [])]


_CATCHES_ITSELF = '''def test_the_constraint_holds(conn):
    try:
        insert_a_duplicate(conn)
        pytest.fail("Should have failed UNIQUE constraint")
    except Exception as e:
        if "Should have failed" in str(e):
            raise
        conn.rollback()
'''

_SORTS_BY_WORDS = '''def run(job):
    try:
        return job()
    except KeyError as e:
        if "busy" in str(e):
            return retry(job)
        raise
'''


def test_a_deliberate_failure_inside_its_own_try_is_reported():
    found = _found(_CATCHES_ITSELF)
    assert found, "the handler catches the failure the try raises"
    assert any("catches its own failure" in f["detail"] for f in found), found


def test_a_handler_that_sorts_an_exception_by_its_words_is_reported():
    found = _found(_SORTS_BY_WORDS)
    assert found, "the handler reads the exception as text"
    assert any("text" in f["detail"] or "words" in f["detail"] for f in found), found


@pytest.mark.parametrize("failure", ["pytest.fail('no')", "self.fail('no')",
                                     "assert False, 'no'", "raise AssertionError('no')"])
def test_each_way_a_test_declares_failure_is_read(failure):
    source = f"def test_it(conn):\n    try:\n        go(conn)\n        {failure}\n    except Exception:\n        pass\n"
    assert _found(source), failure


def test_a_deliberate_failure_outside_a_try_is_left_alone():
    """The rule is about a failure its own handler can catch."""
    assert _found("def test_it():\n    if not ok():\n        pytest.fail('no')\n") == []


def test_a_handler_that_reads_the_type_is_left_alone():
    """What the rule asks for. Sorting by type is the correct way to tell one failure from
    another, and reporting it would punish the remedy."""
    assert _found("def run(job):\n    try:\n        return job()\n"
                  "    except KeyError:\n        return retry(job)\n") == []


def test_a_narrow_handler_that_cannot_catch_the_failure_is_left_alone():
    """`except ValueError` does not catch a test framework's failure, so the two cannot be
    confused and there is nothing here to report."""
    assert _found("def test_it():\n    try:\n        go()\n        pytest.fail('no')\n"
                  "    except ValueError:\n        pass\n") == []


def test_the_report_says_what_to_do():
    assert _found(_CATCHES_ITSELF)[0]["instead"].strip()


def test_a_handler_putting_the_message_in_a_response_is_left_alone():
    """The false positive this check produced on its first full run, on a route handler in
    this package's own tests. Quoting the exception to a caller is what a boundary is for.
    Deciding by those words is the defect, and only a condition decides."""
    assert _found("def route(x):\n    try:\n        return g(x)\n"
                  "    except ValueError as error:\n"
                  "        return respond(400, str(error))\n") == []
