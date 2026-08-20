"""The multi-repository sweep can be exercised without a key, a toolchain or a patch.

`live_sweep.sweep` reached for a module-level `SWEEPS` table. Everything past the no-key
refusal was therefore unreachable in a test: to drive it you would have to overwrite
`live_sweep.SWEEPS`, which is the patching the package now forbids. So the body sat at 51%
line coverage and the parts that decide what a run spends were never executed here.

That is the fourth appearance of one lesson, and the first found by coverage rather than by
reading. `_prove_one`, `prove_hazard` and `model_call.call` each reached for a collaborator
and each now asks for one. This did too, and the tell was different: not a test patching a
name, but a body no test could enter at all.

The budget arithmetic is what these cover. It decides how many model calls a run makes
across several repositories, and until now the only evidence it worked was three live runs
that spent real money.
"""

import pathlib

import pytest
from l1_analyzer import live_sweep


def _stub_sweep(attempted: int, retained: int = 0, detail: str = "stub"):
    """Stands in for a language's real coverage sweep. Handed in, not patched."""
    def run(repo, max_attempts):
        return {"attempted": min(attempted, max_attempts), "retained": [{"x": 1}] * retained,
                "detail": detail}
    return run


@pytest.fixture
def three_python_repos(tmp_path) -> list[pathlib.Path]:
    repos = []
    for name in ("a", "b", "c"):
        repo = tmp_path / name
        repo.mkdir()
        (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
        repos.append(repo)
    return repos


def test_a_rust_repository_is_recognised_by_its_manifest(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n")
    assert live_sweep.language_of(tmp_path) == "rust"


@pytest.mark.parametrize("marker", ["pyproject.toml", "setup.py", "setup.cfg"])
def test_a_python_repository_is_recognised_by_any_of_its_markers(tmp_path, marker):
    (tmp_path / marker).write_text("")
    assert live_sweep.language_of(tmp_path) == "python"


def test_a_directory_that_is_neither_names_nothing(tmp_path):
    """Reported as an outcome rather than skipped, so a run that swept four of six does not
    look like a run that swept four."""
    assert live_sweep.language_of(tmp_path) is None


def test_the_run_ceiling_is_spent_across_the_repositories(three_python_repos):
    """The arithmetic that decides what a run costs, executed rather than trusted."""
    result = live_sweep.sweep(three_python_repos, key="sk-not-real", run_ceiling=5, per_repo=2,
                              sweeps={"python": _stub_sweep(attempted=2)})
    assert result["spent"] == 5
    assert [r["attempted"] for r in result["repos"]] == [2, 2, 1]


def test_a_repository_reached_after_the_ceiling_says_so(three_python_repos):
    result = live_sweep.sweep(three_python_repos, key="sk-not-real", run_ceiling=2, per_repo=2,
                              sweeps={"python": _stub_sweep(attempted=2)})
    assert result["spent"] == 2
    assert "ceiling" in result["repos"][1]["detail"]
    assert "ceiling" in result["repos"][2]["detail"]


def test_a_repository_of_no_known_language_is_still_reported(tmp_path, three_python_repos):
    """The property that keeps the count honest: every repository offered appears."""
    stranger = tmp_path / "stranger"
    stranger.mkdir()
    result = live_sweep.sweep([stranger, *three_python_repos], key="sk-not-real",
                              run_ceiling=9, per_repo=3,
                              sweeps={"python": _stub_sweep(attempted=1)})
    assert len(result["repos"]) == 4
    assert result["repos"][0]["language"] is None
    assert "no sweep applies" in result["repos"][0]["detail"]


def test_retained_proofs_travel_with_their_repository(three_python_repos):
    result = live_sweep.sweep(three_python_repos[:1], key="sk-not-real", run_ceiling=5, per_repo=5,
                              sweeps={"python": _stub_sweep(attempted=3, retained=2)})
    assert result["repos"][0]["retained"] == 2
    assert len(result["repos"][0]["proofs"]) == 2


def test_the_summary_counts_repositories_that_actually_ran(three_python_repos):
    result = live_sweep.sweep(three_python_repos, key="sk-not-real", run_ceiling=2, per_repo=2,
                              sweeps={"python": _stub_sweep(attempted=2)})
    assert "1 of 3 repositories" in result["detail"]


def test_no_key_refuses_every_repository_without_asking_the_sweeps(three_python_repos):
    def _must_not_run(repo, max_attempts):
        raise AssertionError("a sweep ran with no key")

    result = live_sweep.sweep(three_python_repos, key=None, run_ceiling=5, per_repo=5,
                              sweeps={"python": _must_not_run})
    assert result["spent"] == 0
    assert len(result["repos"]) == 3


def test_the_sweeps_table_is_a_required_argument():
    """The lesson, held. Reaching for the module's own table is what made everything past
    the no-key refusal unreachable in a test."""
    import inspect

    parameter = inspect.signature(live_sweep.sweep).parameters["sweeps"]
    assert parameter.default is inspect.Parameter.empty
