"""A boundary that reads a random number satisfies one rule by breaking another.

A peer reported four sites where our rule says a function declares itself an edge and reaches
nothing outside the process. All four reach something non-deterministic instead:

    uuid.uuid4()          a random identifier
    signal.signal(...)    a process-global handler, installed and read back

The conflict is not a bug in either rule. honest-check grants a boundary three privileges,
input and output, catching, and reading something non-deterministic, and it REQUIRES the
marker on a function that does the third. Our rule reads a boundary as a function obtaining
something outside the process, and a random number is not that.

So a function taking a random identifier cannot satisfy both tools. It carries the marker and
honest-check passes; ours then calls the marker a false statement. The author is told to
delete a marker another gate needs, and the two tools disagree in public about the same line.

The peer carries the marker, because the other tool fails without it and ours only reports.
That is the right call and it should not cost them a finding.

Non-determinism is not I/O and this clause is not becoming a clause about non-determinism.
What changes is narrower: a declared boundary that reaches something non-deterministic is not
a FALSE declaration, so the half of the clause that calls a declaration false stays quiet.
The other half, a function that performs I/O below the boundary, is untouched.
"""

import pytest
from l1_analyzer import honest_code_edges as edges
from l1_analyzer import honest_code_read as read

DECORATOR = "from l1_analyzer.boundary import boundary\n\n\n"


def _false_declarations(source: str) -> list[str]:
    return [f["symbol"] for f in (edges.io_below_the_boundary(read.read_tree(source, "python")) or [])
            if "states an edge that is not there" in f["detail"]]


@pytest.mark.parametrize("call", [
    "uuid.uuid4()",
    "uuid.uuid1()",
    "random.random()",
    "secrets.token_hex(16)",
    "signal.signal(signal.SIGTERM, stop)",
    "time.time()",
])
def test_a_boundary_that_reaches_something_non_deterministic_is_not_a_false_declaration(call):
    module = call.split(".")[0]
    found = _false_declarations(
        DECORATOR + f"import {module}\n\n\n@boundary\ndef edge(stop):\n    return {call}\n")
    assert found == [], call


def test_it_is_still_not_counted_as_input_or_output():
    """The line this change does not cross. Another checker treats non-determinism as a
    boundary privilege alongside I/O; this clause is about I/O, and folding the two together
    would make it a different rule wearing the same number."""
    source = "import uuid\n\n\ndef pure():\n    return uuid.uuid4()\n\n\ndef run():\n    return pure()\n"
    found = [f for f in (edges.io_below_the_boundary(read.read_tree(source, "python")) or [])
             if "performs I/O" in f["detail"]]
    assert found == [], "a random number is still not I/O"


def test_a_boundary_that_reaches_nothing_at_all_is_still_reported():
    """The half of the clause that works, and the reason not to widen this further. A
    declaration on a function doing arithmetic is a false statement."""
    assert _false_declarations(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n")


def test_a_boundary_doing_real_input_or_output_is_still_quiet():
    assert _false_declarations(
        DECORATOR + "@boundary\ndef edge(path):\n    return path.read_text()\n") == []


# ---------------------------------------------------------------------------
# The third cause: input and output through a callable a record holds
#
# Three of the fifteen reach a database through a function stored in a record:
#
#     loader["disable_fk_checks"](conn)
#     run["copy_one_table"](...)
#
# There is no attribute access to read, so the reader sees a function that calls nothing.
# The peer was clear that this is their style rather than an accident: a Database in their
# code carries connect, close_connection, write_one and replicate_once as fields.
#
# We already read past this shape once. Clause 19 was taught that a function a dispatch table
# holds is a function something calls, and the same reading works here: if a record's field
# is called, what that field holds is what the boundary reaches.
# ---------------------------------------------------------------------------

def test_a_call_through_a_record_field_counts_as_what_the_field_holds():
    """The narrow version, which is what their three sites need: a literal key on a
    parameter, where the module binds that key to something this reader knows is I/O."""
    source = (DECORATOR + 'READERS = {"fetch_all": lambda c: c.fetchall()}\n\n\n'
              "@boundary\ndef edge(loader, conn):\n"
              '    return loader["fetch_all"](conn)\n')
    assert _false_declarations(source) == [], "the field holds a call that reaches a database"


def test_a_record_field_holding_nothing_of_the_kind_is_still_a_false_declaration():
    """The direction that must not move. Reaching through a record does not excuse a
    declaration on a function that reaches nothing."""
    source = (DECORATOR + 'ADDERS = {"one": lambda n: n + 1}\n\n\n'
              "@boundary\ndef edge(adders, n):\n"
              '    return adders["one"](n)\n')
    assert _false_declarations(source) == ["edge"], source
