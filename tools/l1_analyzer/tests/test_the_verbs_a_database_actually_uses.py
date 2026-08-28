"""Seven false positives from one cause: verbs our reader had never heard of.

A peer read every one of the fifteen sites where our rule said "this function declares itself
an edge and reaches nothing outside the process". None was a defect. Seven of them were real
input and output that our list simply did not name.

    connection.fetch(...)   asyncpg's only read verb
    conn.close()            closing a database connection, twice
    conn.rollback()         undoing a transaction, twice
    conn.push()             replication
    path.mkdir()            making a directory

We knew `execute` and `commit` and stopped there. `fetch` is how you read from PostgreSQL
with asyncpg, so every function that introspects a PostgreSQL database, in any codebase,
reported this way.

The direction of the error is what makes it worth fixing rather than tolerating. Telling an
author their true declaration is false asks them to delete a marker that is doing its job,
and this package's own boundary module says what that produces: a declaration removed from a
function that still reaches a database leaves the reach with nothing naming it.
"""

import pytest
from l1_analyzer import honest_code_edges as edges
from l1_analyzer import honest_code_read as read

DECORATOR = "from l1_analyzer.boundary import boundary\n\n\n"


def _found(source: str) -> list[dict]:
    return [f for f in (edges.io_below_the_boundary(read.read_tree(source, "python")) or [])
            if "states an edge that is not there" in f["detail"]]


@pytest.mark.parametrize("call", [
    "connection.fetch(query)",
    "connection.fetchval(query)",
    "conn.close()",
    "conn.rollback()",
    "conn.push()",
    "conn.executemany(query, rows)",
    "cursor.callproc(name)",
])
def test_a_database_verb_counts_as_reaching_the_database(call):
    found = _found(DECORATOR + f"@boundary\ndef edge(connection, conn, cursor, query, rows, name):\n"
                   f"    return {call}\n")
    assert found == [], call


@pytest.mark.parametrize("call", ["path.mkdir(parents=True)", "path.rmdir()",
                                  "path.touch()", "path.unlink()"])
def test_a_verb_that_changes_the_filesystem_counts_too(call):
    found = _found(DECORATOR + f"@boundary\ndef edge(path):\n    return {call}\n")
    assert found == [], call


@pytest.mark.parametrize("call", ["buffer.close()", "parser.fetch()"])
def test_the_same_verb_on_something_that_is_not_a_connection_is_not_reached_for(call):
    """The reason these are matched on the receiver as well as the verb. `close` on a string
    buffer is not I/O, and adding it as a bare name would report every context manager in
    every file."""
    found = _found(DECORATOR + f"@boundary\ndef edge(buffer, parser):\n    return {call}\n")
    assert found, call


def test_a_function_that_really_reaches_nothing_is_still_reported():
    """The half of this clause that works. A declaration on a function doing arithmetic is
    a false statement and the rule exists to find it."""
    assert _found(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n")
