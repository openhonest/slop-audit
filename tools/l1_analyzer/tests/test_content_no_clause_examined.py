"""Content inside a readable file that no clause looked at.

A Python file holding a JavaScript widget in a string constant scored 100 per cent,
Healthy, with fourteen of nineteen clauses decided and no findings. The JavaScript in it
had a dispatch chain and a swallowed error. Every Python clause examined the Python
correctly, found nothing, and was right to; the file's substance was never examined by
anything.

This is the inverse of the empty-tree failure fixed this morning. That one graded a file no
parser had read, and the count of decided clauses gave it away. This one has a full tree of
the right language and the count of decided clauses is the number that would normally
reassure a reader.

It is not a clause and it is not graded. It is a statement about coverage: this file
contains N lines that parse as another language and nothing examined them. That sentence is
true, costs a reader nothing, and cannot be wrong the way a silent 100 can.

Nothing is guessed from resemblance. A block is named only when a real grammar accepts the
whole of it with no error node. Run over this package's own source, 355 long string
literals produced eleven hits and every one was genuine embedded source held as a test
fixture.
"""

from unittest import mock

import pytest
from l1_analyzer import honest_code

WIDGET = '''"""A Python module that serves a JavaScript widget."""

WIDGET = """
class Widget extends Base {
  send(channel, data) {
    if (channel === 'email') { return sendEmail(data); }
    else if (channel === 'sms') { return sendSms(data); }
    else if (channel === 'push') { return sendPush(data); }
    return null;
  }
}
"""


def widget() -> str:
    return WIDGET
'''

PROSE = '''"""A module with a long docstring and nothing hidden in it.

This paragraph runs to several lines so that it is long enough to be considered, and it
says nothing that any grammar would accept. It is the case that must not fire, because a
reader who is told their prose is unexamined JavaScript will stop reading the notices.
"""


def band(n: int) -> str:
    return "high" if n > 10 else "low"
'''


def test_embedded_source_is_named_with_its_language_and_size():
    found = honest_code.unexamined_blocks(honest_code.read_source_text(WIDGET, "m.py"))
    assert len(found) == 1
    assert found[0]["language"] == "javascript"
    assert found[0]["lines"] >= 5


def test_the_block_is_located_so_a_reader_can_go_and_look():
    found = honest_code.unexamined_blocks(honest_code.read_source_text(WIDGET, "m.py"))
    assert found[0]["line"] > 1


def test_prose_is_not_reported_as_embedded_source():
    """The case that must not fire. A reader told their docstring is unexamined JavaScript
    stops reading the notices, and then the one that matters is skipped too."""
    assert honest_code.unexamined_blocks(honest_code.read_source_text(PROSE, "m.py")) == []


def test_a_short_string_is_not_a_block():
    """One line of something that parses is a fragment, not content nobody examined."""
    source = 'CALL = "f(x);"\n\n\ndef go() -> str:\n    return CALL\n'
    assert honest_code.unexamined_blocks(honest_code.read_source_text(source, "m.py")) == []


def test_a_file_with_nothing_embedded_reports_nothing():
    source = "def band(n: int) -> str:\n    return 'high' if n > 10 else 'low'\n"
    assert honest_code.unexamined_blocks(honest_code.read_source_text(source, "m.py")) == []


# --------------------------------------------------------------------------
# What it does to the assessment, and what it deliberately does not
# --------------------------------------------------------------------------

def test_the_assessment_carries_the_unexamined_content():
    assessment = honest_code.assess_file_text(WIDGET, "m.py")
    assert len(assessment["unexamined"]) == 1


def test_it_does_not_change_the_conformity_share():
    """It is not a clause and it is not graded. The Python in that file really does hold
    every clause that read it, and saying otherwise would be inventing a violation."""
    assessment = honest_code.assess_file_text(WIDGET, "m.py")
    assert assessment["conformity"] == 100.0


def test_the_report_says_the_file_was_not_fully_examined():
    """The whole point. A hundred per cent beside a notice that fourteen lines were never
    looked at is a reading a person can act on; a hundred per cent alone is not."""
    printed = honest_code.report(honest_code.assess_file_text(WIDGET, "m.py"))
    assert "javascript" in printed.lower()
    # The disclosure, not its wording. This pinned the phrase "no clause examined" until the
    # blocks began carrying what the clauses found in them, at which point the sentence
    # became false: the clauses did examine it, separately, and that is the useful part.
    assert "does not cover" in printed


def test_the_hook_says_it_too():
    """The hook prints only what an agent must change, and this is not a violation. It is
    still the one thing that stops a clean hook result reading as a clean file."""
    printed = honest_code.hook_report(honest_code.assess_file_text(WIDGET, "m.py"))
    assert "javascript" in printed.lower()


def test_a_clean_file_with_nothing_embedded_still_says_nothing_at_all():
    source = "def band(n: int, table: dict) -> str:\n    return 'high' if n > table['x'] else 'low'\n"
    assert honest_code.hook_report(honest_code.assess_file_text(source, "m.py")) == ""


def test_the_repository_measure_counts_the_unexamined_blocks(tmp_path):
    (tmp_path / "widget.py").write_text(WIDGET)
    result = honest_code.analyze(tmp_path, "python")
    assert result["unexamined"] == 1
    assert "1 block" in result["details"]


def test_the_count_is_stated_at_zero(tmp_path):
    (tmp_path / "plain.py").write_text("def f(n: int) -> int:\n    return n\n")
    assert "0 blocks" in honest_code.analyze(tmp_path, "python")["details"]


# --------------------------------------------------------------------------
# Page content, which is how embedded source usually arrives
# --------------------------------------------------------------------------

WRAPPED = '''PAGE = """
<script>
class Widget extends Base {
  send(channel, data) {
    if (channel === 'email') { return sendEmail(data); }
    else if (channel === 'sms') { return sendSms(data); }
    return null;
  }
}
</script>
"""


def page() -> str:
    return PAGE
'''

STYLED = '''PAGE = """
<style>
.widget { color: red; margin: 0; }
.widget:hover { color: blue; }
.panel { display: grid; gap: 1rem; }
</style>
"""


def page() -> str:
    return PAGE
'''


def test_script_content_is_found_through_its_wrapper():
    """The same JavaScript reported bare was silent once wrapped in a script tag, because
    the tags are not JavaScript and the whole-grammar test rejected the block. That is the
    case this was built for: page content usually arrives wrapped."""
    found = honest_code.unexamined_blocks(honest_code.read_source_text(WRAPPED, "m.py"))
    assert [b["language"] for b in found] == ["javascript"]


def test_style_content_is_found_the_same_way():
    found = honest_code.unexamined_blocks(honest_code.read_source_text(STYLED, "m.py"))
    assert [b["language"] for b in found] == ["css"]


def test_a_malformed_wrapper_is_never_read_as_markup():
    """One grammar deeper, not one pattern looser. The markup grammar has to accept the
    WHOLE block before anything is looked for inside it, so an unterminated script tag can
    never be reported as markup or as the language it wraps.

    It is still reported, as TypeScript, because that grammar accepts a bare tag as JSX and
    genuinely does accept this text whole. The block is unexamined content and only its
    name is arguable, which is the same ambiguity the precedence rule above settles in the
    other direction and the reason that rule had to be written down."""
    source = honest_code.read_source_text(WRAPPED.replace("</script>", ""), "m.py")
    found = honest_code.unexamined_blocks(source)
    assert [b["language"] for b in found] != ["html"], (
        "markup that does not parse whole was read as markup anyway, so the whole-parse "
        "requirement has stopped holding")
    assert [b["language"] for b in found] != ["javascript"], (
        "the inner text was reached without the wrapper parsing, so something is being "
        "stripped")


def test_the_line_reported_points_at_the_element_in_the_file():
    """A file line, not a block-relative one, and the element's line rather than the
    string's. It used to report the string's line for everything inside it, so a reader
    given line 1 for a script starting on line 6 had to go and find it, and two elements
    carried the same line."""
    found = honest_code.unexamined_blocks(honest_code.read_source_text(WRAPPED, "m.py"))
    line = WRAPPED.split("\n")[found[0]["line"] - 1]
    assert "script" in line, f"line {found[0]['line']} is {line!r}"


def test_markup_with_no_script_or_style_reports_the_markup_itself():
    """Plain markup in a string is still content nothing examined, and naming it as markup
    is truer than naming it as the language of whatever it does not contain."""
    source = 'PAGE = """\n<div>\n<p>one</p>\n<p>two</p>\n</div>\n"""\n\n\ndef page() -> str:\n    return PAGE\n'
    found = honest_code.unexamined_blocks(honest_code.read_source_text(source, "m.py"))
    assert [b["language"] for b in found] == ["html"]


def test_prose_is_still_not_markup():
    """The markup grammar is permissive enough to accept prose, which would undo the whole
    result. Prose has no element and no script, so there is nothing to name."""
    assert honest_code.unexamined_blocks(honest_code.read_source_text(PROSE, "m.py")) == []


BOTH = '''PAGE = """
<style>
.widget { color: red; }
.panel { display: grid; }
</style>
<script>
function send(channel) {
  if (channel === 'a') { return one(); }
  else if (channel === 'b') { return two(); }
  return null;
}
</script>
"""


def page() -> str:
    return PAGE
'''


def test_every_embedded_element_is_named_not_just_the_first():
    """A block holding both a style and a script reported one of them, and which one
    depended on the order they were found in. The other was dropped silently, and the record
    read as though the block had been accounted for.

    This is the case the feature was built for: page content is usually both."""
    found = honest_code.unexamined_blocks(honest_code.read_source_text(BOTH, "m.py"))
    assert sorted(b["language"] for b in found) == ["css", "javascript"]


def test_each_element_reports_its_own_size_rather_than_the_whole_block():
    """The block is thirteen lines. Neither element is, and reporting the block's size
    against one language says the whole string was that language."""
    found = honest_code.unexamined_blocks(honest_code.read_source_text(BOTH, "m.py"))
    assert all(b["lines"] < 8 for b in found), found


def test_each_element_reports_its_own_line():
    """A reader given line 1 for a script that starts on line 6 has to search for it, and
    the two elements would carry the same line."""
    found = honest_code.unexamined_blocks(honest_code.read_source_text(BOTH, "m.py"))
    lines = sorted(b["line"] for b in found)
    assert len(set(lines)) == 2, found
    assert lines[0] < lines[1]


def test_a_single_element_still_reports_the_element():
    found = honest_code.unexamined_blocks(honest_code.read_source_text(WRAPPED, "m.py"))
    assert len(found) == 1
    assert found[0]["language"] == "javascript"


def test_a_bare_block_still_reports_the_whole_of_itself():
    """Nothing wrapped it, so the block IS the content and its own size is the right size."""
    found = honest_code.unexamined_blocks(honest_code.read_source_text(WIDGET, "m.py"))
    assert len(found) == 1 and found[0]["lines"] >= 5


# ---------------------------------------------------------------------------
# A grammar that is not there
#
# `_accepts_whole` caught KeyError, ValueError and ImportError together and returned None,
# which is the same answer it gives for "the grammar read the text and rejected it". Three
# facts, one word. The costly one is ImportError: a grammar that failed to install makes
# every block in that language vanish, the file reports nothing unexamined, and the share
# claims to cover a file it only half read. That is the silent success clause 8 names, and
# the reader wrote it about itself.
# ---------------------------------------------------------------------------

def test_a_language_whose_grammar_is_absent_is_named_rather_than_silently_skipped():
    """The whole reason the catch was wrong. Absence has to reach the reader."""
    with_css = honest_code.read_source_text("x = 1\n\nCSS = '''\nbody {\n    color: red;\n}\n'''\n", "m.py")
    assert [b["language"] for b in honest_code.unexamined_blocks(with_css)] == ["css"]

    without = {name: grammar for name, grammar in honest_code.GRAMMARS.items()
               if name != "css"}
    with mock.patch.object(honest_code, "GRAMMARS", without), \
            pytest.raises(KeyError, match="css"):
        honest_code.unexamined_blocks(with_css)


def test_the_grammars_this_reader_loaded_are_stated_rather_than_discovered_per_call():
    """A table built once at import, so a caller asks what is there instead of parsing and
    catching to find out."""
    assert set(honest_code.GRAMMARS) >= {"html", "css"}


# ---------------------------------------------------------------------------
# Naming the language was never the point
#
# A peer measuring real work hit a twelve-line SQL query inside a PostgreSQL driver,
# reported as ruby. The ruby grammar accepts it whole, there is no SQL grammar, so that
# label can never be right, and a database driver holds dozens of those. A field that
# reports a wrong name and nothing else teaches a reader to skip it, which costs the case
# it was built for.
#
# The fix is not a better guess at the language. Run the clauses on the block and report
# what they say. Measured on three blocks: the SQL misnamed as ruby fires nothing, because
# it is not ruby and has none of ruby's shapes. A real embedded widget fires three clauses.
# A block whose language is ambiguous between five grammars still fires the clause that was
# true of it whichever name it was given.
#
# So a wrong name costs nothing once the findings travel with the block, and the reader gets
# the thing they can act on instead of a label they cannot.
# ---------------------------------------------------------------------------

SQL_IN_A_DRIVER = (
    "def primary_key(table):\n"
    "    return QUERY\n\n\n"
    "QUERY = '''\n"
    "SELECT a.attname as column_name\n"
    "FROM pg_index i\n"
    "JOIN pg_attribute a ON a.attrelid = i.indrelid\n"
    "WHERE i.indisprimary\n"
    "ORDER BY a.attnum;\n"
    "'''\n"
)

WIDGET_IN_A_PAGE = (
    "SCRIPT = '''\n"
    "function send(channel, data) {\n"
    "  try { return go(data); } catch (e) { return null; }\n"
    "}\n"
    "'''\n"
)


def test_a_block_carries_what_the_clauses_found_in_it():
    found = honest_code.unexamined_blocks(honest_code.read_source_text(WIDGET_IN_A_PAGE, "m.py"))
    assert found, "the widget is embedded source and has to be seen"
    assert found[0]["findings"], "a block with no findings attached tells a reader nothing"
    assert any(f["clause"] == "L1.21.8" for f in found[0]["findings"]), found[0]["findings"]


def test_a_misnamed_block_reports_nothing_because_it_is_not_that_language():
    """The SQL case, and the whole argument. It is named ruby because ruby accepts it, and
    every ruby clause then finds nothing in it, because it is not ruby."""
    found = honest_code.unexamined_blocks(honest_code.read_source_text(SQL_IN_A_DRIVER, "m.py"))
    assert found, "the block is still disclosed: the share above did not cover it"
    assert found[0]["findings"] == [], found[0]["findings"]


def test_the_report_shows_a_block_that_found_something_and_not_one_that_did_not():
    """A driver holding dozens of queries must not produce dozens of lines that say only
    that a name was guessed."""
    noisy = honest_code.report(honest_code.assess_file_text(SQL_IN_A_DRIVER, "m.py"))
    useful = honest_code.report(honest_code.assess_file_text(WIDGET_IN_A_PAGE, "m.py"))
    assert "swallow" in useful.lower() or "reports success" in useful
    assert "ruby" not in noisy


def test_the_name_is_a_pick_and_the_other_candidates_travel_with_it():
    """The naming is UNSOLVED, and this test records how far it got rather than hiding it.

    Counting acceptors was tried first, on the theory that many of them means the name is a
    coin flip. Two one-line functions are taken whole by five grammars, and naming that
    block `c` gave a finding whose symbols read "function, function", which is a grammar's
    confusion reaching a person as a fact about their code.

    The theory failed under measurement. A REAL embedded widget is taken by three grammars,
    csharp among them, so every cut that refused the five refused the widget too, and the
    widget is the case this field exists for. Alphabetical order then names that widget
    csharp, which is wrong.

    So the ambiguity is disclosed rather than acted on. A missed widget is the silence this
    was built to stop; a finding under a doubtful name is noise a reader can discount, once
    they are shown the other candidates."""
    real = ("WIDGET = '''\n"
            "function send(channel, data) {\n"
            "  try { return go(data); } catch (e) { return null; }\n"
            "}\n"
            "'''\n")
    found = honest_code.unexamined_blocks(honest_code.read_source_text(real, "m.py"))
    assert found[0]["findings"], "the case this field exists for"
    assert "javascript" in found[0]["also_accepted_by"], found[0]
    assert found[0]["language"] not in found[0]["also_accepted_by"]
