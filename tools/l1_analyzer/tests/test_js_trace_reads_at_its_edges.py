"""Clause 4 on the JavaScript tracer: the decision lifted out, then the read declared.

Three functions here read a file and decided something from what they read, so neither the
deciding nor the reading could be tested without the other, and the clause reported all
three. The remedy is the one `c_trace` got: the decision moves into a function that touches
nothing, and what is left obtains bytes and does nothing else.

The declaration is honest only AFTER the split. A decorator on a function that still
decides is a stamp, and these tests assert the split rather than the decorator: each
decider is checked to contain no read at all, and each is exercised on text alone.
"""

import pathlib

from l1_analyzer import js_trace


def test_the_nvmrc_pin_is_decided_from_text():
    assert js_trace.pin_in("18.17.0\n") == "18.17.0"
    assert js_trace.pin_in("") == ""


def test_the_installed_major_is_decided_from_text():
    assert js_trace.major_in('{"version": "^30.1.2"}', "jest") == (30, "")
    assert js_trace.major_in("{not json", "jest")[0] is None
    assert js_trace.major_in('{"name": "jest"}', "jest")[0] is None
    assert js_trace.major_in('{"version": "next"}', "jest")[0] is None


def test_each_reason_names_the_package_and_what_was_wrong():
    """The reason travels with the absence because a caller's guard once read `if major is
    not None and major < 30`, so a version nobody could read PROCEEDED to the measurement."""
    for text in ("{not json", '{"name": "jest"}', '{"version": "next"}'):
        major, reason = js_trace.major_in(text, "jest")
        assert major is None and "jest" in reason, text


def test_the_deciders_touch_nothing():
    """What makes the declaration on the readers honest rather than a stamp."""
    source = pathlib.Path(js_trace.__file__).read_text()
    for name in ("pin_in", "major_in"):
        body = source.split(f"def {name}")[1].split("\ndef ")[0]
        for reach in ("read_text", "read_bytes", "open(", "subprocess", "Popen"):
            assert reach not in body, (name, reach)


def test_the_readers_are_declared_and_the_clause_reads_the_declaration():
    """The three sites the clause reported are gone from its findings."""

    from l1_analyzer import honest_code_edges as edges
    from l1_analyzer import honest_code_read as read

    source = pathlib.Path(js_trace.__file__).read_text()
    found = edges.io_below_the_boundary(read.read_tree(source, "python")) or []
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == []
