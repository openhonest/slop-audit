"""The version stamp has to survive installation, and the first one did not.

`--version` reported 1.0.0 across 225 commits until this afternoon, and an adopter quoted
numbers from builds they could not name. The fix appended the commit, read from git at
runtime, which works when the tool runs from a checkout and does nothing when it does not.

`uv tool install` copies the package out of the checkout, so the installed copy sits in a
directory with no repository behind it. That is how the tool is actually used, and it is
the exact case that produced the retracted numbers: the same adopter reported 213, then 61,
then 14 problems on unchanged code across three builds all calling themselves 1.0.0.

So the commit is written at BUILD time into a file the package carries, and read at runtime
if it is there. Nothing new was added to do it: `custom` is one of hatchling's own build
hooks, and hatchling is already the build backend.
"""

import pathlib
import subprocess

from l1_analyzer import cli

_PACKAGE = pathlib.Path(cli.__file__).parent


def test_the_build_hook_exists_and_names_the_file_it_writes():
    hook = _PACKAGE.parent / "hatch_build.py"
    assert hook.is_file(), "the build hook is what makes an installed build nameable"
    assert "_build.py" in hook.read_text()


def test_a_stamp_written_at_build_time_is_read_where_there_is_no_repository(tmp_path):
    """The installed case. A directory with no repository still names its commit.

    Git is asked first and this is the fallback, which is the opposite of the first draft.
    A checkout knows its own commit and the file records the commit the wheel was built at,
    so in a working tree the file is stale by however many commits have landed since: the
    suite failed on exactly that within the hour."""
    (tmp_path / "_build.py").write_text('COMMIT = "abcd1234"\nDIRTY = False\n')
    assert cli.build_stamp(str(tmp_path)) == "+gabcd1234"


def test_a_stamp_recording_an_edited_tree_says_so(tmp_path):
    (tmp_path / "_build.py").write_text('COMMIT = "abcd1234"\nDIRTY = True\n')
    assert cli.build_stamp(str(tmp_path)) == "+gabcd1234.dirty"


def test_a_checkout_with_no_written_stamp_still_asks_git():
    """The developer case, which is how this repository runs its own suite."""
    assert "+g" in cli.build_stamp(str(_PACKAGE))


def test_neither_source_invents_a_commit(tmp_path):
    """A directory with no stamp and no repository names none, because the release number
    alone is honest and a made-up commit is not."""
    assert cli.build_stamp(str(tmp_path / "nowhere")) == ""


def test_a_built_wheel_carries_the_commit(tmp_path):
    """End to end, because everything above tests the halves. This is the case that failed."""
    built = subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
                           cwd=_PACKAGE.parent, capture_output=True, text=True, timeout=300,
                           check=False)
    assert built.returncode == 0, built.stderr[-800:]
    import zipfile

    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        stamp = archive.read("l1_analyzer/_build.py").decode()
    here = subprocess.run(["git", "rev-parse", "--short=8", "HEAD"], cwd=_PACKAGE,
                          capture_output=True, text=True, check=True).stdout.strip()
    assert here in stamp, (here, stamp)


def test_the_build_hook_is_scoped_as_tooling_rather_than_production():
    """A build tool reads it and calls what it finds; the program never does.

    That is the same fact as `setup.py`, `conftest.py` and `noxfile.py`, which this
    repository already scopes as tooling. Without it the dead-code reader reported the hook
    class and its helpers unreferenced, and they are: hatchling discovers the class by
    scanning the module for a subclass of its interface, which no reader of the source can
    see and no reference in the source records."""
    from l1_analyzer import scope

    assert "hatch_build.py" in scope._TOOLING_FILES
