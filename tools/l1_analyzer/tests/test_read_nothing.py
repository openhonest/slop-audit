"""A check that read nothing must say so, not report the property it never tested.

The shape these tests pin is the one `state_census.py` closed for the state classifier:
every self-disclosure number a check publishes is computed over its own recognition set,
so an empty recognition set produces an affirmative result rather than a refusal. Zero
findings over zero files is the same number as zero findings over a thousand, and the
band field - the one a reader actually looks at - cannot tell them apart.

Two checks carried it. L1.14 reported `band: Healthy` on a tree where every file was
excluded before it was opened, which is a clean bill of health on a repository the
scanner never read; given that this indicator's whole job is finding live credentials,
a fabricated clean is its worst possible failure. `thread_surface` reported
`verdict: clean` on the same tree, and again on a tree whose only source file the parser
could not read.

The two need different denominators, and the difference is the point. L1.14's rules are
regular expressions over decoded text, so a file it counted as scanned WAS scanned end to
end and `files_scanned` is exact. `thread_surface` matches tree-sitter node types, so a
file it counted as read can still be a file it cannot see into: the parser hands back an
ERROR-bearing tree and every node query comes back empty, which is indistinguishable from
clean code. Its denominator is therefore the count of files that parsed, taken from the
parser's own error flag - a property the scanner's rule table never consults - and not the
count of files opened.

Honest zero is the control in every case below. A refusal that also fired on a repository
the check really did read would be a second lie in the other direction.
"""

import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import (
    absolute_paths,
    interleaving_robustness,
    secret_scan,
    thread_surface,
)


def _tree(files: dict[str, str], git: bool = False, add: bool = False) -> pathlib.Path:
    """A temp repository. `git` inits a working tree; `add` stages the files.

    git-without-add is the read-nothing case for L1.14 and not a contrivance: it is a
    fresh checkout before the first commit, and a repository whose tracked paths all sit
    under an ignored directory reaches it too. The scanner reads the index rather than the
    filesystem, so an empty index means it opens no file at all.
    """
    root = pathlib.Path(tempfile.mkdtemp())
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    if git:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        if add:
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


# --- L1.14: a clean bill on a tree it never opened -----------------------------------

def test_l1_14_refuses_when_it_opened_no_file():
    """The defect: every file excluded by the index, and the band still says Healthy."""
    r = secret_scan.analyze(_tree({"app.py": "x = 1\n"}, git=True), "python")
    assert r["files_scanned"] == 0
    assert r["value"] == "n/a", "a count over no file is not a count"
    assert r["band"] == "n/a", "Healthy here is a clean bill on a repository it never read"


def test_l1_14_refusal_says_why_in_the_details():
    r = secret_scan.analyze(_tree({"app.py": "x = 1\n"}, git=True), "python")
    assert "no file" in r["details"]


def test_l1_14_still_reports_an_honest_zero():
    """The control. A repository it DID read, with no credential in it, stays Healthy:
    the refusal must separate 'read nothing' from 'read the code and found nothing'."""
    r = secret_scan.analyze(_tree({"app.py": "TOKEN = os.environ['TOKEN']\n"}), "python")
    assert r["files_scanned"] == 1
    assert r["value"] == 0 and r["band"] == "Healthy"


def test_l1_14_still_finds_a_credential_in_a_tracked_tree():
    """The second control: staging the file restores the reading, so the refusal is
    about an empty scan and not about git being present."""
    # Assembled from parts, and deliberately not AWS's documented EXAMPLE key: the scanner
    # screens placeholder words, so the sample every reader reaches for is the one value
    # that cannot prove the scanner works.
    key = "AKIA" + "Q7RJ4M2XN5VDPL3B"
    r = secret_scan.analyze(_tree({"app.py": f'AWS = "{key}"\n'}, git=True, add=True), "python")
    assert r["files_scanned"] == 1 and r["value"] == 1 and r["band"] == "Not Healthy"


# --- thread_surface: clean over an empty scope ----------------------------------------

def test_thread_surface_refuses_when_no_file_was_in_scope():
    """The defect: the whole tree bucketed out as tests, and the verdict still says clean."""
    ts = thread_surface.scan(_tree({"tests/test_a.py": "def test_a():\n    assert True\n"}), "python")
    assert ts["bucketed"]["counts"] == {"tests": 1}
    assert ts["verdict"] != thread_surface.CLEAN
    assert ts["verdict"] == thread_surface.UNREAD


def test_thread_surface_refuses_when_the_parser_could_not_read_the_source():
    """The second arm, and the reason this check needs a denominator L1.14 does not.
    The file is opened, decoded and counted, and every node query over it comes back
    empty because the tree is an error. A file count cannot see that; the parse can."""
    ts = thread_surface.scan(_tree({"app.py": "def broken(:\n  ???\n"}), "python")
    assert ts["files_read"] == 1, "the file was opened"
    assert ts["files_parsed"] == 0, "and the parser could not read it"
    assert ts["verdict"] == thread_surface.UNREAD


def test_thread_surface_refusal_is_not_the_no_scanner_refusal():
    """Three facts, three answers. 'No scanner for this language' and 'a scanner that
    read nothing' send the reader to different places, and n/a for both sent them to
    neither."""
    unread = thread_surface.scan(_tree({"tests/test_a.py": "x = 1\n"}), "python")
    no_scanner = thread_surface.scan(_tree({"main.c": "int main(void){return 0;}\n"}), "c")
    assert no_scanner["verdict"] == "n/a"
    assert unread["verdict"] != no_scanner["verdict"]


def test_thread_surface_still_reports_an_honest_clean():
    """The control: a production file that parses and holds no concurrency surface."""
    ts = thread_surface.scan(_tree({"app.py": "def add(a, b):\n    return a + b\n"}), "python")
    assert ts["files_read"] == 1 and ts["files_parsed"] == 1
    assert ts["verdict"] == thread_surface.CLEAN


def test_thread_surface_one_readable_file_is_enough_to_grade():
    """A partial reading is not the same fact as no reading, which is the rule the state
    census settled: umbra admits 0.7% of its declared state and is still graded. One file
    the parser could read carries the verdict, and the counts disclose how thin it was."""
    ts = thread_surface.scan(
        _tree({"ok.py": "def add(a, b):\n    return a + b\n", "bad.py": "def broken(:\n  ???\n"}),
        "python")
    assert ts["files_read"] == 2 and ts["files_parsed"] == 1
    assert ts["verdict"] == thread_surface.CLEAN


def test_thread_surface_findings_are_kept_from_a_file_that_did_not_parse():
    """The parse count is a denominator, never a filter. A hazard tree-sitter recovered
    from an error-bearing file is still a hazard, and dropping it to keep the two numbers
    tidy would trade a false clean for a missed finding."""
    src = "import threading\nCACHE = {}\n\ndef broken(:\n  ???\n"
    ts = thread_surface.scan(_tree({"app.py": src}), "python")
    assert ts["files_parsed"] == 0
    assert any(f["kind"] == "unguarded_shared_state" for f in ts["findings"])
    assert ts["verdict"] == thread_surface.EXPOSED, "a finding outranks the refusal"


# --- the dependent meter --------------------------------------------------------------

def test_interleaving_robustness_does_not_inherit_a_manufactured_clean():
    """It reads thread_surface's findings and calls an empty list 'no exposed surface to
    model'. Over an unread scan that is the same fabricated clean one module downstream,
    which is where a fixed defect comes back."""
    ir = interleaving_robustness.analyze(_tree({"src/lib.rs": "pub fn ((( -> {{ ???\n"}), "rust")
    assert ir["verdict"] != interleaving_robustness.CLEAN
    assert ir["verdict"] == interleaving_robustness.NA


def test_interleaving_robustness_still_reports_a_read_clean():
    ir = interleaving_robustness.analyze(_tree({"src/lib.rs": "pub fn add() -> i32 { 1 }\n"}), "rust")
    assert ir["verdict"] == interleaving_robustness.CLEAN


# --- the survey, pinned so the next reader does not have to re-derive it ---------------

@pytest.mark.parametrize("check", ["L1.15", "L1.16", "L1.17", "absolute_paths"])
def test_the_remaining_empty_denominator_claims_are_recorded(check):
    """These four still assert a positive property over an empty set, and this test
    records that rather than hiding it. It is written to pass on today's behaviour, so it
    fails the day one of them is fixed - at which point the fix moves the assertion here
    and the survey stays true instead of going stale."""
    from l1_analyzer import indicators
    empty = _tree({"README.md": "nothing here\n"})
    known = {
        # A repo under 1,000 production lines gets density 0.0 by a threshold with no
        # derivation, so Healthy is fabricated even where the lines DO exist and are
        # nothing but escape hatches.
        "L1.15": lambda: indicators._compute_type_escapes(empty, "python"),
        "L1.16": lambda: indicators._trailing_whitespace(empty),
        "L1.17": lambda: indicators._god_files(empty),
        "absolute_paths": lambda: absolute_paths.scan(empty, "python"),
    }
    assert known[check]()["band"] == "Healthy"
