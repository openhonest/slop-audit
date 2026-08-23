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


# --------------------------------------------------------------------------
# Clauses 2 and 3, the class that is only data and the method that is only a function
#
# They port together because they read the same four shapes: the classes, the methods in
# each, the constructor among those, and whether a method reaches the receiver for anything
# more than data. Porting one and leaving the other would have put two readings of "a
# method touches self" in the package, which is the defect this file exists to refuse.
#
# The constructor is the one shape the vocabulary did not carry. Python spells it `__init__`
# and JavaScript spells it `constructor`, and a clause that hard-codes either is a clause
# that means something different in the other language.
# --------------------------------------------------------------------------

DATA_ONLY = {
    "python": ("class User:\n"
               "    def __init__(self, email, name):\n"
               "        self.email = email\n"
               "        self.name = name\n\n"
               "    def get_email(self):\n"
               "        return self.email\n"),
    "javascript": ("class User {\n"
                   "  constructor(email, name) {\n"
                   "    this.email = email;\n"
                   "    this.name = name;\n"
                   "  }\n\n"
                   "  getEmail() {\n"
                   "    return this.email;\n"
                   "  }\n"
                   "}\n"),
}

DOES_WORK = {
    "python": ("class User:\n"
               "    def __init__(self, email, name):\n"
               "        self.email = email\n"
               "        self.name = name\n\n"
               "    def rename(self, name):\n"
               "        self.name = name\n"),
    "javascript": ("class User {\n"
                   "  constructor(email, name) {\n"
                   "    this.email = email;\n"
                   "    this.name = name;\n"
                   "  }\n\n"
                   "  rename(name) {\n"
                   "    this.name = name;\n"
                   "  }\n"
                   "}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_class_that_only_holds_data_is_found_in_this_language(language):
    found = rules.data_classes(read.read_tree(DATA_ONLY[language], language))
    assert [f["symbol"] for f in found] == ["User"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_class_whose_method_writes_the_receiver_is_quiet(language):
    """The one thing that separates data from an object: a method that writes the receiver
    is doing something a free function taking the data could not."""
    assert rules.data_classes(read.read_tree(DOES_WORK[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_class_with_no_constructor_is_not_a_data_class(language):
    """The constructor assigning its parameters is the whole shape. Without one there is no
    evidence the class holds data at all."""
    source = {"python": "class User:\n    def get_email(self):\n        return self.email\n",
              "javascript": ("class User {\n  getEmail() {\n"
                             "    return this.email;\n  }\n}\n")}
    assert rules.data_classes(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_method_reaching_the_receiver_only_for_data_is_found(language):
    found = rules.methods_wearing_a_class(read.read_tree(DATA_ONLY[language], language))
    assert [f["symbol"] for f in found] == ["User.getEmail" if language == "javascript"
                                            else "User.get_email"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_method_that_writes_the_receiver_is_not_a_free_function(language):
    assert rules.methods_wearing_a_class(read.read_tree(DOES_WORK[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_constructor_is_named_by_the_vocabulary_rather_than_by_this_clause(language):
    """A clause spelling `__init__` measures something different in JavaScript, quietly."""
    spec = LANG_SPEC[language]
    assert spec["constructor_names"], language
    assert ("__init__" in spec["constructor_names"]) == (language == "python")


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_class_wrapping_a_resource_is_left_alone(language):
    """Acceptable when it wraps a stateful external resource, in the rule's own words. The
    constructor opening something is the evidence, and it is the same evidence either
    side of the language line."""
    source = {"python": ("class Pool:\n"
                         "    def __init__(self, dsn):\n"
                         "        self.conn = connect(dsn)\n\n"
                         "    def close(self):\n"
                         "        self.conn.close()\n"),
              "javascript": ("class Pool {\n"
                             "  constructor(dsn) {\n    this.conn = connect(dsn);\n  }\n\n"
                             "  close() {\n    this.conn.close();\n  }\n}\n")}
    assert rules.data_classes(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_method_that_calls_another_method_is_left_alone(language):
    """Calling a sibling is not fetching data. A free function taking the record could not
    do it, which is the whole test the clause applies."""
    source = {"python": ("class User:\n"
                         "    def check(self):\n        return self.validate()\n"),
              "javascript": ("class User {\n  check() {\n"
                             "    return this.validate();\n  }\n}\n")}
    assert rules.methods_wearing_a_class(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_language_with_no_constructor_shape_says_it_could_not_decide(language):
    """Rust, C and Go have no constructor this vocabulary names. Returning the empty list
    there would read as "no data classes in this file", which is a claim nothing checked."""
    for absent in ("rust", "c", "go"):
        assert rules.data_classes(read.read_tree("", absent)) is None, absent
    assert rules.data_classes(read.read_tree("", language)) is not None


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_keyword_argument_beside_the_bases_is_not_a_base(language):
    """`class LangSpec(TypedDict, total=False)` names one base and one option. Python puts
    both in the same argument list, so reading every identifier under the holder made this
    package's own vocabulary look like it inherited from something called `total`."""
    source = {"python": "class Row(TypedDict, total=False):\n    name: str\n",
              "javascript": "class Row extends Object {}\n"}
    tree = read.read_tree(source[language], language)
    node = read.class_nodes(tree["root"], tree["spec"])[0]
    assert "total" not in read.base_names(node, tree["spec"], tree["raw"])
    assert read.base_names(node, tree["spec"], tree["raw"]) == (
        ["TypedDict"] if language == "python" else ["Object"])
