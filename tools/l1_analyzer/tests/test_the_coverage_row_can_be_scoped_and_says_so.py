"""The coverage row takes build arguments, and says what it was scoped by.

A workspace can hold a target that will not build, and one that will not build fails the
whole build. The prove sweep grew `--cargo-arg` for that on 2026-09-06; L1.19 did not,
because it goes through a nine-language dispatch whose signature had nowhere for the
argument to travel. So a repository the sweep could now read still read n/a on the row every
reader looks at first.

The parameter is not Rust-shaped. Every language's harness has a build tool and any of them
may need arguments; Rust is simply the first to read them.

Two disclosures, and they are the point of the change rather than decoration. A figure over
part of a workspace is a different number from one over all of it, so what the run was
scoped by prints beside the figure. And a language whose harness takes no arguments must say
that arguments were given and not applied, rather than measuring as though nothing was
asked: a reading that quietly narrowed is worse than one that refuses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from l1_analyzer import indicators


def _row(lang: str, build_args: tuple[str, ...], harness) -> dict:
    return indicators._runtime_coverage(
        Path("/nonexistent"), lang, 1.0, None, build_args, harness)


def _measured(repo, timeout, override, build_args):
    return {"value": 88.0, "band": "Healthy", "details": "88/100 regions exercised"}


def test_a_scoped_run_names_its_scope_beside_the_figure():
    row = _row("rust", ("--workspace", "--exclude", "turso_sqlite3"),
               {"rust": _measured})
    assert "88" in str(row["value"])
    assert "--exclude turso_sqlite3" in row["details"], row["details"]


def test_an_unscoped_run_says_nothing_about_scope():
    """The other direction. A line about scoping on a run that scoped nothing is noise, and
    a reader who meets it once stops reading the ones that mean something."""
    row = _row("rust", (), {"rust": _measured})
    assert "scoped" not in row["details"], row["details"]


def test_a_language_whose_harness_takes_no_arguments_says_they_were_not_applied():
    """The quiet narrowing this exists to stop. Nine harnesses take the parameter and one
    reads it, so the other eight would have measured as though nothing had been asked."""
    row = _row("python", ("--workspace",), {"python": _measured})
    assert "not applied" in row["details"], row["details"]
    assert "python" in row["details"]


@pytest.mark.parametrize("lang", sorted(indicators._COVERAGE_HARNESS))
def test_every_harness_in_the_table_takes_the_parameter(lang):
    """One signature for the table, checked rather than assumed. A harness that quietly kept
    the old three-argument shape would raise on the first run that passed an argument, and
    only for its own language."""
    import inspect

    assert len(inspect.signature(indicators._COVERAGE_HARNESS[lang]).parameters) == 4
