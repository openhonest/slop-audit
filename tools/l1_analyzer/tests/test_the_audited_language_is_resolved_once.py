"""The audited language is resolved once, and `auto` never reaches a downstream stage.

Six places in the CLI spelled `str(results.get("lang", args.lang))`. Two things were wrong
with the copy. It is six spellings of one question, so a change to how the language is
settled reaches only the ones somebody remembers. And its fall-through is the REQUESTED
language, which is `auto` by default: a run that skipped the source pass handed the
literal string "auto" to the race harness and the prove loop, which then reported that
"auto" is a language they do not support yet.

indicators.detect_primary_language is the function that settles it, and the source pass
calls it. When no source pass ran, the CLI now calls it too, so every stage reads a real
language or a reason, never the name of the request.
"""

import pathlib

from l1_analyzer import cli, indicators


def test_the_cli_resolves_the_language_in_one_place():
    """Counted over code only. The helper's own docstring quotes the pattern it replaced,
    and a check that cannot tell a description of a defect from the defect is a check
    nobody can keep green."""
    lines = pathlib.Path(cli.__file__).read_text().split("\n")
    reads = [n for n, line in enumerate(lines, start=1)
             if 'results.get("lang"' in line.split("#", 1)[0] and not line.strip().startswith(("\"\"\"", "*", "REQUESTED"))
             and "spelled" not in line]
    assert len(reads) == 1, (
        f"the audited language is read in {len(reads)} places ({reads}); copies can settle it differently"
    )


def test_a_settled_language_is_taken_from_the_results(tmp_path):
    """When the source pass ran, its answer is the audited language, whatever was asked for."""
    assert cli._audited_language({"lang": "rust"}, "auto", tmp_path) == "rust"
    assert cli._audited_language({"lang": "rust"}, "python", tmp_path) == "rust"


def test_auto_is_settled_rather_than_passed_on(tmp_path):
    """No source pass ran, so nothing settled it. The CLI settles it the same way the
    source pass would, rather than handing the word `auto` to a stage that will report it
    as an unsupported language."""
    (tmp_path / "a.py").write_text("x = 1\n")
    resolved = cli._audited_language({}, "auto", tmp_path)
    assert resolved != "auto"
    assert resolved == indicators.detect_primary_language(tmp_path)


def test_an_explicit_request_stands_when_nothing_measured_it(tmp_path):
    """`--lang rust` with no source pass is an instruction, not a guess, so it is kept."""
    assert cli._audited_language({}, "rust", tmp_path) == "rust"
