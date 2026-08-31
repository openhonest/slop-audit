"""Which Ruby test suite a repository has, decided from what is on disk.

Ruby has two suite shapes and the commands to measure them differ, so getting this wrong
runs the wrong tool and measures nothing. JavaScript's equivalent detector has been held by
tests since it was written; Ruby's had none, and it decides both the coverage number and the
determinism score for every Ruby repository the tool sees.

Three ways to be an RSpec suite and one to be Minitest, and RSpec wins where both are
present, because a repository that has both usually runs RSpec and keeps the other for
legacy. A repository with neither shape is measured as not applicable and never as zero of
five, which would read as a suite that ran and came out flaky.
"""

import pytest
from l1_analyzer import ruby_trace


def _repo(tmp_path, *, dirs=(), files=()):
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    for name, text in files:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    return tmp_path


def test_a_spec_directory_is_an_rspec_suite(tmp_path):
    assert ruby_trace._detect_runner(_repo(tmp_path, dirs=["spec"])) == "rspec"


def test_an_rspec_dotfile_is_an_rspec_suite(tmp_path):
    """A project can keep its specs elsewhere and still say so in .rspec."""
    assert ruby_trace._detect_runner(_repo(tmp_path, files=[(".rspec", "--require spec_helper\n")])) == "rspec"


def test_rspec_in_the_lockfile_is_an_rspec_suite(tmp_path):
    """The third way, and the one that needs no directory at all: the dependency is declared
    and resolved, so the suite exists whatever it is laid out like."""
    lock = "GEM\n  specs:\n    rspec (3.13.0)\n    rspec-core (3.13.0)\n"
    assert ruby_trace._detect_runner(_repo(tmp_path, files=[("Gemfile.lock", lock)])) == "rspec"


def test_a_test_directory_with_a_rakefile_is_a_minitest_suite(tmp_path):
    assert ruby_trace._detect_runner(_repo(tmp_path, dirs=["test"], files=[("Rakefile", "task :test\n")])) == "minitest"


def test_a_test_directory_with_no_rakefile_is_neither(tmp_path):
    """Minitest is run through Rake here, so a test directory with nothing to run it is not
    a suite this harness can drive. Guessing would run a command that does not exist."""
    assert ruby_trace._detect_runner(_repo(tmp_path, dirs=["test"])) is None


def test_rspec_wins_where_both_shapes_are_present(tmp_path):
    """A repository with both usually runs RSpec and keeps the other for legacy. The
    preference is stated so it cannot drift into whichever check happens to come first."""
    both = _repo(tmp_path, dirs=["spec", "test"], files=[("Rakefile", "task :test\n")])
    assert ruby_trace._detect_runner(both) == "rspec"


def test_a_repository_with_neither_shape_is_told_apart_from_one_that_failed(tmp_path):
    """None, so the caller refuses with the reason. A zero here would read as a suite that
    ran and came out flaky, which is a measurement nobody made."""
    assert ruby_trace._detect_runner(_repo(tmp_path, dirs=["lib"])) is None


@pytest.mark.parametrize("lock", ["GEM\n  specs:\n    minitest (5.20.0)\n",
                                  "GEM\n  specs:\n    rspec-expectations (3.13.0)\n"])
def test_a_lockfile_naming_another_gem_is_not_an_rspec_suite(tmp_path, lock):
    """`rspec-expectations` is a library RSpec uses and can be depended on alone, so a
    substring match on the lockfile would call every project that uses it an RSpec suite."""
    assert ruby_trace._detect_runner(_repo(tmp_path, files=[("Gemfile.lock", lock)])) is None
