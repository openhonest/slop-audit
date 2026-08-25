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


# ---------------------------------------------------------------------------
# The rows of a table are not a table waiting to be written
#
# An adopter classified all 71 sites this clause reported in their source. Forty-six were
# the two halves of a two-entry dispatch table: the clause saw two functions with one shape
# and said "make it a table", and they ARE the table's rows. Four more were method
# declarations on a Protocol, where a list of names with no bodies is the entire point.
#
# Fifty of seventy-one, which is the rate at which a reader learns to skip a field. The
# nineteen real ones were the finding, and they were buried.
#
# Both exemptions are computable. A function named as a value in a table this file declares
# is that table's row. A method on a Protocol is a signature, and every signature in one
# looks like every other by construction.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", LANGUAGES)
def test_two_functions_a_table_names_are_that_table_s_rows(language):
    source = {"python": ("def send_email(data):\n    return post('/email', data)\n\n\n"
                         "def send_sms(data):\n    return post('/sms', data)\n\n\n"
                         "HANDLERS = {'email': send_email, 'sms': send_sms}\n"),
              "javascript": ("function sendEmail(data) {\n  return post('/email', data);\n}\n\n"
                             "function sendSms(data) {\n  return post('/sms', data);\n}\n\n"
                             "const handlers = {email: sendEmail, sms: sendSms};\n")}
    assert rules.functions_of_one_shape(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_same_two_functions_with_no_table_are_still_reported(language):
    """The other direction, and the one that keeps the clause worth having. Without the
    table they are two functions that differ by a word, which is what it exists to find."""
    source = {"python": ("def send_email(data):\n    return post('/email', data)\n\n\n"
                         "def send_sms(data):\n    return post('/sms', data)\n"),
              "javascript": ("function sendEmail(data) {\n  return post('/email', data);\n}\n\n"
                             "function sendSms(data) {\n  return post('/sms', data);\n}\n")}
    assert rules.functions_of_one_shape(read.read_tree(source[language], language))


def test_a_table_naming_only_one_of_the_pair_still_reports_the_pair():
    """Half a table is not a table. If one of the two is a row and the other is not, the
    two are still a pair somebody wrote twice."""
    source = ("def send_email(data):\n    return post('/email', data)\n\n\n"
              "def send_sms(data):\n    return post('/sms', data)\n\n\n"
              "HANDLERS = {'email': send_email}\n")
    assert rules.functions_of_one_shape(read.read_tree(source, "python"))


def test_method_declarations_on_a_protocol_are_signatures_rather_than_a_table():
    """A Protocol is a list of names with no bodies, so every method in one has the shape
    of every other by construction. Reporting them asks an author to collapse the interface
    they were declaring."""
    source = ("class Reader(Protocol):\n"
              "    def read_one(self, path: str) -> bytes:\n        ...\n\n"
              "    def read_all(self, path: str) -> bytes:\n        ...\n")
    assert rules.functions_of_one_shape(read.read_tree(source, "python")) == []


def test_methods_on_an_ordinary_class_are_still_reported():
    """The exemption is the Protocol, not the class. Two identical methods on a real class
    are two methods somebody wrote twice."""
    source = ("class Sender:\n"
              "    def send_email(self, data):\n        return post('/email', data)\n\n"
              "    def send_sms(self, data):\n        return post('/sms', data)\n")
    assert rules.functions_of_one_shape(read.read_tree(source, "python"))
