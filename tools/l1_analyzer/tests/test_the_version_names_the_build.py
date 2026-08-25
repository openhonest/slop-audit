"""`--version` said 1.0.0 for 225 commits, and one of them changed the rules.

An adopter ran an audit, quoted its numbers, and was then told those numbers came from
rules that no longer exist in that form. Nothing in the tool's own output could have told
them: the release number had not moved, and the build date was the only signal, in a place
nobody looks.

This module's `version` docstring already said "a measurement that cannot name the build
behind it cannot be cited later". It was right and the function did not do it.

A release number names a promise about the interface. A commit names the code. A published
measurement needs the second, because the bands and the denominators in this instrument
have both moved under readers before.
"""

import re
import subprocess

from l1_analyzer import cli


def test_the_version_names_the_release():
    assert cli.version().startswith("1.")


def test_a_build_from_a_source_checkout_names_its_commit():
    """The case that failed. Two builds from two commits must not report one string."""
    assert re.search(r"\+g[0-9a-f]{7,}", cli.version()), cli.version()


def test_the_commit_it_names_is_this_one():
    here = subprocess.run(["git", "rev-parse", "--short=8", "HEAD"],
                          cwd=cli.__file__.rsplit("/", 1)[0], capture_output=True,
                          text=True, check=True).stdout.strip()
    assert here in cli.version(), (here, cli.version())


def test_an_edited_tree_says_so():
    """A measurement taken from an edited checkout did not come from that commit, and a
    reader comparing it against the commit would be comparing it against different code."""
    dirty = subprocess.run(["git", "status", "--porcelain"],
                           cwd=cli.__file__.rsplit("/", 1)[0], capture_output=True,
                           text=True, check=True).stdout.strip()
    assert bool(dirty) == cli.version().endswith(".dirty"), (bool(dirty), cli.version())


def test_the_stamp_is_absent_rather_than_wrong_when_there_is_no_repository():
    """Installed from a wheel there is no commit to name, and inventing one would be worse
    than the release number alone."""
    assert cli.build_stamp("/") == ""
