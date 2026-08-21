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

import contextlib
import pathlib
import re
import subprocess
import tempfile

import pytest
from l1_analyzer import (
    absolute_paths,
    interleaving_robustness,
    secret_scan,
    thread_surface,
)
from l1_analyzer.incomplete import IncompleteCode

# The three states a test tree can be in, written out so the partition is three and every
# call site names the one it depends on. Two booleans had a fourth cell, stage-without-git,
# which cannot exist and which the old body ignored in silence.
NO_GIT = "no-git"
GIT_EMPTY_INDEX = "git-empty-index"
GIT_STAGED = "git-staged"


def _leave_alone(root: pathlib.Path) -> None:
    """No git. The scanners walk the filesystem, so every file written is a file read."""


def _git_init(root: pathlib.Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


def _git_init_and_stage(root: pathlib.Path) -> None:
    _git_init(root)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)


_PREPARE = {
    NO_GIT: _leave_alone,
    GIT_EMPTY_INDEX: _git_init,
    GIT_STAGED: _git_init_and_stage,
}


@contextlib.contextmanager
def _tree(files: dict[str, str], state: str):
    """A temp repository in one of the three states above, released on exit.

    GIT_EMPTY_INDEX is the read-nothing case for L1.14 and not a contrivance: it is a
    fresh checkout before the first commit, and a repository whose tracked paths all sit
    under an ignored directory reaches it too. The scanner reads the index rather than the
    filesystem, so an empty index means it opens no file at all.

    `state` is required and read by subscript, so an unnamed state raises here instead of
    being filed under whichever tree the helper happened to build by default.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        _PREPARE[state](root)
        yield root


# --- L1.14: a clean bill on a tree it never opened -----------------------------------

def test_l1_14_refuses_when_it_opened_no_file():
    """The defect: every file excluded by the index, and the band still says Healthy."""
    with _tree({"app.py": "x = 1\n"}, GIT_EMPTY_INDEX) as root:
        r = secret_scan.analyze(root, "python")
    assert r["files_scanned"] == 0
    assert r["value"] == "n/a", "a count over no file is not a count"
    assert r["band"] == "n/a", "Healthy here is a clean bill on a repository it never read"


def test_l1_14_refusal_says_why_in_the_details():
    with _tree({"app.py": "x = 1\n"}, GIT_EMPTY_INDEX) as root:
        r = secret_scan.analyze(root, "python")
    assert "no file" in r["details"]


def test_l1_14_still_reports_an_honest_zero():
    """The control. A repository it DID read, with no credential in it, stays Healthy:
    the refusal must separate 'read nothing' from 'read the code and found nothing'.

    NO_GIT is the point of the test and not incidental: the scanner reads the index when
    one exists, so `files_scanned == 1` holds only because this tree is not a working copy.
    """
    with _tree({"app.py": "TOKEN = os.environ['TOKEN']\n"}, NO_GIT) as root:
        r = secret_scan.analyze(root, "python")
    assert r["files_scanned"] == 1
    assert r["value"] == 0 and r["band"] == "Healthy"


def test_l1_14_still_finds_a_credential_in_a_tracked_tree():
    """The second control: staging the file restores the reading, so the refusal is
    about an empty scan and not about git being present."""
    # Assembled from parts, and deliberately not AWS's documented EXAMPLE key: the scanner
    # screens placeholder words, so the sample every reader reaches for is the one value
    # that cannot prove the scanner works.
    key = "AKIA" + "Q7RJ4M2XN5VDPL3B"
    with _tree({"app.py": f'AWS = "{key}"\n'}, GIT_STAGED) as root:
        r = secret_scan.analyze(root, "python")
    assert r["files_scanned"] == 1 and r["value"] == 1 and r["band"] == "Not Healthy"


# --- thread_surface: clean over an empty scope ----------------------------------------

def test_thread_surface_refuses_when_no_file_was_in_scope():
    """The defect: the whole tree bucketed out as tests, and the verdict still says clean."""
    with _tree({"tests/test_a.py": "def test_a():\n    assert True\n"}, NO_GIT) as root:
        ts = thread_surface.scan(root, "python")
    assert ts["bucketed"]["counts"] == {"tests": 1}
    assert ts["verdict"] != thread_surface.CLEAN
    assert ts["verdict"] == thread_surface.UNREAD


def test_thread_surface_refuses_when_the_parser_could_not_read_the_source():
    """The second arm, and the reason this check needs a denominator L1.14 does not.
    The file is opened, decoded and counted, and every node query over it comes back
    empty because the tree is an error. A file count cannot see that; the parse can."""
    with _tree({"app.py": "def broken(:\n  ???\n"}, NO_GIT) as root:
        ts = thread_surface.scan(root, "python")
    assert ts["files_read"] == 1, "the file was opened"
    assert ts["files_parsed"] == 0, "and the parser could not read it"
    assert ts["verdict"] == thread_surface.UNREAD


def test_thread_surface_refusal_is_not_the_no_scanner_refusal():
    """Three facts, three answers. 'No scanner for this language' and 'a scanner that
    read nothing' send the reader to different places, and n/a for both sent them to
    neither."""
    with _tree({"tests/test_a.py": "x = 1\n"}, NO_GIT) as root:
        unread = thread_surface.scan(root, "python")
    with _tree({"main.c": "int main(void){return 0;}\n"}, NO_GIT) as root:
        no_scanner = thread_surface.scan(root, "c")
    assert no_scanner["verdict"] == "n/a"
    assert unread["verdict"] != no_scanner["verdict"]


def test_thread_surface_still_reports_an_honest_clean():
    """The control: a production file that parses and holds no concurrency surface."""
    with _tree({"app.py": "def add(a, b):\n    return a + b\n"}, NO_GIT) as root:
        ts = thread_surface.scan(root, "python")
    assert ts["files_read"] == 1 and ts["files_parsed"] == 1
    assert ts["verdict"] == thread_surface.CLEAN


def test_thread_surface_one_readable_file_is_enough_to_grade():
    """A partial reading is not the same fact as no reading, which is the rule the state
    census settled: umbra admits 0.7% of its declared state and is still graded. One file
    the parser could read carries the verdict, and the counts disclose how thin it was."""
    files = {"ok.py": "def add(a, b):\n    return a + b\n", "bad.py": "def broken(:\n  ???\n"}
    with _tree(files, NO_GIT) as root:
        ts = thread_surface.scan(root, "python")
    assert ts["files_read"] == 2 and ts["files_parsed"] == 1
    assert ts["verdict"] == thread_surface.CLEAN


def test_thread_surface_findings_are_kept_from_a_file_that_did_not_parse():
    """The parse count is a denominator, never a filter. A hazard tree-sitter recovered
    from an error-bearing file is still a hazard, and dropping it to keep the two numbers
    tidy would trade a false clean for a missed finding."""
    src = "import threading\nCACHE = {}\n\ndef broken(:\n  ???\n"
    with _tree({"app.py": src}, NO_GIT) as root:
        ts = thread_surface.scan(root, "python")
    assert ts["files_parsed"] == 0
    assert any(f["kind"] == "unguarded_shared_state" for f in ts["findings"])
    assert ts["verdict"] == thread_surface.EXPOSED, "a finding outranks the refusal"


# --- the dependent meter --------------------------------------------------------------

def test_interleaving_robustness_does_not_inherit_a_manufactured_clean():
    """It reads thread_surface's findings and calls an empty list 'no exposed surface to
    model'. Over an unread scan that is the same fabricated clean one module downstream,
    which is where a fixed defect comes back."""
    with _tree({"src/lib.rs": "pub fn ((( -> {{ ???\n"}, NO_GIT) as root:
        ir = interleaving_robustness.analyze(root, "rust")
    assert ir["verdict"] != interleaving_robustness.CLEAN
    assert ir["verdict"] == interleaving_robustness.NA


def test_interleaving_robustness_still_reports_a_read_clean():
    with _tree({"src/lib.rs": "pub fn add() -> i32 { 1 }\n"}, NO_GIT) as root:
        ir = interleaving_robustness.analyze(root, "rust")
    assert ir["verdict"] == interleaving_robustness.CLEAN


# --- the survey, pinned so the next reader does not have to re-derive it ---------------

# The survey, keyed by check and carrying the measure name each refusal must print. The
# key is what the parametrisation reads by subscript, so a check with no entry raises here
# rather than being surveyed under whichever lambda the dict happened to list first.
_SURVEYED = {
    "L1.16": "L1.16 trailing whitespace",
    "L1.17": "L1.17 god-file concentration",
    "absolute_paths": "absolute-path scan",
}


@pytest.mark.parametrize("check", sorted(_SURVEYED))
def test_the_remaining_empty_denominator_claims_are_recorded(check):
    """These three published a positive property over an empty set until 2026-08-16, and
    now each refuses. The survey did the job it was written for: it was set to pass on the
    behaviour of its day so that it would fail the day someone repaired one of them, and
    all three tripped it at once. The assertions moved here rather than being deleted,
    which is the protocol the old docstring promised.

    It was four until 2026-08-15, when L1.15 left the list the same way; its assertion sits
    in the test below. L1.16 and L1.17 divided by a file count and substituted 0.0 when
    there was no file, and both now route the division through `incomplete.ratio`, which
    has no expression that yields a number over an empty denominator. `absolute_paths` read
    `count == 0` as clean, the same number whether it read a thousand files or none, and it
    now refuses before counting.

    `match` pins the measure, not merely the refusal. Three measures raising one exception
    type would otherwise let any one of them stand in for the other two, and the reader who
    has to act on an n/a needs to know which measure went quiet.
    """
    from l1_analyzer import indicators
    with _tree({"README.md": "nothing here\n"}, NO_GIT) as empty:
        known = {
            "L1.16": lambda: indicators._trailing_whitespace(empty),
            "L1.17": lambda: indicators._god_files(empty),
            "absolute_paths": lambda: absolute_paths.scan(empty, "python"),
        }
        with pytest.raises(IncompleteCode, match=re.escape(_SURVEYED[check])):
            known[check]()


def test_a_fourth_measure_that_grew_the_defect_would_be_caught_here():
    """The self-maintaining half, and the reason the survey above is not the whole test.

    A list of three names goes stale the moment a fourth measure is written, and nobody
    adds their own defect to a ledger. This assertion needs no ledger: over a repository
    holding no file at all, NOTHING was read, so no source indicator may publish a band.
    Every one of them has to come back n/a. A measure added tomorrow that substitutes a
    constant for an empty denominator fails here on the day it lands, whatever it is called
    and whichever module it lives in.

    `lang` is the one entry with no band to check - it reports the detected language, not a
    measurement - so the assertion runs over the results that publish one.
    """
    from l1_analyzer import indicators
    with _tree({}, NO_GIT) as nothing:
        results = indicators.compute_source_indicators(nothing, "python", False, 5.0,
                                                       classify_state_bounds=True,
                                                       python_executable=None)
    banded = {key: r["band"] for key, r in results.items() if isinstance(r, dict)}
    assert banded, "the sweep read no indicator, so it proves nothing"
    assert set(banded.values()) == {"n/a"}, (
        f"a band over a repository with no file in it: "
        f"{ {k: v for k, v in banded.items() if v != 'n/a'} }")


def test_l1_15_no_longer_manufactures_a_band_from_an_empty_denominator():
    """The survey entry above, moved rather than deleted, so the fix is pinned where the
    defect was recorded.

    L1.15 carried two claims over inputs it had not measured, and the second was the worse
    one. Over an empty tree it read Healthy off zero lines. Over a NON-empty tree under a
    thousand production lines it also read Healthy, because `if total_loc > 1000 else 0.0`
    substituted a constant for lines it had counted correctly - a fabricated number over a
    real input rather than an honest refusal over an absent one. Both are gone: no lines
    refuses, and lines are divided by however few there are.
    """
    from l1_analyzer import indicators
    with _tree({"README.md": "nothing here\n"}, NO_GIT) as empty:
        assert indicators._compute_type_escapes(empty, "python")["band"] == "n/a"

    with _tree({"a.py": "v: Any = 1\n" * 20}, NO_GIT) as small:
        measured = indicators._compute_type_escapes(small, "python")
    assert measured["value"] == 1000.0 and measured["band"] == "Slop"

    # Honest zero is the control: a small tree really read and really clean keeps Healthy.
    with _tree({"a.py": "def f(x: int) -> int:\n    return x\n" * 20}, NO_GIT) as clean:
        assert indicators._compute_type_escapes(clean, "python")["band"] == "Healthy"
