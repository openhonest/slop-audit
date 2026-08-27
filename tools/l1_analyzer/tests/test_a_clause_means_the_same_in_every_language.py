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
from l1_analyzer import honest_code_edges as edges
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


# --------------------------------------------------------------------------
# Clause 18, the dispatch table that answers for an input nobody wrote a rule for
#
# The meaning is shared and the spelling is not. Python supplies the fallback as a second
# argument to a method, JavaScript as an operator to the right of the lookup, Java as a
# differently named method. The rule is the same in all three: a table read closed and a
# fallback that files an unknown key under an answer written for a different key.
#
# The table has to be one this file declares. `options.timeout ?? 30` reaches into an
# argument nobody in this file wrote the rules for, and calling that an open dispatch would
# flag most of the JavaScript ever written.
# --------------------------------------------------------------------------

OPEN_TABLE = {
    "python": ("HANDLERS = {'a': one, 'b': two}\n\n\n"
               "def send(kind):\n    return HANDLERS.get(kind, fallback)\n"),
    "javascript": ("const handlers = {a: one, b: two};\n\n"
                   "function send(kind) {\n  return handlers[kind] ?? fallback;\n}\n"),
}

CLOSED_TABLE = {
    "python": ("HANDLERS = {'a': one, 'b': two}\n\n\n"
               "def send(kind):\n    return HANDLERS[kind]\n"),
    "javascript": ("const handlers = {a: one, b: two};\n\n"
                   "function send(kind) {\n  return handlers[kind];\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_table_read_with_a_fallback_is_found_in_this_language(language):
    found = rules.open_dispatch(read.read_tree(OPEN_TABLE[language], language))
    assert [f["symbol"] for f in found] == [
        "handlers" if language == "javascript" else "HANDLERS"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_same_table_read_by_subscript_is_quiet(language):
    """A subscript lets an unknown key raise, which records the gap in the table instead of
    hiding it. That is the whole of what the clause asks for."""
    assert rules.open_dispatch(read.read_tree(CLOSED_TABLE[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_fallback_built_from_the_key_records_the_gap_rather_than_hiding_it(language):
    """`COPY.get(key, key)` brings the unknown key back visible as itself, which is the
    opposite of filing it under an answer written for a different input."""
    source = {"python": ("COPY = {'a': 'A'}\n\n\ndef label(key):\n"
                         "    return COPY.get(key, key)\n"),
              "javascript": ("const copy = {a: 'A'};\n\n"
                             "function label(key) {\n  return copy[key] ?? key;\n}\n")}
    assert rules.open_dispatch(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_fallback_on_something_this_file_never_declared_is_not_a_dispatch_table(language):
    """Reaching into an argument is not reading a table whose rules this file wrote.
    Flagging it would flag most of the JavaScript ever written."""
    source = {"python": "def send(options):\n    return options.get('timeout', 30)\n",
              "javascript": ("function send(options) {\n"
                             "  return options['timeout'] ?? 30;\n}\n")}
    assert rules.open_dispatch(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_fallback_naming_the_key_in_a_message_records_the_gap(language):
    """The key need not be the whole fallback. A message built around it still brings the
    unknown key back visible, which is the opposite of hiding it."""
    source = {"python": ("REASONS = {2: 'interrupted'}\n\n\n"
                         "def why(code):\n    return REASONS.get(code, f'unknown exit {code}')\n"),
              "javascript": ("const reasons = {2: 'interrupted'};\n\n"
                             "function why(code) {\n"
                             "  return reasons[code] ?? `unknown exit ${code}`;\n}\n")}
    assert rules.open_dispatch(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_fallback_that_is_a_shared_constant_is_still_open(language):
    """The shape the rule is about: a key the table does not know renders identically to a
    key that was never measured, and nothing downstream can tell them apart."""
    source = {"python": ("WORDS = {'Healthy': 'good'}\n\n\n"
                         "def word(band):\n    return WORDS.get(band, 'No data')\n"),
              "javascript": ("const words = {Healthy: 'good'};\n\n"
                             "function word(band) {\n  return words[band] ?? 'No data';\n}\n")}
    assert rules.open_dispatch(read.read_tree(source[language], language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_fallback_naming_a_different_row_is_still_open(language):
    """The worst case of all, because the answer looks deliberate. An unknown kind is
    handled by the rule somebody wrote for kind `a`."""
    source = {"python": ("HANDLERS = {'a': one, 'b': two}\n\n\n"
                         "def run(kind):\n    return HANDLERS.get(kind, one)\n"),
              "javascript": ("const handlers = {a: one, b: two};\n\n"
                             "function run(kind) {\n  return handlers[kind] ?? one;\n}\n")}
    assert rules.open_dispatch(read.read_tree(source[language], language))


def test_a_language_with_neither_spelling_says_it_could_not_decide():
    """Go returns presence beside the value and C has no table type at all, so there is
    nothing to read either way and the empty list would claim the file was checked."""
    for absent in ("go", "c"):
        assert rules.open_dispatch(read.read_tree("", absent)) is None, absent


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_name_bound_inside_a_function_is_not_bound_at_module_level(language):
    """The reader walked each top-level statement to its leaves, and a function definition
    IS a top-level statement, so every local variable in the file read as module scope. It
    reported three of this package's own locals as configuration somebody turns."""
    source = {"python": ("def read(path):\n    raw = path.read_bytes()\n    return raw\n\n\n"
                         "def size(path):\n    raw = read(path)\n    return len(raw)\n"),
              "javascript": ("function read(path) {\n  const raw = load(path);\n  return raw;\n}\n\n"
                             "function size(path) {\n  const raw = read(path);\n"
                             "  return raw.length;\n}\n")}
    tree = read.read_tree(source[language], language)
    bound = read.module_level_bindings(tree["root"], tree["spec"], tree["raw"])
    assert "raw" not in bound, bound
    assert rules.hidden_configuration(tree) == []


# --------------------------------------------------------------------------
# Clause 8, the swallowed exception
#
# The purest form of a silent failure: it reports success for work that failed. Five of the
# nine languages here have try and catch; Go returns an error beside the value and Rust
# returns a Result, and neither is a handler this clause can read. That is a fact about
# those languages rather than a gap in this reader, and the clause says so.
#
# The handler's body is the one shape the grammars disagree about. Python calls it a block,
# JavaScript a statement block, Ruby a `then`, and Python does not field it at all.
# --------------------------------------------------------------------------

SWALLOWS = {
    "python": ("def send(data):\n"
               "    try:\n        return go(data)\n"
               "    except ValueError:\n        return None\n"),
    "javascript": ("function send(data) {\n"
                   "  try {\n    return go(data);\n"
                   "  } catch (e) {\n    return null;\n  }\n}\n"),
}

RERAISES = {
    "python": ("def send(data):\n"
               "    try:\n        return go(data)\n"
               "    except ValueError:\n        raise\n"),
    "javascript": ("function send(data) {\n"
                   "  try {\n    return go(data);\n"
                   "  } catch (e) {\n    throw e;\n  }\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_handler_returning_a_stand_in_is_found_in_this_language(language):
    found = edges.swallowed_exceptions(read.read_tree(SWALLOWS[language], language))
    assert len(found) == 1, found
    assert "reports success for work that failed" in found[0]["detail"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_handler_that_re_raises_is_doing_what_the_rule_asks(language):
    assert edges.swallowed_exceptions(read.read_tree(RERAISES[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_empty_handler_is_the_same_swallow(language):
    """The commonest spelling of all, and the one with nothing in the body to read."""
    source = {"python": ("def send(data):\n    try:\n        go(data)\n"
                         "    except ValueError:\n        pass\n"),
              "javascript": ("function send(data) {\n  try {\n    go(data);\n"
                             "  } catch (e) {\n  }\n}\n")}
    assert len(edges.swallowed_exceptions(read.read_tree(source[language], language))) == 1


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_handler_that_maps_the_error_to_a_response_is_not_swallowing(language):
    """A boundary catching and mapping is doing what the rule asks. It hands the caller
    something that names the failure rather than something that looks like success."""
    source = {"python": ("def route(request):\n    try:\n        return go(request)\n"
                         "    except ValueError as error:\n        return respond(400, str(error))\n"),
              "javascript": ("function route(request) {\n  try {\n    return go(request);\n"
                             "  } catch (error) {\n    return respond(400, error.message);\n  }\n}\n")}
    assert edges.swallowed_exceptions(read.read_tree(source[language], language)) == []


def test_a_language_with_no_handler_says_the_question_cannot_arise():
    """Go returns an error beside the value and Rust returns a Result. Neither is a handler
    this clause reads, and reporting the empty list would claim the file was checked."""
    for absent in ("go", "rust"):
        assert edges.swallowed_exceptions(read.read_tree("", absent)) is None, absent


# --------------------------------------------------------------------------
# Clause 19, check-then-act on something two callers share
#
# A read of a shared value followed by a write to it, inside one function. Between the two,
# another caller reads the same answer, and both proceed believing they hold the thing.
#
# An await in between makes the race certain rather than occasional, because the runtime is
# guaranteed to give another caller the chance. Both languages spell it `await` and both
# needed the node type named, since the vocabulary carried no key for it.
# --------------------------------------------------------------------------

RACE = {
    "python": ("SEATS = {}\n\n\n"
               "def claim(seat, who):\n"
               "    if seat in SEATS:\n        return False\n"
               "    SEATS[seat] = who\n    return True\n"),
    "javascript": ("const seats = {};\n\n"
                   "function claim(seat, who) {\n"
                   "  if (seats[seat]) { return false; }\n"
                   "  seats[seat] = who;\n  return true;\n}\n"),
}

AWAITED = {
    "python": ("SEATS = {}\n\n\n"
               "async def claim(seat, who):\n"
               "    if seat in SEATS:\n        return False\n"
               "    await settle(seat)\n"
               "    SEATS[seat] = who\n    return True\n"),
    "javascript": ("const seats = {};\n\n"
                   "async function claim(seat, who) {\n"
                   "  if (seats[seat]) { return false; }\n"
                   "  await settle(seat);\n"
                   "  seats[seat] = who;\n  return true;\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_read_then_a_write_of_a_shared_container_is_found(language):
    found = rules.check_then_act(read.read_tree(RACE[language], language))
    assert [f["symbol"].split("(")[0] for f in found] == ["claim"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_writing_without_reading_first_is_not_a_race(language):
    """The other direction. A function that only writes cannot have decided anything from
    what it read, so there is nothing for a second caller to have decided too."""
    source = {"python": "SEATS = {}\n\n\ndef claim(seat, who):\n    SEATS[seat] = who\n",
              "javascript": ("const seats = {};\n\n"
                             "function claim(seat, who) {\n  seats[seat] = who;\n}\n")}
    assert rules.check_then_act(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_await_between_them_makes_the_race_certain(language):
    found = rules.check_then_act(read.read_tree(AWAITED[language], language))
    assert found and "certain" in found[0]["detail"], found
    assert "occasional" not in found[0]["detail"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_without_an_await_the_race_is_reported_as_occasional(language):
    """The distinction is the finding. A reader deciding what to fix first needs to know
    which of the two they are looking at."""
    found = rules.check_then_act(read.read_tree(RACE[language], language))
    assert found and "occasional" in found[0]["detail"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_local_container_is_not_shared_with_anyone(language):
    """Only what the file declares at the top. A container built inside the function is
    that call's own, and no second caller can see it."""
    source = {"python": ("def claim(seat, who):\n    seats = {}\n"
                         "    if seat in seats:\n        return False\n"
                         "    seats[seat] = who\n    return True\n"),
              "javascript": ("function claim(seat, who) {\n  const seats = {};\n"
                             "  if (seats[seat]) { return false; }\n"
                             "  seats[seat] = who;\n  return true;\n}\n")}
    assert rules.check_then_act(read.read_tree(source[language], language)) == []


# --------------------------------------------------------------------------
# Clause 20, logging is a declared boundary and an error is returned
#
# A principle with no clause until now. A log line written from inside a function is a
# return value that skipped the type system: the function produces an observable output its
# signature never admits, so no caller can see it, no test can assert on it without
# capturing output, and no caller can decline it.
#
# Two rules follow and this reads both. An error is RETURNED, never written: a function that
# logs a failure and carries on has reported it somewhere the caller cannot reach, which is
# how a failure gets lost. And information goes through one logging function of your own,
# declared as a boundary, because `logger.info(...)` reaches a global you did not declare
# and cannot substitute, so twenty-four call sites become twenty-four independent edges.
# --------------------------------------------------------------------------

LOGS_A_FAILURE = {
    "python": ("def save(row):\n"
               "    if not row:\n        logger.error('empty row')\n        return None\n"
               "    return store(row)\n"),
    "javascript": ("function save(row) {\n"
                   "  if (!row) {\n    console.error('empty row');\n    return null;\n  }\n"
                   "  return store(row);\n}\n"),
}

RAISES_INSTEAD = {
    "python": ("def save(row):\n"
               "    if not row:\n        raise ValueError('empty row')\n"
               "    return store(row)\n"),
    "javascript": ("function save(row) {\n"
                   "  if (!row) { throw new Error('empty row'); }\n"
                   "  return store(row);\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_logging_a_failure_and_carrying_on_is_found(language):
    found = edges.undeclared_logging(read.read_tree(LOGS_A_FAILURE[language], language))
    assert [f["symbol"] for f in found] == ["save"], found
    assert "carries on" in found[0]["detail"], found[0]["detail"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_raising_instead_of_logging_is_what_the_rule_asks_for(language):
    assert edges.undeclared_logging(read.read_tree(RAISES_INSTEAD[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_function_that_only_reports_information_is_still_an_edge(language):
    """The second half. It loses nothing, and it is one of however many independent edges
    the file opens onto a global nobody declared."""
    source = {"python": "def save(row):\n    logger.info('saving')\n    return store(row)\n",
              "javascript": ("function save(row) {\n  console.log('saving');\n"
                             "  return store(row);\n}\n")}
    found = edges.undeclared_logging(read.read_tree(source[language], language))
    assert [f["symbol"] for f in found] == ["save"], found
    assert "carries on" not in found[0]["detail"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_finding_says_how_many_edges_the_file_opens(language):
    """A reader deciding whether to build one logging function needs the count, not one
    site at a time."""
    source = {"python": ("def a(x):\n    logger.info('a')\n    return x\n\n\n"
                         "def b(x):\n    logger.info('b')\n    return x\n"),
              "javascript": ("function a(x) {\n  console.log('a');\n  return x;\n}\n\n"
                             "function b(x) {\n  console.log('b');\n  return x;\n}\n")}
    found = edges.undeclared_logging(read.read_tree(source[language], language))
    assert len(found) == 2
    assert "2" in found[0]["detail"], found[0]["detail"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_function_that_logs_nothing_is_quiet(language):
    source = {"python": "def save(row):\n    return store(row)\n",
              "javascript": "function save(row) {\n  return store(row);\n}\n"}
    assert edges.undeclared_logging(read.read_tree(source[language], language)) == []


# --------------------------------------------------------------------------
# Clause 4, I/O at the boundary
#
# The clause adopters meet most, and the last one still written against Python's own parser.
#
# A declaration needs a spelling every language has. Python's is a decorator, which most
# languages do not have; the Honest Framework's own architecture format spells the same fact
# as a `boundary_in` or `boundary_out` prefix on the function's NAME, and a name is
# something every language has. Both are read, so a project declares its edges in whichever
# its language gives it.
# --------------------------------------------------------------------------

IO_BELOW = {
    "python": ("def price(sku):\n    return open(sku).read()\n\n\n"
               "def total(skus):\n    return sum(price(s) for s in skus)\n"),
    "javascript": ("function price(sku) {\n  return fs.readFileSync(sku);\n}\n\n"
                   "function total(skus) {\n  return skus.map(price);\n}\n"),
}

DECLARED_BY_NAME = {
    "python": ("def boundary_in_price(sku):\n    return open(sku).read()\n\n\n"
               "def total(skus):\n    return sum(boundary_in_price(s) for s in skus)\n"),
    "javascript": ("function boundary_in_price(sku) {\n  return fs.readFileSync(sku);\n}\n\n"
                   "function total(skus) {\n  return skus.map(boundary_in_price);\n}\n"),
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_io_in_a_function_a_sibling_calls_is_found_in_this_language(language):
    found = edges.io_below_the_boundary(read.read_tree(IO_BELOW[language], language))
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == ["price"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_function_nothing_calls_is_the_edge_and_is_left_alone(language):
    """A function nothing in the file calls IS where the I/O belongs. Not decided: whether
    an uncalled function is truly an entry point, because a module read only from outside
    has every function looking like one."""
    source = {"python": "def price(sku):\n    return open(sku).read()\n",
              "javascript": "function price(sku) {\n  return fs.readFileSync(sku);\n}\n"}
    assert edges.io_below_the_boundary(read.read_tree(source[language], language)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_name_prefix_declares_the_edge_in_any_language(language):
    """The spelling every language has. A decorator is Python's, and most languages have
    none, so the framework's own architecture format puts it in the name instead."""
    found = edges.io_below_the_boundary(read.read_tree(DECLARED_BY_NAME[language], language))
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == [], found
    assert [f["symbol"] for f in found if f["withheld_by"] == "declaration"] == ["boundary_in_price"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_function_a_table_holds_is_called_here_too(language):
    """The blind spot an adopter found in the Python reading: a function reached only
    through a dispatch table was reached by nothing as far as the call graph could see."""
    source = {"python": ("def price(sku):\n    return open(sku).read()\n\n\n"
                         "HANDLERS = {'price': price}\n"),
              "javascript": ("function price(sku) {\n  return fs.readFileSync(sku);\n}\n\n"
                             "const handlers = {price: price};\n")}
    found = edges.io_below_the_boundary(read.read_tree(source[language], language))
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == ["price"], found


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_function_that_touches_nothing_outside_is_quiet(language):
    source = {"python": "def price(n):\n    return n * 2\n\n\ndef total(n):\n    return price(n)\n",
              "javascript": ("function price(n) {\n  return n * 2;\n}\n\n"
                             "function total(n) {\n  return price(n);\n}\n")}
    assert edges.io_below_the_boundary(read.read_tree(source[language], language)) == []


# --------------------------------------------------------------------------
# The same construct, spelled another way
#
# A neighbouring project found a check that banned if-statements and reported zero while
# seventy-six stood in the code: it knew one spelling and never learned the other.
#
# Layout is not the risk here, because tree-sitter gives an indented `if` and a one-line
# `if` the same node type. A different CONSTRUCT saying the same thing is, and three were
# found by asking: a chain of ternaries, a match statement, and a suppression that silences
# an exception with no handler body to read.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("language", LANGUAGES)
def test_a_chain_of_ternaries_is_a_dispatch_chain(language):
    """Three arms testing one name against literals, written as expressions."""
    source = {"python": ("def send(kind):\n    return one() if kind == 'a' else two() "
                         "if kind == 'b' else three() if kind == 'c' else four()\n"),
              "javascript": ("function send(kind) {\n  return kind === 'a' ? one() : "
                             "kind === 'b' ? two() : kind === 'c' ? three() : four();\n}\n")}
    assert rules.dispatch_chains(read.read_tree(source[language], language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_match_on_literals_is_a_dispatch_chain(language):
    """The modern spelling, and the one a reader is most likely to write today. A match on
    literal cases IS a table written as syntax."""
    source = {"python": ("def send(kind):\n    match kind:\n"
                         "        case 'a':\n            return one()\n"
                         "        case 'b':\n            return two()\n"
                         "        case 'c':\n            return three()\n"),
              "javascript": ("function send(kind) {\n  switch (kind) {\n"
                             "    case 'a': return one();\n    case 'b': return two();\n"
                             "    case 'c': return three();\n  }\n}\n")}
    assert rules.dispatch_chains(read.read_tree(source[language], language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_match_on_shapes_rather_than_literals_is_not_a_table(language):
    """The other direction, and the reason this is not simply "match is a violation". A
    match that destructures is doing what no dict lookup can, and reporting it would ask an
    author to throw away the one thing the construct is for."""
    source = {"python": ("def send(event):\n    match event:\n"
                         "        case {'kind': k, 'body': b}:\n            return one(k, b)\n"
                         "        case [first, *rest]:\n            return two(first, rest)\n"
                         "        case _:\n            return three()\n"),
              "javascript": ("function send(event) {\n  switch (true) {\n"
                             "    case event.kind !== undefined: return one(event);\n"
                             "    default: return three();\n  }\n}\n")}
    assert rules.dispatch_chains(read.read_tree(source[language], language)) == []


def test_suppressing_an_exception_is_a_swallow_with_no_body_to_read():
    """The purest swallow: there is no handler at all, so a reader looking for one finds
    nothing and the clause was quiet. `contextlib.suppress(Exception)` discards every error
    the block raises and returns as though it succeeded."""
    source = ("import contextlib\n\n\ndef save(row):\n"
              "    with contextlib.suppress(ValueError):\n        return store(row)\n")
    found = edges.swallowed_exceptions(read.read_tree(source, "python"))
    assert found, found
    assert "ValueError" in found[0]["symbol"], found[0]["symbol"]


def test_suppressing_a_control_flow_signal_is_still_not_the_failure_this_names():
    source = ("import contextlib\n\n\ndef save(row):\n"
              "    with contextlib.suppress(KeyboardInterrupt):\n        return store(row)\n")
    assert edges.swallowed_exceptions(read.read_tree(source, "python")) == []
