"""Every git indicator says what its number is made of (L1.1 through L1.7).

Six of the eight published a bare percentage and nothing else. The feature file named
that as a known gap rather than hiding it, which is better than silence and still leaves
a reader with a band and no way to act on it.

It cost ten commands to answer one question. Asked why this repository reads Slop on
L1.5 and L1.6, I had to re-derive from `git log --numstat` what the analyzer had already
counted and thrown away: 45,197 lines added against 8,865 deleted, and five of 152
commits net-negative. The counts existed. They just were not published.

The rule the two indicators that already had details follow: name the numerator and the
denominator in the units the reader would count in. `16137 doc / 64783 total lines added`
is a sentence somebody can check against their own repository. `24.9` is not.
"""

import pathlib
import subprocess
import tempfile

import pytest

from l1_analyzer import indicators


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    def git(*args):
        env = {"GIT_AUTHOR_DATE": "2026-08-01T10:00:00", "GIT_COMMITTER_DATE": "2026-08-01T10:00:00",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, env=env)

    git("init", "-q")
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n")
    git("add", "-A"); git("commit", "-qm", "code")
    (tmp_path / "doc.md").write_text("# doc\n")
    git("add", "-A"); git("commit", "-qm", "doc")
    (tmp_path / "a.py").write_text("x = 1\n")
    git("add", "-A"); git("commit", "-qm", "prune")
    return tmp_path


@pytest.mark.parametrize("key", ["L1.1", "L1.2", "L1.3", "L1.4", "L1.5", "L1.6", "L1.7", "L1.8"])
def test_every_git_indicator_publishes_the_counts_behind_its_number(tmp_path, key):
    r = indicators.compute_git_indicators(_repo(tmp_path), None, None)
    details = (r[key] or {}).get("details")
    assert details, f"{key} publishes a band with no counts behind it"
    assert any(ch.isdigit() for ch in details), f"{key} details name no number: {details!r}"


def test_the_delete_ratio_names_both_sides_of_its_fraction(tmp_path):
    """The one that sent me to git log. A reader must be able to see the two line counts
    without re-deriving them."""
    r = indicators.compute_git_indicators(_repo(tmp_path), None, None)
    details = r["L1.5"]["details"]
    assert "deleted" in details and "added" in details, details
