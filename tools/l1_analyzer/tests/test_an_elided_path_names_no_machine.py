"""We charged ourselves for describing the defect we had fixed, and the path was not one.

The absolute-path check reports a machine-specific path written into source, because such a
path breaks on every other checkout and leaks the author's home directory into a committed
artifact. Both harms are real and a comment carries the second one as well as code does, so
this module deliberately does NOT exempt prose, and its own note says so.

The finding on this repository was `/Users/.../tools/x/y.py`, inside a docstring explaining
that a function used to return an absolute name and now returns a relative one. The middle is
cut out. The elision sits exactly where the user name would be, which is the part that leaks,
and nothing can open it either.

So the fix is not "ignore comments". It is that a path somebody has already emptied of its
machine is not a machine-specific path.
"""

import pytest
from l1_analyzer import absolute_paths


def _found(source: str, tmp_path) -> list[dict]:
    (tmp_path / "app.py").write_text(source)
    return absolute_paths.scan(tmp_path, "python").get("findings") or []


@pytest.mark.parametrize("elided", [
    "/Users/.../tools/x/y.py",
    "/home/.../project/out.json",
    "/Users/..../deep/path.py",
])
def test_a_path_with_its_middle_cut_out_is_not_reported(elided, tmp_path):
    assert _found(f'def go():\n    """It returned {elided} once."""\n    return 1\n',
                  tmp_path) == [], elided


def test_a_real_home_path_in_a_comment_is_still_reported(tmp_path):
    """The decision this module already made, and it is right. A comment leaks a user name
    into a committed artifact whether or not the program reads the line."""
    assert _found("# see /Users/someone/tools/x/y.py for the original\ndef go():\n    return 1\n",
                  tmp_path)


def test_a_real_home_path_in_a_docstring_is_still_reported(tmp_path):
    assert _found('def go():\n    """It writes /Users/someone/out.json."""\n    return 1\n',
                  tmp_path)


def test_a_real_home_path_the_code_opens_is_still_reported(tmp_path):
    assert _found('def load():\n    return open("/Users/someone/x.py").read()\n', tmp_path)


def test_a_windows_path_with_its_middle_cut_out_is_not_reported(tmp_path):
    assert _found(r'# it was C:\...\build\out.exe' + "\ndef go():\n    return 1\n", tmp_path) == []


def test_a_real_windows_path_is_still_reported(tmp_path):
    assert _found(r'PATH = "C:\Users\someone\out.exe"' + "\n", tmp_path)
