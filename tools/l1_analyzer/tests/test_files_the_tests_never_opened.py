"""Which files does the code read that the test run never opened?

Two projects reported the same failure within a day of each other, from repositories with no
shared code. In both, the tests passed while the code was broken, because the tests were
handed a stand-in instead of the real thing.

One edits a settings file. Its 244 tests were green, its branch coverage was 84.6 per cent,
and four defects reached production and damaged 47 records in the live file. Every fixture
was written by the person who wrote the parser, so it held only the shapes he thought to put
there, and the real file had anchors and folded values he had never seen. The other opens a
database through a stand-in that accepted any path. Production never created the folder the
file lives in, and the stand-in could not fail the way opening a file fails.

Coverage cannot see this. Both defects sat inside branches the coverage report already
counted as reached, and repairing them moved that number DOWN.

A text search over the source cannot see it either, and I tried. It reports a file as
untested whenever no test names it, which is wrong for every file a test reaches by calling
the code that opens it.

Watching the run answers it exactly. We already start the suite and already load a plugin
into it, so the run can report every file it opened. What the code reads and the run never
opened is the finding, observed rather than guessed.
"""

import sys
from pathlib import Path

from l1_analyzer import unopened_files

_APP = """from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "real.yaml"


def load(path=None):
    return (path or DATA).read_text()
"""

_TEST_WITH_A_FAKE = """import sys
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])
from pkg.app import load


def test_load(tmp_path):
    fake = tmp_path / "fixture.yaml"
    fake.write_text("schema_version: 3\\n")
    assert "schema_version" in load(fake)
"""

_TEST_THROUGH_PRODUCTION = _TEST_WITH_A_FAKE + """

def test_load_reaches_the_real_file():
    assert "schema_version" in load()
"""


def _repo(tmp_path: Path, test_source: str) -> Path:
    for part in ("pkg", "tests", "data"):
        (tmp_path / part).mkdir()
    (tmp_path / "data" / "real.yaml").write_text("schema_version: 3\n")
    (tmp_path / "pkg" / "app.py").write_text(_APP)
    (tmp_path / "tests" / "test_app.py").write_text(test_source)
    return tmp_path


# ---------------------------------------------------------------------------
# The half that watches
# ---------------------------------------------------------------------------

def test_the_run_reports_a_file_it_opened(tmp_path):
    target = tmp_path / "seen.yaml"
    target.write_text("x\n")
    opened = unopened_files.opened_during(
        lambda: target.read_text(), tmp_path / "out.json")
    assert str(target) in opened


def test_the_run_does_not_report_a_file_it_left_alone(tmp_path):
    target = tmp_path / "unseen.yaml"
    target.write_text("x\n")
    opened = unopened_files.opened_during(lambda: None, tmp_path / "out.json")
    assert str(target) not in opened


# ---------------------------------------------------------------------------
# The half that says which files the code could read
# ---------------------------------------------------------------------------

def test_a_literal_naming_a_file_on_disk_is_a_candidate(tmp_path):
    repo = _repo(tmp_path, _TEST_WITH_A_FAKE)
    assert "data/real.yaml" in unopened_files.files_the_code_names(repo)[0]


def test_a_literal_naming_nothing_on_disk_is_not(tmp_path):
    """The check that turns a guess into a claim. ".html" is a suffix in an f-string, not
    a file, and a search that kept it reported three of this repository's own non-files."""
    repo = _repo(tmp_path, _TEST_WITH_A_FAKE)
    (repo / "pkg" / "page.py").write_text('NAME = f"{slug}.html"\n')
    assert ".html" not in unopened_files.files_the_code_names(repo)[0]


def test_a_name_several_files_share_is_refused_rather_than_guessed(tmp_path):
    """Two files with one basename cannot be told apart from the literal, so the answer
    is that we do not know, never a guess at one of them."""
    repo = _repo(tmp_path, _TEST_WITH_A_FAKE)
    (repo / "pkg" / "real.yaml").write_text("y\n")
    (repo / "pkg" / "other.py").write_text('P = "real.yaml"\n')
    named, ambiguous = unopened_files.files_the_code_names(repo)
    assert "real.yaml" in ambiguous
    assert not any(n.endswith("pkg/real.yaml") for n in named)


# ---------------------------------------------------------------------------
# The finding
# ---------------------------------------------------------------------------

def test_a_file_only_a_fake_stood_in_for_is_reported(tmp_path):
    result = unopened_files.analyze(_repo(tmp_path, _TEST_WITH_A_FAKE), "python", sys.executable, timeout_seconds=300.0)
    assert "data/real.yaml" in result["never_opened"], result


def test_a_file_a_test_reaches_through_the_code_is_not_reported(tmp_path):
    """The case a text search gets wrong. No test names this file; a test calls the
    function that opens it."""
    result = unopened_files.analyze(_repo(tmp_path, _TEST_THROUGH_PRODUCTION), "python",
                                    sys.executable, timeout_seconds=300.0)
    assert result["never_opened"] == [], result


def test_a_suite_that_could_not_run_decides_nothing(tmp_path):
    """Never an empty list. A repository whose suite we could not run was not measured,
    and reporting no findings would be a clean bill on a run that never happened."""
    empty = tmp_path / "nothing"
    empty.mkdir()
    result = unopened_files.analyze(empty, "python", sys.executable, timeout_seconds=300.0)
    assert result["never_opened"] is None
    assert result["details"]


def test_the_result_carries_no_band(tmp_path):
    """An empty list does not mean the tests are good, so there is no grade to give it.
    The list is the finding."""
    result = unopened_files.analyze(_repo(tmp_path, _TEST_WITH_A_FAKE), "python",
                                    sys.executable, timeout_seconds=300.0)
    assert result["band"] == "n/a"


# ---------------------------------------------------------------------------
# Somebody else's code
#
# The first run on this repository reported five files, all of them inside the virtual
# environment. The filter matched the text "/.venv/" against the path, and the walk yields
# paths relative to the repository, which begin ".venv/" with no leading slash. So the
# filter was written for one spelling of a path and handed another.
# ---------------------------------------------------------------------------

def test_a_dependency_is_not_this_repository_however_the_path_is_spelled(tmp_path):
    for spelling in (".venv/bin/pytest", "/abs/repo/.venv/bin/pytest",
                     "node_modules/x/index.js", "pkg/__pycache__/app.pyc"):
        assert not unopened_files._ours(spelling), spelling


def test_the_repositorys_own_code_is_kept(tmp_path):
    for spelling in ("pkg/app.py", "/abs/repo/pkg/app.py", "data/real.yaml",
                     "venvtools/helper.py"):
        assert unopened_files._ours(spelling), spelling


def test_a_dependency_is_not_walked_into(tmp_path):
    """Found on this repository. Five findings, all of them somebody else's binaries,
    reported because a bare name in our source matched a file inside the environment."""
    repo = _repo(tmp_path, _TEST_WITH_A_FAKE)
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "pytest").write_text("#!/bin/sh\n")
    by_path, by_name = unopened_files.files_on_disk(repo)
    assert not [p for p in by_path if ".venv" in p]
    assert "pytest" not in by_name
