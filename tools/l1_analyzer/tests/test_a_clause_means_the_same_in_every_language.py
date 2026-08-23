"""Clause 1, read through the per-language node vocabulary instead of Python's own parser.

L1.21 was written against Python's `ast` module, so a JavaScript file could be graded on
two clauses out of nineteen and nothing structural could be seen at all. The rest of this
analyzer went multi-language long ago: `lang_spec` carries per-language node types for nine
languages and the other twenty indicators read them.

There is one implementation, not two. A second Python-only copy of each rule would be a
value with two owners and nothing checking they agree, which is the defect this package
spent a night removing from four other places.

THE RISK IS NOT THE PORTING. It is silently changing what a clause MEANS while porting it,
so the rule runs on JavaScript and quietly measures something else. Every case below
therefore asserts both directions on the same source: the clause fires on the violation and
goes quiet when the violation alone is removed. A fixture that only fires proves the clause
runs, not that it is reading the thing it names.
"""

import pytest
from l1_analyzer import honest_code_read as read
from l1_analyzer import honest_code_rules as rules
from l1_analyzer.lang_spec import LANG_SPEC

DISPATCH = {
    "python": (
        "def send(channel, data):\n"
        "    if channel == 'email':\n        return send_email(data)\n"
        "    elif channel == 'sms':\n        return send_sms(data)\n"
        "    elif channel == 'push':\n        return send_push(data)\n"
        "    return None\n"),
    "javascript": (
        "function send(channel, data) {\n"
        "  if (channel === 'email') { return sendEmail(data); }\n"
        "  else if (channel === 'sms') { return sendSms(data); }\n"
        "  else if (channel === 'push') { return sendPush(data); }\n"
        "  return null;\n"
        "}\n"),
}

# The same code with the dispatch removed and nothing else changed. This is what makes each
# case above evidence rather than a demonstration that the clause runs at all.
NO_DISPATCH = {
    "python": (
        "def send(channel, data):\n"
        "    return HANDLERS[channel](data)\n"),
    "javascript": (
        "function send(channel, data) {\n"
        "  return HANDLERS[channel](data);\n"
        "}\n"),
}

ORDINARY = {
    "python": (
        "def clamp(n, low, high):\n"
        "    if n < low:\n        return low\n"
        "    elif n > high:\n        return high\n"
        "    return n\n"),
    "javascript": (
        "function clamp(n, low, high) {\n"
        "  if (n < low) { return low; }\n"
        "  else if (n > high) { return high; }\n"
        "  return n;\n"
        "}\n"),
}

LANGUAGES = ["python", "javascript"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_dispatch_chain_is_found_in_this_language(language):
    found = rules.dispatch_chains(read.read_tree(DISPATCH[language], language))
    assert len(found) == 1, found
    assert "channel" in found[0]["symbol"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_same_source_without_the_chain_is_quiet(language):
    """The other direction, on the same code. Without this a fixture proves the clause
    runs, not that it is reading the thing it names."""
    assert rules.dispatch_chains(read.read_tree(NO_DISPATCH[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_ordinary_conditional_is_not_a_dispatch_chain(language):
    """The rule says so itself: bounds checks and null guards are ordinary conditionals. A
    clause that fires on every function with a condition teaches a reader to ignore it."""
    assert rules.dispatch_chains(read.read_tree(ORDINARY[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_two_armed_test_is_not_yet_a_table(language):
    source = {"python": "def f(kind):\n    if kind == 'a':\n        return one()\n    return two()\n",
              "javascript": "function f(kind) {\n  if (kind === 'a') { return one(); }\n  return two();\n}\n"}
    assert rules.dispatch_chains(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_chain_dispatching_on_two_different_names_is_not_one_table(language):
    """One axis of variation, or it is not a table. Two names is ordinary control flow that
    happens to be spelled as a chain."""
    source = {
        "python": ("def f(a, b):\n"
                   "    if a == 1:\n        return one()\n"
                   "    elif b == 2:\n        return two()\n"
                   "    elif a == 3:\n        return three()\n    return None\n"),
        "javascript": ("function f(a, b) {\n"
                       "  if (a === 1) { return one(); }\n"
                       "  else if (b === 2) { return two(); }\n"
                       "  else if (a === 3) { return three(); }\n  return null;\n}\n"),
    }
    assert rules.dispatch_chains(read.read_tree(source[language], language)) == []


# --------------------------------------------------------------------------
# The reader that puts a tree in front of a clause
# --------------------------------------------------------------------------

def test_the_tree_reader_names_the_language_it_read():
    source = read.read_tree("const x = 1;\n", "javascript")
    assert source["language"] == "javascript"
    assert source["root"].type in ("program", "module")


def test_the_tree_reader_carries_the_vocabulary_for_that_language():
    """A clause reads node types from the spec rather than naming them, which is what lets
    one implementation serve every language the spec covers."""
    assert read.read_tree("x = 1\n", "python")["spec"] is LANG_SPEC["python"]


def test_a_language_the_spec_does_not_cover_is_refused():
    """Refused rather than parsed as something else. A tree read with the wrong grammar
    produces findings about a file nobody read, which is the failure this package spent the
    morning removing."""
    with pytest.raises(KeyError):
        read.read_tree("x = 1\n", "klingon")


# --------------------------------------------------------------------------
# Clause 5, inheritance for reuse
# --------------------------------------------------------------------------

INHERITS = {
    "python": "class User:\n    pass\n\n\nclass Admin(User):\n    pass\n",
    "javascript": "class User {}\n\n\nclass Admin extends User {}\n",
}

NO_INHERITANCE = {
    "python": "class User:\n    pass\n\n\nclass Admin:\n    pass\n",
    "javascript": "class User {}\n\n\nclass Admin {}\n",
}

EXCEPTIONS = {
    "python": ("class CheckError(Exception):\n    pass\n\n\n"
               "class ParseError(CheckError):\n    pass\n"),
    "javascript": ("class CheckError extends Error {}\n\n\n"
                   "class ParseError extends CheckError {}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_inheriting_an_implementation_is_found_in_this_language(language):
    found = rules.inheritance_for_reuse(read.read_tree(INHERITS[language], language))
    assert [f["symbol"] for f in found] == ["Admin"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_same_classes_without_the_inheritance_are_quiet(language):
    assert rules.inheritance_for_reuse(read.read_tree(NO_INHERITANCE[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_exception_hierarchy_is_exceptions_all_the_way_down(language):
    """A class deriving from one this file defines as an exception is still an exception,
    however deep. Sixteen of these in one adopter's file fired as violations before the
    bases were followed to their root."""
    assert rules.inheritance_for_reuse(read.read_tree(EXCEPTIONS[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_declared_shape_is_not_inheritance_for_reuse(language):
    source = {"python": "class Row(TypedDict):\n    name: str\n",
              "javascript": "class Row extends Object {}\n"}
    assert rules.inheritance_for_reuse(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_base_names_a_definition_inherits_are_read(language):
    tree = read.read_tree(INHERITS[language], language)
    spec, raw = tree["spec"], tree["raw"]
    # Selected by NAME. `walk` promises no order, which this file's own feature says, and
    # taking the last node was relying on the thing that promise denies.
    admin = next(n for n in read.walk(tree["root"]) if n.type in spec["class_types"]
                 and read.node_text(n, raw).startswith("class Admin"))
    assert rules.base_names(admin, spec, raw) == ["User"]
