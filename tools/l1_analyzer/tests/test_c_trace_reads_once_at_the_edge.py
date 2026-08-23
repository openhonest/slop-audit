"""The makefile reader, split into the part that reads and the part that decides.

Honest Code rule 4 puts I/O at the boundary and pure logic in the middle. `_make_target`
did both: it walked three candidate filenames, opened whichever existed, and then searched
the text for a target. The search is the decision and it needed a file on disk to reach it,
so every test of the decision had to build a directory first.

The split is the rule applied literally. `make_target_in` decides from text and touches
nothing. `_read_makefile` finds the file and reads it. The entry point calls the reader and
hands the text to the decider, so the I/O happens once, where the module meets the world.
"""

import pathlib

import pytest
from l1_analyzer import c_trace

# --------------------------------------------------------------------------
# The decision, with no filesystem anywhere near it
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("text", "target"), [
    ("all:\n\tgcc -o app main.c\ntest:\n\t./t\n", "test"),
    ("check:\n\t./t\n", "check"),
    ("test:\n\t./t\ncheck:\n\t./c\n", "test"),
])
def test_the_declared_test_target_is_named(text, target):
    assert c_trace.make_target_in(text) == (target, "")


def test_a_makefile_declaring_neither_target_says_so():
    target, why = c_trace.make_target_in("all:\n\tgcc -o app main.c\n")
    assert target is None
    assert "declares no" in why


def test_an_empty_makefile_declares_no_target():
    target, why = c_trace.make_target_in("")
    assert target is None and why.strip()


def test_a_target_named_inside_a_recipe_line_is_not_a_declaration():
    """`^test\\s*:` anchors to the start of a line. A recipe mentioning the word is not a
    rule declaring it, and matching it would report a build the makefile cannot run."""
    assert c_trace.make_target_in("all:\n\techo test: nothing\n")[0] is None


def test_the_decider_needs_no_directory_to_be_exercised():
    """The point of the split. Every case above is a string, so the decision can be tested
    without building a tree, and the reader below is the only thing that needs one."""
    assert c_trace.make_target_in("test:\n\t./t\n")[0] == "test"


# --------------------------------------------------------------------------
# The read, which is the only part that meets the filesystem
# --------------------------------------------------------------------------

def test_the_first_makefile_found_is_read(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\t./t\n")
    text, name, why = c_trace._read_makefile(tmp_path)
    assert "test:" in text and name == "Makefile" and why == ""


@pytest.mark.parametrize("name", ["Makefile", "makefile", "GNUmakefile"])
def test_each_of_the_three_usual_names_is_found(name, tmp_path):
    """The name reported back is whichever of the three the reader looked for first, and on
    a case-insensitive filesystem two of them are the same file. That is a fact about the
    platform, so the assertion is that the file was FOUND rather than what it was called."""
    (tmp_path / name).write_text("check:\n\t./t\n")
    text, found, why = c_trace._read_makefile(tmp_path)
    assert "check:" in text, why
    assert found.lower() == name.lower() or found in c_trace._MAKEFILES


def test_a_repository_with_no_makefile_says_which_names_it_looked_for(tmp_path):
    text, name, why = c_trace._read_makefile(tmp_path)
    assert text == "" and name == ""
    assert "Makefile" in why


def test_an_unreadable_makefile_is_a_different_answer_from_an_absent_one(tmp_path):
    """The two send a reader to different repairs, and a single empty string would have
    made them one answer."""
    makefile = tmp_path / "Makefile"
    makefile.write_text("test:\n\t./t\n")
    makefile.chmod(0o000)
    try:
        text, _name, why = c_trace._read_makefile(tmp_path)
    finally:
        makefile.chmod(0o644)
    if text:
        pytest.skip("this filesystem let the unreadable file be read anyway")
    assert "could not be read" in why


# --------------------------------------------------------------------------
# The entry point, which is where the I/O now happens
# --------------------------------------------------------------------------

def test_no_helper_below_the_entry_point_touches_the_filesystem():
    """Rule 4, asserted against the module rather than described in a docstring. Only the
    reader and the entry points may do I/O, and the reader is called by the entry point
    alone."""
    import ast

    from l1_analyzer import honest_code_python_rules as python_rules

    source = pathlib.Path(c_trace.__file__).read_text()
    found = python_rules.io_below_the_boundary({
        "path": "c_trace.py", "language": "python", "text": source,
        "tree": ast.parse(source), "readable": True, "unreadable_reason": ""})
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == [], found
