"""Clause 1's other half: the table was built, and then filled with code.

The clause has read if/elif chains since it was written. It has never read the case that
comes after somebody takes its advice: a dispatch table whose values are sixteen functions
that are the same function with different words in them. The table is there, so the clause
was quiet, and the thing the principle exists to produce was never produced.

This was found in a real package on 2026-08-23. An agent was asked to turn sixteen SQL
generators into one function over a table of templates, said the words back correctly, and
wrote sixty functions instead. Nothing in the audit said so. The repository-wide duplicate
measure did fire, at the worst band, and a percentage over a whole repository is not
something anyone acts on.

WHAT THIS DECIDES. Two functions leave the same shape behind when every name and every
quoted string is erased. That is mechanical.

IT IS AN OPINION, AND IT SAYS SO. This clause lives in L1.21, which is opt-in and which
nobody reaches by accident. Everything else in the audit grades a stranger's code and hedges
accordingly; this one is for people who have already accepted that two functions differing
by a word are two rows of a table. So it states the position, it is strict, and it exits
non-zero. A reader who disagrees about one group declares it with the allow marker.
"""

import pytest
from l1_analyzer import honest_code_read as read
from l1_analyzer import honest_code_rules as rules

LANGUAGES = ["python", "javascript"]

TWO_OF_ONE = {
    "python": (
        "def rename_table(table, details):\n"
        "    name = details['new_name']\n"
        "    return [f'ALTER TABLE \"{table}\" RENAME TO \"{name}\"']\n\n\n"
        "def rename_column(table, details):\n"
        "    name = details['to_column']\n"
        "    return [f'ALTER TABLE \"{table}\" RENAME COLUMN \"{name}\"']\n"
    ),
    "javascript": (
        "function renameTable(table, details) {\n"
        "  const name = details['new_name'];\n"
        "  return [`ALTER TABLE ${table} RENAME TO ${name}`];\n"
        "}\n\n"
        "function renameColumn(table, details) {\n"
        "  const name = details['to_column'];\n"
        "  return [`ALTER TABLE ${table} RENAME COLUMN ${name}`];\n"
        "}\n"
    ),
}

TWO_DIFFERENT = {
    "python": (
        "def rename_table(table, details):\n"
        "    name = details['new_name']\n"
        "    return [f'ALTER TABLE \"{table}\" RENAME TO \"{name}\"']\n\n\n"
        "def create_table(table, details):\n"
        "    body = []\n"
        "    for column in details['columns']:\n"
        "        body.append(render(column))\n"
        "    return [f'CREATE TABLE \"{table}\" ({body})']\n"
    ),
    "javascript": (
        "function renameTable(table, details) {\n"
        "  const name = details['new_name'];\n"
        "  return [`ALTER TABLE ${table} RENAME TO ${name}`];\n"
        "}\n\n"
        "function createTable(table, details) {\n"
        "  const body = [];\n"
        "  for (const column of details['columns']) {\n"
        "    body.push(render(column));\n"
        "  }\n"
        "  return [`CREATE TABLE ${table} (${body})`];\n"
        "}\n"
    ),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_two_functions_that_are_one_function_are_found(language):
    found = rules.functions_of_one_shape(read.read_tree(TWO_OF_ONE[language], language))
    assert len(found) == 1, found
    assert "rename" in found[0]["symbol"].lower()


@pytest.mark.parametrize("language", LANGUAGES)
def test_two_functions_that_do_different_things_are_quiet(language):
    """The other direction. A rule that fires on any two functions in a file measures
    nothing, and this is the fixture that catches such a rule."""
    assert rules.functions_of_one_shape(read.read_tree(TWO_DIFFERENT[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_finding_names_every_function_in_the_group(language):
    """A count is not actionable. The reason the repository-wide duplicate measure did not
    stop this is that it reported a percentage and named nothing."""
    found = rules.functions_of_one_shape(read.read_tree(TWO_OF_ONE[language], language))
    named = found[0]["symbol"] + found[0]["detail"]
    assert named.count("rename") >= 2 or named.lower().count("rename") >= 2


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_finding_states_the_opinion_rather_than_hedging_it(language):
    """It used to carry a line saying one function might not do. That hedge belongs in the
    general audit, which grades anyone's code. L1.21 is opt-in and states the Honest
    position, so a reader who disagrees on one group declares it with the allow marker
    instead of reading a hedge on every group."""
    found = rules.functions_of_one_shape(read.read_tree(TWO_OF_ONE[language], language))
    assert found[0]["undecided"] == ""


@pytest.mark.parametrize("language", LANGUAGES)
def test_even_two_one_line_wrappers_are_a_table_with_two_rows(language):
    """The opinionated end, and it is deliberate. This clause lives in L1.21, which is
    opt-in, so nobody meets it who has not accepted that two functions differing by a word
    are two rows somebody wrote as code.

    The strictness is close to free. Measured on this package, the smallest body worth
    comparing can be 6 leaves or 16 and the count moves by one, because real code does not
    sit near that boundary. So the floor is set low, where it reads the one-line pair the
    principle is actually about."""
    source = {"python": "def a(x):\n    return go(x)\n\n\ndef b(x):\n    return stop(x)\n",
              "javascript": ("function a(x) {\n  return go(x);\n}\n\n"
                             "function b(x) {\n  return stop(x);\n}\n")}
    assert rules.functions_of_one_shape(read.read_tree(source[language], language))


def test_the_clause_reports_this_beside_its_dispatch_chains():
    """One principle, two ways of breaking it. A chain that should be a table, and a table
    filled with code that should be rows."""
    source = read.read_tree(TWO_OF_ONE["python"], "python")
    found = rules.dispatch_chains(source)
    assert any(f["clause"] == "L1.21.1" for f in found), found


def test_the_group_is_reported_at_its_first_function_in_the_file():
    """The line has to be stable, and `walk` promises no order.

    A group of two was reported at whichever member the walk happened to return first,
    which for one fixture was the second function in the file. The number a reader is given
    is where they put the allow marker, so an anchor that can move between runs is an allow
    marker that stops working for a reason nobody can see."""
    source = read.read_tree(TWO_OF_ONE["python"], "python")
    found = rules.functions_of_one_shape(source)
    assert found[0]["line"] == 1, found
    assert found[0]["symbol"] == "rename_table, rename_column", found
