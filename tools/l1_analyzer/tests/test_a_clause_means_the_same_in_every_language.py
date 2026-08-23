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


# --------------------------------------------------------------------------
# Clause 14, the implicit default
#
# A literal default cannot be told from a caller who chose that value, and it manufactures
# an input region no test exercises. A default binding a collaborator is the opposite: it
# puts a dependency in the signature, which is what clause 13 asks for.
#
# Java has no default parameters at all. That is not this reader failing to read Java; it
# is a question that cannot arise there, and the two are different verdicts.
# --------------------------------------------------------------------------

LITERAL_DEFAULT = {
    "python": "def send(channel, timeout=30):\n    return go(channel, timeout)\n",
    "javascript": ("function send(channel, timeout = 30) {\n"
                   "  return go(channel, timeout);\n}\n"),
}

NO_DEFAULT = {
    "python": "def send(channel, timeout):\n    return go(channel, timeout)\n",
    "javascript": ("function send(channel, timeout) {\n"
                   "  return go(channel, timeout);\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_literal_default_is_found_in_this_language(language):
    found = rules.implicit_defaults(read.read_tree(LITERAL_DEFAULT[language], language))
    assert [f["symbol"] for f in found] == ["send(timeout)"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_same_signature_without_the_default_is_quiet(language):
    assert rules.implicit_defaults(read.read_tree(NO_DEFAULT[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_default_binding_a_collaborator_is_not_an_implicit_default(language):
    """It makes a dependency visible in the signature. Flagging it would push the code back
    toward the module-level lookup clause 13 exists to remove."""
    source = {"python": "def send(channel, clock=default_clock()):\n    return clock\n",
              "javascript": ("function send(channel, clock = defaultClock()) {\n"
                             "  return clock;\n}\n")}
    assert rules.implicit_defaults(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_empty_container_default_is_a_literal_too(language):
    """The commonest one, and the one that bites: a shared mutable default nobody chose."""
    source = {"python": "def send(channel, tags=[]):\n    return tags\n",
              "javascript": "function send(channel, tags = []) {\n  return tags;\n}\n"}
    found = rules.implicit_defaults(read.read_tree(source[language], language))
    assert [f["symbol"] for f in found] == ["send(tags)"], found


def test_a_language_with_no_default_parameters_says_the_question_cannot_arise():
    """Java has no default parameter. Reporting "unreadable" there would claim a gap in
    this reader that is really a fact about the language, and reporting the empty list
    would claim the file was checked and found clean."""
    assert rules.implicit_defaults(read.read_tree("class U { void f(int a) {} }", "java")) is None


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("kind", ["number", "string", "boolean", "nothing", "list", "map"])
def test_every_kind_of_literal_default_is_found(language, kind):
    """Each kind separately, because a reader that caught the number and missed the empty
    map would pass a single fixture and leave the commonest case of the rule unmeasured."""
    written = {
        "number": {"python": "30", "javascript": "30"},
        "string": {"python": "'utf-8'", "javascript": "'utf-8'"},
        "boolean": {"python": "True", "javascript": "true"},
        "nothing": {"python": "None", "javascript": "null"},
        "list": {"python": "[]", "javascript": "[]"},
        "map": {"python": "{}", "javascript": "{}"},
    }[kind][language]
    body = {"python": f"def f(x, timeout={written}):\n    return x\n",
            "javascript": f"function f(x, timeout = {written}) {{\n  return x;\n}}\n"}
    found = rules.implicit_defaults(read.read_tree(body[language], language))
    assert [f["symbol"] for f in found] == ["f(timeout)"], (kind, found)


# --------------------------------------------------------------------------
# Clause 13, configuration read from module scope
#
# The WRITE is what makes a module-level value configuration. A table nobody writes is a
# fact about the world, and flagging it would make this clause demand the opposite of
# clauses 1 and 18, which both require exactly such a table. Two clauses of one instrument
# must not ask for opposite things, and the first version of this one did.
#
# Python needs `global` to rebind from inside a function and JavaScript does not, so the
# fixtures differ in that one line and the rule does not mention either.
# --------------------------------------------------------------------------

TURNED_KNOB = {
    "python": ("TIMEOUT = 30\n\n\n"
               "def configure(n):\n    global TIMEOUT\n    TIMEOUT = n\n\n\n"
               "def send(data):\n    return go(data, TIMEOUT)\n"),
    "javascript": ("let timeout = 30;\n\n"
                   "function configure(n) {\n  timeout = n;\n}\n\n"
                   "function send(data) {\n  return go(data, timeout);\n}\n"),
}

PASSED_IN = {
    "python": ("def send(data, timeout):\n    return go(data, timeout)\n"),
    "javascript": ("function send(data, timeout) {\n  return go(data, timeout);\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_module_value_one_function_writes_and_another_reads_is_found(language):
    found = rules.hidden_configuration(read.read_tree(TURNED_KNOB[language], language))
    assert [f["symbol"] for f in found] == [
        "send(timeout)" if language == "javascript" else "send(TIMEOUT)"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_same_value_taken_as_a_parameter_is_quiet(language):
    assert rules.hidden_configuration(read.read_tree(PASSED_IN[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_table_nobody_writes_is_a_fact_rather_than_a_knob(language):
    """The clause that would otherwise demand the opposite of clauses 1 and 18. Both require
    a module-level table read from inside functions, and the first version of this one
    reported every such table as hidden configuration."""
    source = {"python": ("HANDLERS = {'a': one, 'b': two}\n\n\n"
                         "def send(kind):\n    return HANDLERS[kind]()\n"),
              "javascript": ("const handlers = {a: one, b: two};\n\n"
                             "function send(kind) {\n  return handlers[kind]();\n}\n")}
    assert rules.hidden_configuration(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_function_that_turns_the_knob_is_not_itself_reported(language):
    """It is the one place the value is meant to be reached. Reporting it would name the
    setter as the victim of its own setting."""
    found = rules.hidden_configuration(read.read_tree(TURNED_KNOB[language], language))
    assert not [f for f in found if f["symbol"].startswith("configure")], found


SUBSCRIPT_KNOB = {
    "python": ("SETTINGS = {'timeout': 30}\n\n\n"
               "def configure(n):\n    SETTINGS['timeout'] = n\n\n\n"
               "def fetch(url):\n    return get(url, SETTINGS['timeout'])\n"),
    "javascript": ("const settings = {timeout: 30};\n\n"
                   "function configure(n) {\n  settings['timeout'] = n;\n}\n\n"
                   "function fetch(url) {\n  return get(url, settings['timeout']);\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_table_written_by_subscript_is_a_knob_somebody_turns(language):
    """The write need not rebind the name. `SETTINGS['timeout'] = n` leaves the binding
    alone and changes what every reader of it sees, which is the same failure."""
    found = rules.hidden_configuration(read.read_tree(SUBSCRIPT_KNOB[language], language))
    assert [f["symbol"].split("(")[0] for f in found] == ["fetch"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_constant_nothing_can_change_is_not_configuration(language):
    """Nothing about it can differ between two calls, so no caller's behaviour depends on
    something they cannot see."""
    source = {"python": "TIMEOUT = 30\n\n\ndef fetch(url):\n    return get(url, TIMEOUT)\n",
              "javascript": ("const timeout = 30;\n\n"
                             "function fetch(url) {\n  return get(url, timeout);\n}\n")}
    assert rules.hidden_configuration(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_configuration_clause_says_what_it_cannot_see(language):
    """Whether a knob was disguised as a fact is not decidable from a file. A value nobody
    writes here may still be reassigned from another module, and no reading of this file
    sees that."""
    found = rules.hidden_configuration(read.read_tree(SUBSCRIPT_KNOB[language], language))
    assert found
    assert found[0]["undecided"].strip()
