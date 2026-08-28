"""Thirty-one command-line flags, each written out, and the audit counted the repeat.

Our own duplication check reports 9.4 per cent of this repository's production lines inside
a repeated window, and the largest single contributor is this: 127 lines in the command-line
module, in eighteen runs. Every run is another `parser.add_argument` with the same shape and
different words.

That is a table written as code, which is the first rule this instrument enforces on other
people: when the thing that varies is the data, put the data in a table and write the code
once. We were charging others for it and paying it ourselves.

The table is also the only place a reader can see every flag at once, which the eighteen
scattered calls never allowed.
"""

import argparse

import pytest
from l1_analyzer import cli


def _parsed(argv: list[str]) -> argparse.Namespace:
    return cli.build_parser().parse_args(argv)


def test_every_flag_lives_in_the_table():
    """The shape, asserted rather than described. A flag added as a call rather than a row
    is the duplication coming back."""
    import inspect

    source = inspect.getsource(cli.build_parser)
    assert source.count("add_argument") <= 1, source


def test_the_table_names_every_flag_the_parser_offers():
    """Nothing is added outside the table, and nothing in the table goes missing."""
    named = {row["flags"][0] for row in cli.FLAGS if row["flags"][0].startswith("--")}
    offered = {a for a in cli.build_parser()._option_string_actions if a.startswith("--")}
    assert offered - {"--help"} == named


@pytest.mark.parametrize(("argv", "attribute", "expected"), [
    (["--gate"], "gate", True),
    (["--verbose"], "verbose", True),
    (["--max-type-escapes", "7"], "max_type_escapes", 7),
    (["--prove-max", "9"], "prove_max", 9),
    ([], "prove_max", 3),
    ([], "max_type_escapes", None),
])
def test_each_flag_still_parses_the_way_it_did(argv, attribute, expected):
    assert getattr(_parsed(argv), attribute) == expected


def test_every_flag_carries_help_a_reader_can_use():
    """A row with no help is a flag nobody can discover, and a table makes that checkable
    where thirty-one separate calls did not."""
    missing = [row["flags"][0] for row in cli.FLAGS if not row.get("help", "").strip()]
    assert missing == [], missing


def test_the_table_found_two_flags_with_no_help_at_all():
    """Recorded because it is what the table bought. `--format` and `--verbose` had shipped
    with no help text since they were added, and thirty-one scattered calls gave nobody a
    place to notice. Both are written now and the test above keeps them written."""
    for flag in ("--format", "--verbose"):
        row = next(r for r in cli.FLAGS if r["flags"][0] == flag)
        assert row["help"].strip(), flag


def test_the_positional_argument_is_in_the_table_too():
    """It is a row like any other, so nothing sits outside the one place a reader looks."""
    assert any(not row["flags"][0].startswith("-") for row in cli.FLAGS)
