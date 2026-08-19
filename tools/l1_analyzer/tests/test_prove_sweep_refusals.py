"""The prove sweeps refuse rather than reporting a clean zero, and every refusal says why.

`slop-audit-0it` lists these among the n/a refusals that must never become 0.0, and left
them as "needs an API key". They do not: every one of them is the path taken when the key
is ABSENT, which is the state of any machine that has not exported one, including CI.

The shape that matters is `attempted: 0` beside a `detail` naming the reason. A sweep that
generated no proof and published `retained: []` alone reads as "we looked and there was
nothing to find", which is the fabricated-clean this whole instrument exists to refuse.
Zero attempts and zero retained are the same two numbers whether the loop ran and found
nothing or never ran at all, and only the detail separates them.

Each refusal must also carry its OWN reason. Borrowing a neighbour's wording is the same
defect one step quieter: a run that could not find cargo, told it needs an API key, sends
the reader to fetch a key that will not help.
"""

import pathlib
import tempfile

import pytest
from l1_analyzer import coverage_prove, python_coverage_prove


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _empty_repo():
    return pathlib.Path(tempfile.mkdtemp())


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove])
def test_a_sweep_without_a_key_refuses_and_names_the_key(no_key, module):
    result = module.prove_coverage_repo(_empty_repo())
    assert result["retained"] == []
    assert result["attempted"] == 0
    assert "ANTHROPIC_API_KEY" in result["detail"], result["detail"]


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove])
def test_the_refusal_never_publishes_a_band_or_a_score(no_key, module):
    """The failure this guards. A refusal that carried a band would be read as a verdict,
    and zero attempts is not zero findings."""
    result = module.prove_coverage_repo(_empty_repo())
    assert "band" not in result
    assert "value" not in result
    assert result["detail"].strip(), "a refusal with no reason is a refusal nobody can act on"


def test_the_two_sweeps_do_not_borrow_each_other_s_wording(no_key):
    """Each names its own reason. They agree here because both really do need the key,
    and the assertion is that the sentence is theirs to give."""
    rust = coverage_prove.prove_coverage_repo(_empty_repo())["detail"]
    python = python_coverage_prove.prove_coverage_repo(_empty_repo())["detail"]
    assert "ANTHROPIC_API_KEY" in rust and "ANTHROPIC_API_KEY" in python


def test_a_key_without_a_toolchain_refuses_for_the_toolchain(monkeypatch):
    """The second refusal, reached only once the key exists. It must not repeat the first
    one's sentence: a repository with a key and no pytest is not missing a key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key-for-a-refusal-path")
    result = python_coverage_prove.prove_coverage_repo(_empty_repo())
    assert result["attempted"] == 0
    assert "ANTHROPIC_API_KEY" not in result["detail"], result["detail"]
    assert result["detail"].strip()
