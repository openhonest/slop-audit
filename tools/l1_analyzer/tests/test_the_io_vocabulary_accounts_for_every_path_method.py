"""Every filesystem call `pathlib.Path` offers is either an edge or declared not to be.

L1.21.4 decides whether a function is an edge by matching call names against a per-language
set. A set can never be complete, and every gap is silent in the same direction: a function
that reaches outside the process reads as pure interior.

Two gaps were found by accident, both the same way. `rglob` was missing, hiding four
undeclared filesystem edges. Then `exists`, `stat`, `is_file` and `is_dir` were missing,
hiding twelve more, among them the scope rules that decide which files an audit opens and the
staleness refusal in the Rust port's own parity harness. Each was noticed only because a
function that obviously does I/O was reported as declaring an edge it does not have.

This does not fix the shape, and the module it guards says so: recognising I/O by what a call
is made ON rather than by what it is called would subsume most of the name list, and that
needs a receiver-type read the clause does not do. What this does is turn the next gap into a
failing test rather than an accident. Every public method `pathlib.Path` carries has to appear
in exactly one of three places below, so adding a method to the standard library, or removing
a name from the vocabulary, fails here and not in somebody's audit six months later.

The tables are read against whatever interpreter runs the tests, and this package supports
3.12 and up. A table may therefore name a method this interpreter does not have, which costs
nothing: a ruling about a name that cannot appear rules on nothing. A rename is still caught,
because the new name arrives in no table and the closure test fires on it.
"""

from __future__ import annotations

import pathlib

from l1_analyzer.lang_spec import LANG_SPEC

# Methods that compute a new path, compare two, or read a name. They touch nothing outside
# the process, so calling one does not make a function an edge.
PURE = frozenset({
    "as_posix", "as_uri", "from_uri", "full_match", "is_absolute", "is_relative_to",
    "is_reserved", "joinpath", "match", "relative_to", "with_name", "with_segments",
    "with_stem", "with_suffix",
})

# Methods that DO reach the filesystem and are still not in the vocabulary, because the
# vocabulary matches a bare name and these names belong to something else far more often.
#
# The counts are from this repository on 2026-09-23, over its own Python: `.resolve(` 87
# times, `.walk(` 73, `.replace(` 53. Almost none of the second and third are a Path. A
# promise resolver, a DNS resolver, a tree walk and `str.replace` all spell themselves this
# way, so adding the name would trade a silent miss for a loud false positive, which is the
# failure that makes an auditor stop believing the number.
#
# `group` is the same shape from the other end: `Path.group` reads the file's group owner and
# `re.Match.group` reads a capture, and this repository calls the second 49 times and the
# first never.
#
# These are the names that motivate the structural answer. Until a clause can read what a
# call is made ON, the honest thing is to say which names it cannot decide.
UNDECIDABLE_BY_NAME = frozenset({"group", "replace", "resolve", "walk"})


def path_methods() -> frozenset[str]:
    """Every public method `pathlib.Path` carries on the interpreter running the tests."""
    return frozenset(name for name in dir(pathlib.Path)
                     if not name.startswith("_")
                     and callable(getattr(pathlib.Path, name, None)))


def test_every_path_method_is_an_edge_or_is_declared_not_to_be():
    """The closure. A method in none of the three tables is a gap nobody has ruled on."""
    io_calls = frozenset(LANG_SPEC["python"]["io_calls"])
    unaccounted = path_methods() - io_calls - PURE - UNDECIDABLE_BY_NAME
    assert not unaccounted, (
        "these pathlib.Path methods are in no table, so nothing has ruled on whether calling "
        f"one makes a function an edge: {sorted(unaccounted)}")


def test_no_method_is_ruled_on_twice():
    """One name, one answer. A method in two tables means two readers can disagree about it
    and both cite a table."""
    io_calls = frozenset(LANG_SPEC["python"]["io_calls"])
    for first, second, label in ((io_calls, PURE, "io_calls and PURE"),
                                 (io_calls, UNDECIDABLE_BY_NAME, "io_calls and UNDECIDABLE"),
                                 (PURE, UNDECIDABLE_BY_NAME, "PURE and UNDECIDABLE")):
        both = first & second & path_methods()
        assert not both, f"{label} both claim: {sorted(both)}"
