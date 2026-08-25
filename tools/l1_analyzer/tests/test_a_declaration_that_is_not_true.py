"""A boundary declaration on a function that is not one.

The decorator says "this function is an edge". Clause 4 reads it and withholds the finding
it would otherwise report, which is right when the function really does obtain something.
On a function that touches nothing outside the process it is a false statement, and nothing
reported it: the clause never fires on such a function anyway, so the declaration silences
nothing and sat there looking like a fact.

It cannot be told from a stamp in general, and this package's own docstring says so. It can
be told in one case, and that case is computable: a function under the decorator that
reaches nothing outside the process is a suppression by construction. A peer maintaining
the write hook had built a detector that counted markers rather than markers that withheld
anything, found it wrong three times in four, and removed it. This counts something true.
"""

import ast

from l1_analyzer import honest_code_python_rules as python_rules


def _findings(source: str) -> list[dict]:
    return python_rules.io_below_the_boundary({
        "path": "m.py", "language": "python", "text": source,
        "tree": ast.parse(source), "readable": True, "unreadable_reason": ""}) or []


DECORATOR = "from l1_analyzer.boundary import boundary\n\n\n"


def test_a_declaration_on_a_function_that_obtains_nothing_is_reported():
    found = _findings(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n\n\n"
                      "def run(n):\n    return edge(n)\n")
    assert [f["symbol"] for f in found] == ["edge"], found
    assert "no call this reader counts as I/O" in found[0]["detail"]


def test_a_declaration_on_a_function_that_does_obtain_something_is_not_reported():
    """The other direction, and the one that matters: a true declaration must stay silent
    or the rule punishes the thing it asks for."""
    found = _findings(DECORATOR + "@boundary\ndef edge(path):\n    return path.read_text()\n\n\n"
                      "def run(path):\n    return edge(path)\n")
    assert [f for f in found if f["withheld_by"] == ""] == [], found


def test_an_undeclared_function_that_obtains_nothing_is_not_reported():
    """Only a declaration can be false. A plain function claiming nothing cannot be."""
    assert _findings("def edge(n):\n    return n + 1\n\n\n"
                     "def run(n):\n    return edge(n)\n") == []


def test_a_declaration_on_an_uncalled_function_is_still_reported():
    """Clause 4 leaves an uncalled function alone, because it may be the entry point. That
    reasoning does not cover a false claim: an entry point that obtains nothing is still
    not an edge."""
    found = _findings(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n")
    assert [f["symbol"] for f in found] == ["edge"], found


def test_the_report_says_what_to_do_about_it():
    found = _findings(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n")
    assert found[0]["instead"].strip()


# ---------------------------------------------------------------------------
# What counts as I/O, and the message that described the wrong thing
#
# A peer running two tools over one codebase found 34 functions where this clause called a
# declaration false and their checker did not, plus 28 declarations they had removed on this
# clause's word and then put back. One cause: this list has sixteen names and theirs has
# sixty. Every case was a name missing here.
#
# The message made it harder to see. It read "obtains nothing outside the process", which is
# about intake, and the code tests membership in an I/O list, which is both directions. Both
# of us reasoned from the sentence rather than the code, and both got it wrong. Printing is
# output, and a function that prints is at an edge.
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize("body", [
    "print(msg)",
    "input()",
    "sys.stdout.write(msg)",
    "sys.stderr.write(msg)",
])
def test_a_function_that_writes_to_the_terminal_is_at_an_edge(body):
    """The 34. Printing is output, and output is I/O in the rule this clause implements."""
    found = _findings(DECORATOR + f"import sys\n\n\n@boundary\ndef say(msg):\n    {body}\n")
    assert [f for f in found if "states an edge that is not there" in f["detail"]] == [], body


@pytest.mark.parametrize("call", [
    "asyncpg.connect(dsn)",
    "aiosqlite.connect(path)",
    "psycopg2.connect(dsn)",
    "redis.Redis(host)",
    "os.walk(root)",
    "shutil.rmtree(path)",
    "socket.socket()",
    "logging.info(msg)",
])
def test_a_function_that_reaches_a_database_the_disk_or_the_network_is_at_an_edge(call):
    """The 28 they put back. A declaration this reader cannot corroborate is reported as
    false, and reporting a true declaration false is the direction that misleads."""
    module = call.split(".")[0]
    found = _findings(DECORATOR + f"import {module}\n\n\n@boundary\n"
                      f"def edge(dsn, path, root, host, msg):\n    return {call}\n")
    assert [f for f in found if "states an edge that is not there" in f["detail"]] == [], call


def test_an_ordinary_write_on_an_ordinary_object_is_not_reached_for():
    """The reason these are matched on the whole dotted call rather than the bare name.
    `buffer.write(x)` is not I/O, and adding `write` as a bare name more than doubled the
    findings on two real codebases."""
    found = _findings(DECORATOR + "@boundary\ndef edge(buffer, msg):\n"
                      "    buffer.write(msg)\n    return buffer.getvalue()\n")
    assert [f["symbol"] for f in found] == ["edge"], found


def test_the_message_says_what_the_reader_actually_checked():
    """It said "obtains nothing outside the process", which is narrower than the code and
    is what led two people to read this as a question about intake."""
    found = _findings(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n")
    assert "obtains nothing outside the process" not in found[0]["detail"]
    assert "I/O" in found[0]["detail"] or "reader" in found[0]["detail"]
