"""A whole-package scan is done once per session, not once per test that wants it.

Four tests in test_vacuity.py and two in test_no_dead_code_in_this_repo.py each ran a
whole-package analysis, and each is the same analysis over the same unchanged tree. The
two dead-code tests alone cost 28 seconds of a 153-second suite.

This is not a micro-optimisation. A suite that takes minutes is a suite people stop
running before they push, and the four gates in this repository are only as good as how
often someone waits for them. The session-scoped fixtures below do the work once, and this
test is what stops the next whole-package scan from being written inline again.
"""

import pathlib
import re

import pytest


@pytest.mark.parametrize("name", ["test_vacuity.py", "test_no_dead_code_in_this_repo.py"])
def test_no_test_runs_a_whole_package_scan_of_its_own(name):
    """Counted over the file's code. The fixtures in conftest.py are where these live now,
    and a test that calls the scanner directly on the package is one that will run it
    again."""
    source = pathlib.Path(__file__).parent.joinpath(name).read_text()
    inline = [n for n, line in enumerate(source.split("\n"), start=1)
              if re.search(r"\b(?:vacuity\.check|dead_code\.analyze)\(\s*(?:PKG|REPO|_PKG)\b",
                           line.split("#", 1)[0])]
    assert not inline, (
        f"{name} runs a whole-package scan inline at line(s) {inline}; ask for the "
        "session-scoped fixture instead, so the tree is analyzed once"
    )
