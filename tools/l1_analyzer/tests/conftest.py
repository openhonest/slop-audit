"""Session-scoped fixtures for the analyses that read the whole tree.

Four tests in test_vacuity.py and two in test_no_dead_code_in_this_repo.py each ran a
whole-package analysis of the same unchanged tree. The two dead-code ones alone cost 28
seconds of a 153-second suite.

A suite that takes minutes is a suite people stop waiting for, and four pre-commit gates
are only as good as how often someone runs them. Session scope is safe here because both
analyses are pure over a tree that no test writes to: every test that mutates source does
it in its own tmp_path.
"""

import pathlib

import pytest
from l1_analyzer import dead_code, vacuity

PACKAGE = pathlib.Path(vacuity.__file__).parent
REPOSITORY = pathlib.Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def vacuity_of_the_package() -> dict:
    """`vacuity.check` over this package, run once."""
    return vacuity.check(PACKAGE)


@pytest.fixture(scope="session")
def dead_code_of_the_repository() -> dict:
    """`dead_code.analyze` over this repository, run once."""
    return dead_code.analyze(REPOSITORY, "python")
