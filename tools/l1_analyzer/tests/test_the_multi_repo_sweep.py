"""The live sweep runs over several repositories, under one budget, from a named key file.

Three things it owes, and each is a way the sweep could lie about what it did.

It loads the key from a file rather than the ambient environment. A sweep that silently
found a key somewhere is a sweep whose cost nobody authorised; the file it read is named
in the result.

It carries the ceiling per repository AND across the run. Five per repo over six repos is
thirty calls, which is not what "start with five" meant to anyone reading it.

It records every repository it touched, including the ones that refused. A repo skipped
for a missing toolchain has to appear in the result saying so. Dropping it leaves a run
that swept four of six looking like a run that swept four.
"""


import pytest
from l1_analyzer import live_sweep


def test_the_key_is_read_from_a_named_file_not_the_ambient_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nANTHROPIC_API_KEY=sk-test-not-a-real-key\nMORE=2\n")
    assert live_sweep.key_from(env) == "sk-test-not-a-real-key"


def test_a_file_without_the_key_yields_nothing_rather_than_a_guess(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")
    assert live_sweep.key_from(env) is None
    assert live_sweep.key_from(tmp_path / "does-not-exist") is None


def test_a_quoted_value_loses_its_quotes():
    """Shell files quote. A key carrying its own quote marks fails at the API with an
    authentication error, which sends a reader to the account rather than to the file."""
    assert live_sweep._value('ANTHROPIC_API_KEY="sk-quoted"') == "sk-quoted"
    assert live_sweep._value("ANTHROPIC_API_KEY='sk-single'") == "sk-single"
    assert live_sweep._value("ANTHROPIC_API_KEY=sk-bare") == "sk-bare"


def test_the_run_budget_bounds_the_whole_sweep_not_each_repo():
    """Five per repo over six repos is thirty. The run ceiling is what was authorised."""
    assert live_sweep.share(run_ceiling=5, per_repo=5, spent=0) == 5
    assert live_sweep.share(run_ceiling=5, per_repo=5, spent=3) == 2
    assert live_sweep.share(run_ceiling=5, per_repo=5, spent=5) == 0
    assert live_sweep.share(run_ceiling=100, per_repo=5, spent=0) == 5


def test_a_repository_that_refused_still_appears_in_the_run(tmp_path):
    """A repo dropped for a missing toolchain leaves a run that swept four of six looking
    like a run that swept four."""
    result = live_sweep.sweep([tmp_path], key=None, run_ceiling=5, per_repo=5)
    assert len(result["repos"]) == 1
    assert result["repos"][0]["attempted"] == 0
    assert result["repos"][0]["detail"]
    assert result["spent"] == 0


def test_no_key_refuses_the_whole_run_before_touching_a_repository(tmp_path):
    result = live_sweep.sweep([tmp_path], key=None, run_ceiling=5, per_repo=5)
    assert "no ANTHROPIC_API_KEY" in result["detail"]
    assert result["spent"] == 0


@pytest.mark.parametrize("language", ["rust", "python"])
def test_each_language_has_a_sweep_behind_it(language):
    assert language in live_sweep.SWEEPS


def test_an_unset_per_repo_cap_divides_the_run_ceiling_across_the_repositories():
    """Otherwise multi-repo is hollow at a small ceiling.

    With a run ceiling of 5, a per-repository cap of 5 and three repositories, the first
    repository takes the entire budget and the other two are reported as not swept. That
    is a correct sweep of one repository wearing the shape of a sweep of three. When no
    per-repository cap is given, the ceiling is divided so every repository gets a turn.
    """
    assert live_sweep.fair_share(ceiling=5, repos=3) == 2      # 2 + 2 + 1, the run cap still binds
    assert live_sweep.fair_share(ceiling=5, repos=1) == 5
    assert live_sweep.fair_share(ceiling=12, repos=4) == 3
    assert live_sweep.fair_share(ceiling=2, repos=5) == 1      # never zero: a turn each, until the run cap bites
    assert live_sweep.fair_share(ceiling=0, repos=3) == 0


def test_every_repository_is_offered_a_turn_at_the_starting_ceiling(tmp_path):
    """The property the fair share exists for, asserted end to end without a key."""
    repos = []
    for name in ("a", "b", "c"):
        repo = tmp_path / name
        repo.mkdir()
        (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
        repos.append(repo)
    offered = [live_sweep.share(5, live_sweep.fair_share(5, len(repos)), spent)
               for spent in (0, 2, 4)]
    assert offered == [2, 2, 1]
    assert sum(offered) == 5
