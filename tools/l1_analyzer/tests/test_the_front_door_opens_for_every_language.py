"""Nine languages in the vocabulary, four suffixes at the door.

Every clause reads the shared node vocabulary now, and that vocabulary covers nine
languages. The table of file suffixes covers Python, JavaScript, TypeScript and HTML, so a
Java, C#, Go, Rust, Ruby or C file was never handed to a clause at all: it came back as a
file no reader here parses, before any clause was asked.

The list of clause languages was a third hand-written copy of the same fact, naming Python
and the browser three. So a clause could be ported, its language covered by the vocabulary,
its file still refused at the door, and its table row still saying the language does not
apply. Three owners of one fact and nothing checking they agree.

Found by porting the last clause: a Java file with no step definitions came back
"unreadable", and the reason given was that no reader here parses a .java file, which was
true and was about the door rather than about the clause.
"""

import pytest
from l1_analyzer import honest_code
from l1_analyzer.lang_spec import LANG_SPEC

_A_FILE = {
    "python": ("m.py", "def send(c):\n    return go(c)\n"),
    "javascript": ("app.js", "function send(c) { return go(c) }\n"),
    "typescript": ("app.ts", "function send(c: number) { return go(c) }\n"),
    "java": ("App.java", "class A { int send(int c) { return go(c); } }\n"),
    "csharp": ("App.cs", "class A { int Send(int c) { return Go(c); } }\n"),
    "go": ("app.go", "func send(c int) int { return goo(c) }\n"),
    "rust": ("app.rs", "fn send(c: i32) -> i32 { goo(c) }\n"),
    "ruby": ("app.rb", "def send(c)\n  goo(c)\nend\n"),
    "c": ("app.c", "int send(int c) { return goo(c); }\n"),
}


def test_every_language_the_vocabulary_covers_has_a_suffix_at_the_door():
    """The vocabulary is the one owner. A language it covers and the door refuses is a
    port that cannot be reached by the files it was written for."""
    missing = set(LANG_SPEC) - set(honest_code._SUFFIXES.values())
    assert missing == set(), missing


def test_the_clause_languages_are_the_vocabulary_rather_than_a_third_copy():
    """Hand-written, it said Python and the browser three. A clause reading a language the
    vocabulary covers and declaring it does not apply is the same fact disagreeing with
    itself in a third place."""
    assert honest_code._ALL == frozenset(LANG_SPEC)


@pytest.mark.parametrize("lang", list(_A_FILE))
def test_a_file_in_each_language_reaches_the_clauses(lang):
    name, source = _A_FILE[lang]
    assessed = honest_code.read_source_text(source, name)
    assert assessed["unreadable_reason"] == "", assessed["unreadable_reason"]
    assert assessed["language"] == lang


@pytest.mark.parametrize("lang", list(_A_FILE))
def test_at_least_one_clause_decides_in_each_language(lang):
    """The point of the port, asserted at the door rather than on a checker. A language
    where nothing decides would be a row of nothing-decided that reads as a clean file."""
    name, source = _A_FILE[lang]
    assessed = honest_code.assess(honest_code.read_source_text(source, name))
    assert [c["code"] for c in assessed if c["decided"]], lang


def test_a_suffix_nobody_wrote_down_is_still_refused():
    """The direction that must not move. An unknown file type is refused rather than
    guessed at, because a tree read with the wrong grammar produces findings about a file
    nobody read."""
    assessed = honest_code.read_source_text("hello\n", "notes.txt")
    assert assessed["unreadable_reason"]
