"""The nineteen clause checkers of L1.21, one per Honest Code principle.

The numbering is the Honest Framework's, so a clause number means one thing across every
Open Honest artifact.

Every checker is a pure function of a source and returns the sites it found. That matters
more here than anywhere else in this tool: a conformity score is only worth having if each
finding can be read at the site, and a checker that had to run something could not sit
behind a hook that fires on every write.

`None` is the third answer. It means the clause was not decided for this file, and it is
different from an empty list, which means the clause ran and found nothing. Conflating them
would let a question nobody asked count as a question answered.

Each checker also states what it does NOT decide. That is the difference between a
conformity number worth having and one that can be raised by looking away.

How a source is read, and the vocabulary a ported clause reads it through, live in
`honest_code_read`.
"""


from tree_sitter import Node

from l1_analyzer.honest_code_read import (
    Finding,
    _finding,
    base_names,
    chain_subjects,
    class_nodes,
    first_name,
    function_nodes,
    handler_body,
    is_absent_value,
    is_chain_arm,
    is_constructor,
    method_nodes,
    module_level_bindings,
    names_written_in,
    node_text,
    reaches_receiver,
    sends_failure_onward,
    walk,
    writes_receiver,
)
from l1_analyzer.lang_spec import LangSpec

BOUNDARY_DECORATORS = frozenset({"boundary", "boundary_in", "boundary_out", "edge",
                                 "entrypoint", "entry_point"})

# Bases that DECLARE a shape rather than share an implementation. The rules allow exactly
# these, and flagging them would flag the recommended alternative.
DECLARED_SHAPES = frozenset({
    "TypedDict", "Protocol", "Exception", "Enum", "IntEnum", "StrEnum", "NamedTuple",
    "ABC", "ABCMeta", "BaseException", "Generic", "object",
    # JavaScript spells the same declarations differently. `Error` is its exception root and
    # `Object` its base of everything, so a class extending either declares a shape rather
    # than sharing an implementation.
    "Error", "TypeError", "RangeError", "Object", "HTMLElement",
})

# The nodes a grammar hangs a class's bases from. Python parenthesises them as an argument
# list; JavaScript names a heritage clause. Read from structure, so neither language is
# named in the rule.

# What makes a class a wrapper around a stateful external resource, which the rule permits.
RESOURCE_CALLS = frozenset({
    "connect", "Connection", "Session", "create_engine", "socket", "open", "Client",
    "Pool", "ClientSession", "connect_async", "acquire",
})


# The languages that have a DOM to keep a second copy of state in. Declared once and read
# both by the clause table and by the two checkers, so "not applicable" is decided in one
# place rather than agreed in two.
BROWSER_LANGUAGES = frozenset({"javascript", "typescript", "html"})

_STORE_LIBRARIES = ("redux", "zustand", "mobx", "vuex", "pinia", "recoil", "jotai")
_DOM_CALLS = ("addEventListener", "querySelector", "querySelectorAll", "getElementById",
              "innerHTML", "createElement", "appendChild")


# Calls that record a failure. The vocabulary is small on purpose: a try whose LAST
# statement records a failure is asserting that the call above it raised, so the catch
# below is the success condition rather than a swallow.
_RECORDS_A_FAILURE = frozenset({"append", "add", "extend", "fail", "error", "insert"})

# BaseException signals that carry control flow rather than failure. `except SystemExit:
# pass` around a `--help` invocation is argparse's normal exit for help, so it is the
# expected terminal state of the thing under test.
#


# --------------------------------------------------------------------------
# 1. Dict-lookup polymorphism over if/elif chains
# --------------------------------------------------------------------------

def dispatch_chains(source: dict) -> list[Finding] | None:
    """An if/elif chain testing ONE name against literals to select behaviour.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers rather than being reimplemented per language.

    Two or more elif arms, because one `if` and one `else` is a binary choice and a table
    starts where the third case would otherwise be another arm.

    Reported beside the functions that are one function. One principle, two ways of
    breaking it: a chain that should be a table, and a table filled with code where its
    rows should have carried the words.

    Not decided: whether the axis of variation is worth naming. The rule says to build a
    table when you can name the axis and it has a finite set of kinds, and nothing here
    reads that."""
    spec, raw = source["spec"], source["raw"]
    found: list[Finding] = []
    for node in walk(source["root"]):
        if node.type not in spec["branch_types"] or is_chain_arm(node):
            continue
        names = chain_subjects(node, spec, raw)
        if len(names) >= 3 and len(set(names)) == 1:
            found.append(_finding(
                "L1.21.1", names[0], node.start_point[0] + 1,
                f"{len(names)} arms dispatch on `{names[0]}` to select behaviour",
                "a dict mapping each value to the function that handles it, read by "
                "subscript so an unknown key raises", ""))
    return found + functions_of_one_shape(source)


# A body big enough to have a shape at all. Deliberately low, because this clause is an
# opinion and L1.21 is opt-in: anyone running it has already accepted that two functions
# differing by a word are a table with two rows, however short they are.
#
# The floor buys almost nothing anyway, which is why it can be this low. Measured against
# this package: a floor of 6 reports 13 groups, 12 reports 13, and 16 reports 12. Real code
# does not sit near the boundary, so the strict end costs one extra finding and reads the
# one-line pair the principle is actually about.
_SHAPE_TOKENS = 8


def functions_of_one_shape(source: dict) -> list[Finding]:
    """Functions that are one function with different words in them.

    Every name and every quoted string is erased and only the shape is kept, so two
    functions that differ by a table name and a keyword read identically. This is clause 1
    read from the other side: the chain became a table, and then the table was filled with
    sixteen functions where its rows should have carried the text.

    This clause is an OPINION, and it says so rather than hedging. L1.21 is opt-in and
    nobody reaches it by accident, so the finding states the Honest position: two functions
    differing by a word are two rows of a table somebody wrote as code. A reader who
    disagrees on a given group declares it, which is what the allow marker is for."""
    from l1_analyzer.clone_detect import normalized_tokens

    spec, raw = source["spec"], source["raw"]
    shapes: dict[str, list[Node]] = {}
    for fn in function_nodes(source["root"], spec):
        symbols = [symbol for symbol, _ in normalized_tokens(fn, source["language"])]
        if len(symbols) < _SHAPE_TOKENS:
            continue
        shapes.setdefault(" ".join(symbols), []).append(fn)

    found: list[Finding] = []
    for group in shapes.values():
        if len(group) < 2:
            continue
        # In file order, both the line and the names. `walk` promises no order, so the
        # group was reported at whichever member came back first, and for one fixture that
        # was the second function in the file. The line a reader is given is where they put
        # the allow marker, so an anchor that can move between runs is a marker that stops
        # working for a reason nobody can see.
        group = sorted(group, key=lambda fn: fn.start_point)
        names = [node_text(fn.child_by_field_name("name"), raw) or first_name(fn, raw)
                 for fn in group]
        found.append(_finding(
            "L1.21.1", ", ".join(names), group[0].start_point[0] + 1,
            f"{len(names)} functions leave one shape behind once every name and quoted "
            f"string is erased, so what separates them is words: {', '.join(names)}",
            "one function over a table, where each row carries the words that function "
            "would have pasted in", ""))
    return found




def data_classes(source: dict) -> list[Finding] | None:
    """A class whose constructor assigns its parameters, with no method doing more.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers. The constructor is the whole shape: without one there
    is no evidence the class holds data at all.

    Not decided: whether a class the rule permits was the right choice. A wrapper around a
    resource is allowed and whether it earned the permission is a question for a reader.

    Not decided either: a language whose constructor this vocabulary does not name. Rust,
    C and Go have no constructor shape to read, so the clause says it could not decide
    rather than returning the empty list, which would read as "no data classes here"."""
    spec, raw = source["spec"], source["raw"]
    if not spec["constructor_names"] and not spec["constructor_types"]:
        return None
    shapes = DECLARED_SHAPES | local_exception_roots(source)
    found: list[Finding] = []
    for node in class_nodes(source["root"], spec):
        if set(base_names(node, spec, raw)) & shapes:
            continue
        methods = method_nodes(node, spec)
        init = next((m for m in methods if is_constructor(m, spec, raw)), None)
        if init is None:
            continue
        if _calls_a_resource(init, spec, raw):
            continue
        others = [m for m in methods if m is not init]
        if all(not writes_receiver(m, spec, raw) for m in others):
            name = node_text(node.child_by_field_name("name"), raw) or first_name(node, raw)
            found.append(_finding(
                "L1.21.2", name, node.start_point[0] + 1,
                "the class holds data and does nothing a dict could not",
                f"a TypedDict: `{name} = TypedDict(\"{name}\", {{...}})`", ""))
    return found


def _calls_a_resource(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether a constructor opens something. A class wrapping a resource is allowed."""
    for n in walk(node):
        if n.type not in spec["call_types"]:
            continue
        fn = n.child_by_field_name(spec["call_fn"])
        if fn is not None and node_text(fn, raw).split(".")[-1] in RESOURCE_CALLS:
            return True
    return False


# --------------------------------------------------------------------------
# 3. Pure functions over methods
# --------------------------------------------------------------------------

def methods_wearing_a_class(source: dict) -> list[Finding] | None:
    """A method that reaches the receiver only to fetch data it could have received.

    Read through the language's own node vocabulary. `self` and `this` are the same shape
    with two spellings, and the vocabulary already carried both.

    Not decided: whether the class is required by a framework. Django models and React
    components are the usual cases and neither is readable from the method alone."""
    spec, raw = source["spec"], source["raw"]
    if not spec["this_idents"]:
        return None
    found: list[Finding] = []
    for node in class_nodes(source["root"], spec):
        if set(base_names(node, spec, raw)) & DECLARED_SHAPES:
            continue
        owner = node_text(node.child_by_field_name("name"), raw) or first_name(node, raw)
        for method in method_nodes(node, spec):
            name = node_text(method.child_by_field_name("name"), raw)
            if not name or name.startswith("__") or is_constructor(method, spec, raw):
                continue
            if not reaches_receiver(method, spec, raw):
                continue
            if writes_receiver(method, spec, raw):
                continue
            found.append(_finding(
                "L1.21.3", f"{owner}.{name}", method.start_point[0] + 1,
                "the method reaches the receiver only for data it could have been passed",
                f"a free function: `{name}_{owner.lower()}(data)`", ""))
    return found


# --------------------------------------------------------------------------
# 4. I/O at the boundary
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 5. Flat composition over inheritance
# --------------------------------------------------------------------------


def local_exception_roots(source: dict) -> set[str]:
    """Classes this file defines that reach an exception root through their own bases.

    Followed to the root rather than one level, so a three-deep hierarchy is still
    exceptions all the way down. Sixteen second-level exceptions in one adopter's file
    fired as violations before this existed."""
    spec, raw = source["spec"], source["raw"]
    bases = {node_text(node.child_by_field_name("name"), raw) or first_name(node, raw):
             base_names(node, spec, raw)
             for node in walk(source["root"]) if node.type in spec["class_types"]}
    known = {name for name, parents in bases.items() if set(parents) & DECLARED_SHAPES}
    while True:
        grew = {name for name, parents in bases.items() if set(parents) & known} - known
        if not grew:
            return known
        known |= grew


def inheritance_for_reuse(source: dict) -> list[Finding] | None:
    """A class whose base is neither a declared shape nor a framework requirement.

    An exception hierarchy is followed to its root. The table knew the literal name
    `Exception` and nothing about a class deriving from one, so `class
    ParseError(HonestCheckError)` read as inheriting to share an implementation. That is
    the normal way to write exceptions and the framework's rule permits it; sixteen of them
    in one adopter's file fired as violations.

    Not decided: whether a framework demands the base, and whether a base defined in
    another module is an exception. A Django model must inherit, and one file cannot see
    past its own imports. Both stay reported, which sends a reader to look rather than
    hiding it."""
    spec, raw = source["spec"], source["raw"]
    shapes = DECLARED_SHAPES | local_exception_roots(source)
    found: list[Finding] = []
    for node in walk(source["root"]):
        if node.type not in spec["class_types"]:
            continue
        name = node_text(node.child_by_field_name("name"), raw) or first_name(node, raw)
        inherited = [b for b in base_names(node, spec, raw) if b not in shapes and b != name]
        if inherited:
            found.append(_finding(
                "L1.21.5", name, node.start_point[0] + 1,
                f"inherits from {', '.join(inherited)}, which hides where behaviour comes from",
                "compose the steps at the point of assembly: `pipe(validate, authenticate, "
                "create)`", ""))
    return found


# --------------------------------------------------------------------------
# 6 and 7. The two browser clauses
# --------------------------------------------------------------------------


def client_side_state(source: dict) -> list[Finding] | None:
    """A store library or `localStorage` holding a copy of what the server already knows.

    Two sources of truth means one of them is lying. Not applicable to a file in a language
    with no DOM, and that is a different answer from finding nothing."""
    if source["language"] not in BROWSER_LANGUAGES:
        return None
    text = source["text"]
    found: list[Finding] = []
    for library in _STORE_LIBRARIES:
        if library in text:
            found.append(_finding(
                "L1.21.6", library, _line_of(text, library),
                f"{library} holds a second copy of state the server already has",
                "let the server render the HTML and swap it in, so there is one copy", ""))
    for storage in ("localStorage", "sessionStorage"):
        if storage in text:
            found.append(_finding(
                "L1.21.6", storage, _line_of(text, storage),
                f"{storage} keeps state the server cannot see",
                "send it to the server and render from there", ""))
    return found


def imperative_dom(source: dict) -> list[Finding] | None:
    """`addEventListener`, `querySelector` and `innerHTML`: how, in a place the reader has
    to go and find.

    Not applicable to a file with no DOM to drive."""
    if source["language"] not in BROWSER_LANGUAGES:
        return None
    text = source["text"]
    return [_finding(
        "L1.21.7", call, _line_of(text, call),
        f"{call} describes how, somewhere the reader has to go and find",
        "an attribute that declares intent: hx-post, hx-target, hx-trigger", "")
        for call in _DOM_CALLS if call in text]


def _line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.split("\n"), start=1):
        if needle in line:
            return number
    return 1


# --------------------------------------------------------------------------
# 8. Typed exceptions at the boundary
# --------------------------------------------------------------------------

def swallowed_exceptions(source: dict) -> list[Finding] | None:
    """A handler whose body throws the error away.

    Read through the language's own node vocabulary. Catch-and-swallow is the purest form
    of a silent failure: it reports success for work that failed. A handler that re-raises,
    or that maps the error to a response, is doing what the rule asks.

    Not decided: whether the enclosing function is a boundary. A route handler catching and
    mapping is right, and nothing in the file says which functions are routes.

    Not decided either: a language with no exception. Go returns an error beside the value
    and Rust returns a Result, and neither is a handler this reads. Reporting those files
    clean would claim they were checked."""
    spec, raw = source["spec"], source["raw"]
    if not spec["handler_types"]:
        return None
    found: list[Finding] = []
    for node in walk(source["root"]):
        if node.type not in spec["handler_types"]:
            continue
        body = handler_body(node, spec)
        if body is None or not _throws_it_away(body, node, spec, raw):
            continue
        # The catch is the ASSERTION when the guarded body's last statement records a
        # failure: that statement runs only if the call above it did NOT raise, so reaching
        # it is the defect and the handler is the success condition. Keying on the handler
        # alone made both readings look alike.
        if _guarded_body_asserts_a_raise(node, spec, raw):
            continue
        caught = _caught_text(node, spec, raw)
        # A signal that carries control flow is not the failure this rule is about. Catching
        # one and returning is how a program stops cleanly.
        if caught and set(caught.split()) <= spec["control_flow_exceptions"]:
            continue
        found.append(_finding(
            "L1.21.8", caught or "everything", node.start_point[0] + 1,
            f"catches {caught or 'everything'} and reports success for work that failed",
            "let it raise and map the type to a response at the boundary", ""))
    return found


def _throws_it_away(body: Node, handler: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether a handler body discards the failure instead of disclosing it.

    Empty, or one statement returning a value a caller cannot tell from success. A body
    that mentions the caught error is disclosing it: a route mapping the message into a
    response hands the caller something that names the failure."""
    if sends_failure_onward(body, spec, raw):
        return False
    statements = [c for c in body.named_children if c.type != "pass_statement"]
    if not statements:
        return True
    if len(statements) > 1:
        return False
    only = statements[0]
    if only.type not in spec["return_types"]:
        return False
    returned = [c for c in only.named_children]
    if not returned:
        return True
    caught_name = _caught_variable(handler, spec, raw)
    if caught_name and caught_name in node_text(returned[0], raw):
        return False
    return is_absent_value(returned[0], spec, raw)


def _guarded_body_asserts_a_raise(handler: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether the body this handler guards is asserting that its call raised.

    The shape is a call followed by a statement that records a failure. That statement runs
    only when the call did NOT raise, so the handler beneath is the success condition and
    the defect would be reaching the recorder.

    Not decided: whether the recorded failure is the one the author meant. A body ending in
    an unrelated append reads the same way, and separating them would need the meaning of
    the collection rather than its shape."""
    guarded = handler.parent
    if guarded is None or guarded.type not in spec["try_types"]:
        return False
    body = next((c for c in guarded.named_children
                 if c.type in spec["handler_body_types"]), None)
    if body is None:
        return False
    statements = [c for c in body.named_children if c.type != "pass_statement"]
    if len(statements) < 2:
        return False
    last = statements[-1]
    if last.type in spec["assertion_types"]:
        return True
    for call in walk(last):
        if call.type in spec["call_types"]:
            fn = call.child_by_field_name(spec["call_fn"])
            if fn is not None and node_text(fn, raw).split(".")[-1] in _RECORDS_A_FAILURE:
                return True
    return False


def _caught_text(handler: Node, spec: LangSpec, raw: bytes) -> str:
    """What this handler says it catches, or nothing when it catches everything."""
    parts = [node_text(c, raw) for c in handler.named_children
             if c.type not in spec["handler_body_types"]]
    return " ".join(p for p in parts if p).strip()


def _caught_variable(handler: Node, spec: LangSpec, raw: bytes) -> str:
    """The name the handler binds the error to, or nothing if it binds none.

    The last identifier before the body, which is where all five grammars put it whether
    they field it or not."""
    before = [c for c in handler.named_children if c.type not in spec["handler_body_types"]]
    names = [node_text(n, raw) for part in before for n in walk(part)
             if n.type == "identifier"]
    return names[-1] if names else ""


# --------------------------------------------------------------------------
# 9. SQL over application caches
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 10. Pure-function assertions over mocks
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 11. Type declarations over imperative validation
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 12. Context managers over instance state
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 13. Configuration as parameters
# --------------------------------------------------------------------------

_KNOB_UNDECIDED = ("whether a table nobody writes is a knob disguised as a fact is not "
                   "readable from a file, so only the ones some function turns were checked")


def hidden_configuration(source: dict) -> list[Finding] | None:
    """A module-level value that some function WRITES, read inside another.

    Read through the language's own node vocabulary. The write is what makes it
    configuration. A table nobody writes is a fact about the world, and flagging it would
    make this clause demand the opposite of clauses 1 and 18, which both require exactly
    such a table. Two clauses of one instrument must not ask for opposite things, and the
    first version of this one did.

    Not decided: whether a knob was disguised as a fact. A module-level value nobody writes
    in this file may still be reassigned from another, and no reading of this file sees
    it."""
    spec, raw = source["spec"], source["raw"]
    bound = module_level_bindings(source["root"], spec, raw)
    if not bound:
        return []
    functions = function_nodes(source["root"], spec)
    turned: set[str] = set()
    for fn in functions:
        turned |= names_written_in(fn, spec, raw) & set(bound)
    if not turned:
        return []
    found: list[Finding] = []
    for fn in functions:
        if names_written_in(fn, spec, raw) & turned:
            continue
        owner = node_text(fn.child_by_field_name("name"), raw) or first_name(fn, raw)
        read_here = sorted({node_text(n, raw) for n in walk(fn)
                            if n.type == "identifier" and node_text(n, raw) in turned})
        for name in read_here:
            found.append(_finding(
                "L1.21.13", f"{owner}({name})", fn.start_point[0] + 1,
                f"reads `{name}`, which another function here writes, so its behaviour "
                "depends on something no caller can see",
                f"take `{name.lower()}` as a parameter, so the dependency is in the "
                "signature", _KNOB_UNDECIDED))
    return found


# --------------------------------------------------------------------------
# 14. No implicit defaults
# --------------------------------------------------------------------------

def implicit_defaults(source: dict) -> list[Finding] | None:
    """A LITERAL default, which cannot be told from a caller who chose that value.

    Read through the language's own node vocabulary. A default that binds a collaborator is
    the opposite failure: it makes a dependency visible in the signature, which is what
    rule 13 asks for, and flagging it would push the code back toward the module-level
    lookup the rule exists to remove.

    Not decided: a language with no default parameter. Java, Go, C and Rust have none, so
    the question cannot arise there. That is a fact about the language, not a gap in this
    reader, and the empty list would instead claim the file was checked and found clean."""
    spec, raw = source["spec"], source["raw"]
    if not spec["default_param_types"]:
        return None
    found: list[Finding] = []
    for fn in function_nodes(source["root"], spec):
        owner = node_text(fn.child_by_field_name("name"), raw) or first_name(fn, raw)
        for parameter in walk(fn.child_by_field_name("parameters") or fn):
            if parameter.type not in spec["default_param_types"]:
                continue
            default = _default_of(parameter)
            if default is None or not _is_literal_node(default, spec):
                continue
            name = node_text(parameter.child_by_field_name(spec["default_param_name"]), raw)
            found.append(_finding(
                "L1.21.14", f"{owner}({name})", parameter.start_point[0] + 1,
                f"`{name}={node_text(default, raw)}` absorbs the caller's omission, so "
                "nothing can tell chose from forgot",
                "make absence an explicit case of a bounded type, resolved at the boundary "
                "and exercised by a test", ""))
    return found


def _default_of(parameter: Node) -> Node | None:
    """The value a parameter falls back to, or nothing if it declares none.

    The named child after the `=` token. Five grammars spell the default five ways and two
    of them use one node type for every parameter whether it has a default or not, so the
    token is the only thing all five carry and it is the grammar's own answer."""
    children = list(parameter.children)
    equals = next((i for i, c in enumerate(children) if c.type == "="), None)
    if equals is None:
        return None
    return next((c for c in children[equals + 1:] if c.is_named), None)


def _is_literal_node(node: Node, spec: LangSpec) -> bool:
    """Whether a default is a value rather than a bound collaborator."""
    while node.type in spec["value_wrapper_types"]:
        inner = next((c for c in node.named_children), None)
        if inner is None:
            break
        node = inner
    return node.type in spec["literal_types"] or node.type in spec["container_literal_types"]


# --------------------------------------------------------------------------
# 15. Simple gherkin steps
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 16. Declarative equivalents over lifecycle hooks
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 17. Strangler pattern — the clause nothing decides
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 18. Dispatch tables close open input
# --------------------------------------------------------------------------

def open_dispatch(source: dict) -> list[Finding] | None:
    """A read of a table this file declares that supplies a value for an absent key.

    Two spellings, read through the language's own vocabulary. Python and Java pass the
    fallback as an argument to a method; JavaScript and C# put it to the right of an
    ordinary lookup as an operator. The rule is the same in both: the fallback files an
    input nobody wrote a rule for under an answer written for a different input, and
    re-opens the space while the code still reads closed. A subscript lets an unknown key
    raise, which records the gap in the table instead of hiding it.

    Only a table this file declares. Reaching into an argument is not reading a table whose
    rules this file wrote, and calling that an open dispatch would flag most of the
    JavaScript ever written.

    Not decided: a language with neither spelling. Go returns presence beside the value and
    C has no table type at all, so there is nothing here to read either way."""
    spec, raw = source["spec"], source["raw"]
    if not spec["fallback_methods"] and not spec["fallback_operators"]:
        return None
    tables = {name for name, value in module_level_bindings(
        source["root"], spec, raw).items() if _is_table(value, spec)}
    if not tables:
        return []
    found: list[Finding] = []
    for node in walk(source["root"]):
        looked_up = _fallback_lookup(node, spec, raw)
        if looked_up is None:
            continue
        table, key, fallback = looked_up
        if table not in tables:
            continue
        # A fallback DERIVED FROM THE KEY records the gap rather than hiding it. The rule's
        # objection is that a fallback files an unknown input under an answer written for a
        # different input; `COPY.get(key, key)` does the opposite, and the unknown key comes
        # back visible as itself.
        if node_text(key, raw) and node_text(key, raw) in node_text(fallback, raw):
            continue
        found.append(_finding(
            "L1.21.18", table, node.start_point[0] + 1,
            f"`{table}` is read with a fallback, which answers for an input nobody wrote "
            "a rule for",
            f"read it by subscript, `{table}[key]`, and record the unknown key as a gap "
            "in the table", ""))
    return found


def _is_table(node: Node, spec: LangSpec) -> bool:
    """Whether a module-level binding holds a map literal, which is what a dispatch table
    is in every language here."""
    return node.type in spec["container_literal_types"]


def _fallback_lookup(node: Node, spec: LangSpec, raw: bytes) -> tuple[str, Node, Node] | None:
    """The table, key and fallback of one lookup that answers for an absent key.

    Nothing if this node is not such a lookup. Both spellings are read here so the clause
    itself names neither."""
    if node.type in spec["call_types"]:
        fn = node.child_by_field_name(spec["call_fn"])
        args = node.child_by_field_name(spec["call_args"])
        if fn is None or args is None or fn.type not in spec["member_types"]:
            return None
        if node_text(fn, raw).split(".")[-1] not in spec["fallback_methods"]:
            return None
        given = [c for c in args.named_children]
        obj = fn.child_by_field_name("object") or fn.child_by_field_name("value")
        if obj is None or obj.type != "identifier" or len(given) < 2:
            return None
        return node_text(obj, raw), given[0], given[1]

    if node.type in spec["comparison_types"] or node.type == "binary_expression":
        operator = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if operator is None or left is None or right is None:
            return None
        if node_text(operator, raw) not in spec["fallback_operators"]:
            return None
        if left.type not in spec["subscript_types"]:
            return None
        table = left.child_by_field_name("object") or left.child_by_field_name("value")
        key = left.child_by_field_name("index") or left.child_by_field_name("subscript")
        if table is None or table.type != "identifier" or key is None:
            return None
        return node_text(table, raw), key, right
    return None


# --------------------------------------------------------------------------
# 19. Atomic test-and-set over check-then-act
# --------------------------------------------------------------------------
