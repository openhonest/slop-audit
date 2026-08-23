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
    assert "no clause examined" in printed.lower()


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
