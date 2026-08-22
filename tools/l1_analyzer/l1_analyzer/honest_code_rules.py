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

import ast

from tree_sitter import Node

from l1_analyzer.honest_code_read import (
    Finding,
    _base_names,
    _called,
    _classes,
    _finding,
    _functions,
    _methods,
    node_text,
    walk,
)
from l1_analyzer.lang_spec import COMPARISON_OPS, LangSpec

BOUNDARY_DECORATORS = frozenset({"boundary", "boundary_in", "boundary_out", "edge",
                                 "entrypoint", "entry_point"})

# Bases that DECLARE a shape rather than share an implementation. The rules allow exactly
# these, and flagging them would flag the recommended alternative.
DECLARED_SHAPES = frozenset({
    "TypedDict", "Protocol", "Exception", "Enum", "IntEnum", "StrEnum", "NamedTuple",
    "ABC", "ABCMeta", "BaseException", "Generic", "object",
})

# What makes a class a wrapper around a stateful external resource, which the rule permits.
RESOURCE_CALLS = frozenset({
    "connect", "Connection", "Session", "create_engine", "socket", "open", "Client",
    "Pool", "ClientSession", "connect_async", "acquire",
})

# Calls whose bare name is unambiguous: nothing but I/O is spelled this way.
_IO_CALLS = frozenset({
    "read_text", "read_bytes", "write_text", "write_bytes", "open", "iterdir", "glob",
    "Popen", "check_output", "urlopen", "execute", "fetchall", "fetchone", "commit",
    "listdir", "makedirs", "remove",
})

# Calls whose bare name is shared with something ordinary. `TABLE.get(key)` is a dict
# lookup and `requests.get(url)` fetches a page, and reading the bare name reported this
# tool's own suffix table as I/O. These are matched on the whole dotted call.
_IO_RECEIVERS = frozenset({
    "requests", "httpx", "session", "client", "urllib", "aiohttp", "subprocess",
    "conn", "connection", "cursor", "db",
})
_AMBIGUOUS_IO = frozenset({"get", "post", "put", "delete", "patch", "request", "run", "head"})

_CACHE_NAMES = frozenset({"redis", "memcache", "memcached", "pylibmc", "diskcache", "aiocache"})
_CACHE_DECORATORS = frozenset({"lru_cache", "cache", "cached", "memoize", "cached_property"})

# The languages that have a DOM to keep a second copy of state in. Declared once and read
# both by the clause table and by the two checkers, so "not applicable" is decided in one
# place rather than agreed in two.
BROWSER_LANGUAGES = frozenset({"javascript", "typescript", "html"})

_STORE_LIBRARIES = ("redux", "zustand", "mobx", "vuex", "pinia", "recoil", "jotai")
_DOM_CALLS = ("addEventListener", "querySelector", "querySelectorAll", "getElementById",
              "innerHTML", "createElement", "appendChild")

_MOCK_NAMES = frozenset({"Mock", "MagicMock", "AsyncMock", "patch", "mock_open", "NonCallableMock"})
_MOCK_LIMIT = 3

_HOOK_CALLS = frozenset({"register", "signal", "on_event", "add_event_handler", "atexit"})
_HOOK_DECORATORS = frozenset({"atexit", "on_event", "listens_for", "add_event_handler",
                              "before_request", "after_request", "receiver"})
_HOOK_MODULES = frozenset({"atexit", "signal"})

# Calls that record a failure. The vocabulary is small on purpose: a try whose LAST
# statement records a failure is asserting that the call above it raised, so the catch
# below is the success condition rather than a swallow.
_RECORDS_A_FAILURE = frozenset({"append", "add", "extend", "fail", "error", "insert"})

# BaseException signals that carry control flow rather than failure. `except SystemExit:
# pass` around a `--help` invocation is argparse's normal exit for help, so it is the
# expected terminal state of the thing under test.
#
# What this does NOT decide: a program that swallows an exit it did not intend has a real
# defect, and it is a different one from the silent failure this clause names.
_CONTROL_FLOW = frozenset({"SystemExit", "KeyboardInterrupt", "GeneratorExit"})

_MUTATING_METHODS = frozenset({"append", "extend", "update", "pop", "clear", "setdefault",
                               "add", "remove", "insert", "popitem", "sort", "discard"})

_STEP_DECORATORS = frozenset({"given", "when", "then", "step"})
_STEP_LIMIT = 30

_TYPED_SCALARS = frozenset({"int", "str", "float", "bool", "bytes", "list", "dict", "set", "tuple"})


# --------------------------------------------------------------------------
# 1. Dict-lookup polymorphism over if/elif chains
# --------------------------------------------------------------------------

def dispatch_chains(source: dict) -> list[Finding] | None:
    """An if/elif chain testing ONE name against literals to select behaviour.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers rather than being reimplemented per language.

    Two or more elif arms, because one `if` and one `else` is a binary choice and a table
    starts where the third case would otherwise be another arm.

    Not decided: whether the axis of variation is worth naming. The rule says to build a
    table when you can name the axis and it has a finite set of kinds, and nothing here
    reads that."""
    spec, raw = source["spec"], source["raw"]
    found: list[Finding] = []
    for node in walk(source["root"]):
        if node.type not in spec["branch_types"] or _is_chain_arm(node):
            continue
        names = chain_subjects(node, spec, raw)
        if len(names) >= 3 and len(set(names)) == 1:
            found.append(_finding(
                "L1.21.1", names[0], node.start_point[0] + 1,
                f"{len(names)} arms dispatch on `{names[0]}` to select behaviour",
                "a dict mapping each value to the function that handles it, read by "
                "subscript so an unknown key raises", ""))
    return found


def _is_chain_arm(node: Node) -> bool:
    """Whether this branch is the `else if` of another, rather than the head of a chain.

    Without it a three-armed chain reports three times, once from each arm it is also the
    head of."""
    parent = node.parent
    while parent is not None and parent.type in ("else_clause", "elif_clause"):
        parent = parent.parent
    return parent is not None and parent.type == node.type


def chain_subjects(node: Node, spec: LangSpec, raw: bytes) -> list[str]:
    """The name each arm of one if chain compares against a literal.

    A bounds check, a null guard and ordinary boolean logic contribute nothing: the rule
    says so itself, and a clause firing on every function with a condition teaches a reader
    to ignore the number."""
    subjects: list[str] = []
    for arm in _chain_arms(node, spec):
        test = arm.child_by_field_name(spec["branch_cond"])
        while test is not None and test.type == "parenthesized_expression":
            test = next(iter(test.named_children), None)
        name = _equality_subject(test, spec, raw)
        if not name:
            return []
        subjects.append(name)
    return subjects


def _chain_arms(node: Node, spec: LangSpec) -> list[Node]:
    """Every arm of one if chain, in source order, whichever way the grammar spells it.

    The two shapes are read from structure rather than from a language name. Python hangs
    its `elif` arms off the head as children; JavaScript nests each `else if` inside the
    previous one's alternative. A reader keyed to either shape alone sees a one-armed chain
    in the other language and reports nothing."""
    arms = [node]
    arms += [c for c in node.children if c.type == "elif_clause"]
    current = node
    while True:
        alternative = current.child_by_field_name("alternative")
        if alternative is None:
            return arms
        nested = alternative if alternative.type in spec["branch_types"] else next(
            (c for c in alternative.named_children if c.type in spec["branch_types"]), None)
        if nested is None:
            return arms
        arms.append(nested)
        current = nested


def _equality_subject(test: Node | None, spec: LangSpec, raw: bytes) -> str:
    """The name on one side of an equality test whose other side is a literal."""
    if test is None or test.type not in spec["comparison_types"]:
        return ""
    children = [c for c in test.children if c.is_named or c.type in COMPARISON_OPS]
    operators = [node_text(c, raw) for c in test.children if not c.is_named]
    if not any(op in ("==", "===", "is") for op in operators):
        return ""
    named = [c for c in children if c.is_named]
    if len(named) != 2:
        return ""
    left, right = named
    if right.type in spec["literal_types"] and left.type == "identifier":
        return node_text(left, raw)
    if left.type in spec["literal_types"] and right.type == "identifier":
        return node_text(right, raw)
    return ""





def data_classes(source: dict) -> list[Finding] | None:
    """A class whose body is an `__init__` assigning parameters to self, plus accessors.

    Not decided: whether a class the rule permits was the right choice. A wrapper around a
    resource is allowed and whether it earned the permission is a question for a reader."""
    found: list[Finding] = []
    shapes = DECLARED_SHAPES | _local_exceptions(source)
    for node in _classes(source):
        if set(_base_names(node)) & shapes:
            continue
        methods = _methods(node)
        init = next((m for m in methods if m.name == "__init__"), None)
        if init is None:
            continue
        if _called(init) & RESOURCE_CALLS:
            continue
        others = [m for m in methods if m.name != "__init__"]
        if all(_only_reads_self(m) for m in others):
            found.append(_finding(
                "L1.21.2", node.name, node.lineno,
                "the class holds data and does nothing a dict could not",
                f"a TypedDict: `{node.name} = TypedDict(\"{node.name}\", {{...}})`", ""))
    return found


def _only_reads_self(method: ast.FunctionDef) -> bool:
    """Whether a method reaches `self` only for data it could have been passed.

    A method that writes self or calls another method is doing something a free function
    taking the data could not, so it is left alone."""
    for node in ast.walk(method):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id != "self":
                continue
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                return False
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
            return False
    return True


# --------------------------------------------------------------------------
# 3. Pure functions over methods
# --------------------------------------------------------------------------

def methods_wearing_a_class(source: dict) -> list[Finding] | None:
    """A method that reads `self` only to reach data it could have received.

    Not decided: whether the class is required by a framework. Django models and React
    components are the usual cases and neither is readable from the method alone."""
    found: list[Finding] = []
    for node in _classes(source):
        if set(_base_names(node)) & DECLARED_SHAPES:
            continue
        for method in _methods(node):
            if method.name.startswith("__"):
                continue
            if not _reads_self(method) or not _only_reads_self(method):
                continue
            found.append(_finding(
                "L1.21.3", f"{node.name}.{method.name}", method.lineno,
                "the method reaches self only for data it could have been passed",
                f"a free function: `{method.name}_{node.name.lower()}(data)`", ""))
    return found


def _reads_self(method: ast.FunctionDef) -> bool:
    return any(isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
               and n.value.id == "self" for n in ast.walk(method))


# --------------------------------------------------------------------------
# 4. I/O at the boundary
# --------------------------------------------------------------------------

def io_below_the_boundary(source: dict) -> list[Finding] | None:
    """A function that performs I/O and is itself called by a sibling.

    A function nothing in the module calls IS the edge, which is where the I/O belongs.
    One that a sibling calls has had the I/O pushed inward, and neither it nor its caller
    can be tested without a mock.

    Not decided: whether an uncalled function is truly an entry point. A module read only
    from outside has every function looking like a boundary."""
    functions = list(_functions(source))
    called_by_siblings: set[str] = set()
    for fn in functions:
        called_by_siblings |= _called(fn) - {fn.name}
    found: list[Finding] = []
    for fn in functions:
        if fn.name not in called_by_siblings or _declares_a_boundary(fn):
            continue
        touched = sorted(_io_calls(fn))
        if touched:
            found.append(_finding(
                "L1.21.4", fn.name, fn.lineno,
                f"performs I/O ({', '.join(touched)}) and is called by another function here",
                "take the data as a parameter and let the caller at the edge do the I/O", ""))
    return found


# --------------------------------------------------------------------------
# 5. Flat composition over inheritance
# --------------------------------------------------------------------------

def _declares_a_boundary(fn: ast.FunctionDef) -> bool:
    """Whether this function is decorated as one of the project's own edges.

    Read from what the decorator NAMES, not from its text: a parametrize carrying the word
    as test data is not a declaration, which is the lesson clause 16 learned from one
    carrying an exit handler."""
    for decorator in fn.decorator_list:
        named = decorator.func if isinstance(decorator, ast.Call) else decorator
        if set(ast.unparse(named).split(".")) & BOUNDARY_DECORATORS:
            return True
    return False


def _io_calls(fn: ast.FunctionDef) -> set[str]:
    """The I/O this function performs, by name.

    An unambiguous name counts on its own. An ambiguous one counts only with a receiver
    that names a client, because `TABLE.get(key)` is a dict lookup and `requests.get(url)`
    fetches a page."""
    touched: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        bare = _bare_name(node)
        if bare in _IO_CALLS:
            touched.add(bare)
            continue
        if bare not in _AMBIGUOUS_IO or not isinstance(node.func, ast.Attribute):
            continue
        receiver = ast.unparse(node.func.value).split(".")[-1].lower()
        if receiver in _IO_RECEIVERS:
            touched.add(f"{receiver}.{bare}")
    return touched


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
    found: list[Finding] = []
    shapes = DECLARED_SHAPES | _local_exceptions(source)
    for node in _classes(source):
        inherited = [b for b in _base_names(node) if b not in shapes]
        if inherited:
            found.append(_finding(
                "L1.21.5", node.name, node.lineno,
                f"inherits from {', '.join(inherited)}, which hides where behaviour comes from",
                "compose the steps at the point of assembly: `pipe(validate, authenticate, "
                "create)`", ""))
    return found


# --------------------------------------------------------------------------
# 6 and 7. The two browser clauses
# --------------------------------------------------------------------------

def _local_exceptions(source: dict) -> set[str]:
    """Classes this file defines that reach `Exception` through their own bases.

    Followed to the root rather than one level, so a three-deep hierarchy is still
    exceptions all the way down."""
    bases = {node.name: _base_names(node) for node in _classes(source)}
    known = {name for name, parents in bases.items()
             if set(parents) & {"Exception", "BaseException"}}
    while True:
        grew = {name for name, parents in bases.items() if set(parents) & known} - known
        if not grew:
            return known
        known |= grew


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
    """A handler whose body only passes, or returns a stand-in.

    Catch-and-swallow is the purest form of a silent failure: it reports success for work
    that failed. A handler that re-raises, or that maps the error to a response, is doing
    what the rule asks.

    Not decided: whether the enclosing function is a boundary. A route handler catching and
    mapping is right, and nothing in the file says which functions are routes."""
    found: list[Finding] = []
    for parent in ast.walk(source["tree"]):
        if not isinstance(parent, ast.Try):
            continue
        # The catch is the ASSERTION when the try's last statement records a failure: that
        # statement runs only if the call above it did NOT raise, so reaching it is the
        # defect and the handler is the success condition. Keying on the bare `pass` made
        # both readings look alike.
        if _asserts_a_raise(parent.body):
            continue
        for node in parent.handlers:
            if not _swallows(node.body):
                continue
            if _caught_names(node) <= _CONTROL_FLOW and _caught_names(node):
                continue
            caught = ast.unparse(node.type) if node.type else "everything"
            found.append(_finding(
                "L1.21.8", caught, node.lineno,
                f"catches {caught} and reports success for work that failed",
                "let it raise and map the type to a response at the boundary", ""))
    return found


def _caught_names(handler: ast.ExceptHandler) -> set[str]:
    """The exception names one handler catches, bare or in a tuple."""
    if handler.type is None:
        return set()
    caught = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return {ast.unparse(node).split(".")[-1] for node in caught}


def _asserts_a_raise(body: list[ast.stmt]) -> bool:
    """Whether this try body is asserting that its call raised.

    The shape is a call followed by a statement that records a failure. That statement runs
    only when the call did NOT raise, so the handler beneath is the success condition and
    the defect would be reaching the recorder.

    What it does not decide: whether the recorded failure is the one the author meant. A
    try ending in an unrelated append reads the same way, and separating them would need
    the meaning of the collection rather than its shape."""
    if len(body) < 2:
        return False
    last = body[-1]
    if isinstance(last, (ast.Assert, ast.Raise)):
        return True
    if not isinstance(last, ast.Expr) or not isinstance(last.value, ast.Call):
        return False
    return _bare_name(last.value) in _RECORDS_A_FAILURE


def _swallows(body: list[ast.stmt]) -> bool:
    """Whether a handler body throws the error away.

    A bare `pass`, or a single return of a FALSY stand-in: None, False, zero, an empty
    string or an empty container. Each is indistinguishable from a successful empty result,
    so the caller cannot tell "there were none" from "I could not look".

    A return of a truthy constant is a REPORT, not a swallow. `return "could not query
    rustup toolchains"` names the failure and hands it to a caller that discloses it. The
    first version of this counted that as a swallow, which flagged the one handler in this
    repository doing exactly the right thing."""
    if any(isinstance(n, ast.Raise) for statement in body for n in ast.walk(statement)):
        return False
    meaningful = [s for s in body if not isinstance(s, ast.Pass)]
    if not meaningful:
        return True
    if len(meaningful) > 1:
        return False
    only = meaningful[0]
    if not isinstance(only, ast.Return):
        return False
    if only.value is None:
        return True
    if isinstance(only.value, ast.Constant):
        return not only.value.value
    if isinstance(only.value, (ast.List, ast.Set, ast.Tuple)):
        return not only.value.elts
    if isinstance(only.value, ast.Dict):
        return not only.value.keys
    return False


# --------------------------------------------------------------------------
# 9. SQL over application caches
# --------------------------------------------------------------------------

_UNPROFILED = ("whether the query was profiled first is not readable from any file, so "
               "only the cache itself was checked")


def unmeasured_caches(source: dict) -> list[Finding] | None:
    """A cache client or a memoising decorator.

    Partly decided, and the clause says which half. The cache is readable. Whether anyone
    profiled the query before adding it is not in any file, and implying otherwise would
    claim the whole rule was checked."""
    found: list[Finding] = []
    for node in ast.walk(source["tree"]):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            names = [a.name.split(".")[0] for a in node.names] + [module.split(".")[0]]
            for name in names:
                if name in _CACHE_NAMES:
                    found.append(_finding(
                        "L1.21.9", name, node.lineno,
                        f"{name} is a second source of truth with an invalidation bug waiting",
                        "profile the query and add the index first", _UNPROFILED))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                bare = ast.unparse(decorator).split("(")[0].split(".")[-1]
                if bare in _CACHE_DECORATORS:
                    found.append(_finding(
                        "L1.21.9", node.name, node.lineno,
                        f"@{bare} caches the result before anything measured the cost",
                        "profile it and fix the query or the schema first", _UNPROFILED))
    return found


# --------------------------------------------------------------------------
# 10. Pure-function assertions over mocks
# --------------------------------------------------------------------------

def mock_heavy_tests(source: dict) -> list[Finding] | None:
    """Three or more mocks in one test.

    The count is a readout on the CODE, not on the test: three mocks means the function
    under test has three hidden dependencies. One or two is ordinary isolation.

    Not applicable to a file that is not a test."""
    if not _is_test_file(source["path"]):
        return None
    found: list[Finding] = []
    for fn in _functions(source):
        if not fn.name.startswith("test"):
            continue
        mocks = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and _bare_name(n) in _MOCK_NAMES]
        if len(mocks) >= _MOCK_LIMIT:
            found.append(_finding(
                "L1.21.10", fn.name, fn.lineno,
                f"{len(mocks)} mocks, so the function under test has {len(mocks)} hidden "
                "dependencies",
                "extract the pure logic and assert f(input) == expected on it directly", ""))
    return found


def _bare_name(call: ast.Call) -> str:
    return ast.unparse(call.func).split(".")[-1]


def _is_test_file(path: str) -> bool:
    name = path.replace("\\", "/").split("/")[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in path


# --------------------------------------------------------------------------
# 11. Type declarations over imperative validation
# --------------------------------------------------------------------------

def imperative_validation(source: dict) -> list[Finding] | None:
    """An `isinstance` check on a parameter the signature already types.

    Re-checking a value the signature promised is distrust of your own contract. A check on
    a value that arrived untyped from outside is where validation belongs, so only the
    typed ones are counted.

    Not decided: whether the function is a boundary receiving external input. A typed
    parameter at a true boundary may still deserve a runtime check."""
    found: list[Finding] = []
    for fn in _functions(source):
        typed = {a.arg for a in fn.args.args + fn.args.kwonlyargs
                 if a.annotation is not None
                 and ast.unparse(a.annotation).split("[")[0] in _TYPED_SCALARS}
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and _bare_name(node) == "isinstance"):
                continue
            if not node.args or not isinstance(node.args[0], ast.Name):
                continue
            if node.args[0].id in typed:
                found.append(_finding(
                    "L1.21.11", f"{fn.name}({node.args[0].id})", node.lineno,
                    f"re-checks `{node.args[0].id}`, which the signature already types",
                    "trust the contract in the interior and tighten the boundary or the "
                    "type instead", ""))
    return found


# --------------------------------------------------------------------------
# 12. Context managers over instance state
# --------------------------------------------------------------------------

def unscoped_resources(source: dict) -> list[Finding] | None:
    """A resource assigned to `self` in a class that is not a context manager.

    A connection with a manual lifecycle is a leak waiting for an exception. A class with
    `__enter__` has scoped it, which is the whole point of the rule."""
    found: list[Finding] = []
    for node in _classes(source):
        if any(m.name == "__enter__" or m.name == "__aenter__" for m in _methods(node)):
            continue
        for method in _methods(node):
            for statement in ast.walk(method):
                if not isinstance(statement, ast.Assign):
                    continue
                if not isinstance(statement.value, ast.Call):
                    continue
                if _bare_name(statement.value) not in RESOURCE_CALLS:
                    continue
                for target in statement.targets:
                    if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                        found.append(_finding(
                            "L1.21.12", f"{node.name}.{target.attr}", statement.lineno,
                            "a resource with a manual lifecycle, waiting for an exception",
                            "scope it: `with create_connection(config) as conn:`", ""))
    return found


# --------------------------------------------------------------------------
# 13. Configuration as parameters
# --------------------------------------------------------------------------

_KNOB_UNDECIDED = ("whether a table nobody writes is a knob disguised as a fact is not "
                   "readable from a file, so only the ones some function turns were checked")


def hidden_configuration(source: dict) -> list[Finding] | None:
    """A module-level value that some function WRITES, read inside another.

    The write is what makes it configuration. A table nobody writes is a fact about the
    world, and flagging it would make this clause demand the opposite of clauses 1 and 18,
    which both require exactly such a table. Two clauses of one instrument must not ask for
    opposite things, and the first version of this one did.

    Not decided: whether a knob was disguised as a fact. A module-level value nobody writes
    in this file may still be reassigned from another, and no reading of this file sees
    it."""
    turned = _turned_names(source)
    if not turned:
        return []
    found: list[Finding] = []
    for fn in _functions(source):
        if _turns_any(fn, turned):
            continue
        for name in sorted({n.id for n in ast.walk(fn)
                            if isinstance(n, ast.Name) and n.id in turned}):
            found.append(_finding(
                "L1.21.13", f"{fn.name}({name})", fn.lineno,
                f"reads `{name}`, which another function here writes, so its behaviour "
                "depends on something no caller can see",
                f"take `{name.lower()}` as a parameter, so the dependency is in the "
                "signature", _KNOB_UNDECIDED))
    return found


def _turned_names(source: dict) -> set[str]:
    """Module-level names some function reassigns or mutates in place.

    Somebody turns these, so two callers can get different behaviour for a reason neither
    of them can see at the call site."""
    declared = set(_module_level(source))
    turned: set[str] = set()
    for fn in _functions(source):
        turned |= _written_in(fn) & declared
    return turned


def _written_in(fn: ast.FunctionDef) -> set[str]:
    """The names this function reassigns, subscript-assigns, or mutates by method call."""
    written: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Global):
            written |= set(node.names)
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    written.add(target.id)
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    written.add(target.value.id)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and _bare_name(node) in _MUTATING_METHODS
                and isinstance(node.func.value, ast.Name)):
            written.add(node.func.value.id)
    return written


def _turns_any(fn: ast.FunctionDef, turned: set[str]) -> bool:
    """Whether this function is one of the ones doing the turning. It is the writer rather
    than a reader surprised by the write."""
    return bool(_written_in(fn) & turned)


def _module_level(source: dict) -> dict[str, ast.expr]:
    """The names assigned at module level, and what they were assigned."""
    assigned: dict[str, ast.expr] = {}
    for node in source["tree"].body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned[target.id] = node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            assigned[node.target.id] = node.value
    return assigned


# --------------------------------------------------------------------------
# 14. No implicit defaults
# --------------------------------------------------------------------------

def implicit_defaults(source: dict) -> list[Finding] | None:
    """A LITERAL default, which cannot be told from a caller who chose that value.

    A default that binds a collaborator is the opposite failure. It makes a dependency
    visible in the signature, which is what rule 13 asks for, and flagging it would push
    the code back toward the module-level lookup the rule exists to remove."""
    found: list[Finding] = []
    for fn in _functions(source):
        defaults = list(zip(fn.args.args[len(fn.args.args) - len(fn.args.defaults):],
                            fn.args.defaults))
        defaults += [(a, d) for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults) if d]
        for argument, default in defaults:
            if not _is_literal(default):
                continue
            found.append(_finding(
                "L1.21.14", f"{fn.name}({argument.arg})", fn.lineno,
                f"`{argument.arg}={ast.unparse(default)}` absorbs the caller's omission, so "
                "nothing can tell chose from forgot",
                "make absence an explicit case of a bounded type, resolved at the boundary "
                "and exercised by a test", ""))
    return found


def _is_literal(node: ast.expr) -> bool:
    """Whether a default is a value rather than a bound collaborator."""
    if isinstance(node, ast.UnaryOp):
        return _is_literal(node.operand)
    return isinstance(node, (ast.Constant, ast.List, ast.Dict, ast.Set, ast.Tuple))


# --------------------------------------------------------------------------
# 15. Simple gherkin steps
# --------------------------------------------------------------------------

def heavy_step_definitions(source: dict) -> list[Finding] | None:
    """A step definition longer than thirty lines.

    Step length is a readout on the ARCHITECTURE, not on the test: a step needing thirty
    lines of setup means the code under test has hidden dependencies.

    Not applicable to a file holding no step definitions."""
    steps = [fn for fn in _functions(source)
             if any(ast.unparse(d).split("(")[0].split(".")[-1] in _STEP_DECORATORS
                    for d in fn.decorator_list)]
    if not steps:
        return None
    return [_finding(
        "L1.21.15", fn.name, fn.lineno,
        f"{fn.end_lineno - fn.lineno} lines of setup, which is a readout on the code under "
        "test rather than on the test",
        "make the function under test pure, so the step is call it and check the result", "")
        for fn in steps if (fn.end_lineno or fn.lineno) - fn.lineno > _STEP_LIMIT]


# --------------------------------------------------------------------------
# 16. Declarative equivalents over lifecycle hooks
# --------------------------------------------------------------------------

def lifecycle_hooks(source: dict) -> list[Finding] | None:
    """An exit handler, a signal handler, an ORM callback or a mount effect.

    Each puts behaviour somewhere the reader does not look. A call at the place it happens
    is not a hook, however much work it does."""
    found: list[Finding] = []
    for node in ast.walk(source["tree"]):
        if not isinstance(node, ast.Call):
            continue
        whole = ast.unparse(node.func)
        root = whole.split(".")[0]
        if root in _HOOK_MODULES and _bare_name(node) in _HOOK_CALLS:
            found.append(_finding(
                "L1.21.16", whole, node.lineno,
                f"{whole} parks behaviour where the reader does not look",
                "declare it where it happens, so the sequence is visible at the call site", ""))
    for node in ast.walk(source["tree"]):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            # What a decorator DOES is decided by what it calls, not by what it carries.
            # Matching the unparsed decorator as text read a parametrize whose test data
            # was the string "atexit.register(cleanup)" as a registration.
            called = decorator.func if isinstance(decorator, ast.Call) else decorator
            whole = ast.unparse(called)
            if any(name in whole.split(".") for name in _HOOK_DECORATORS):
                found.append(_finding(
                    "L1.21.16", node.name, node.lineno,
                    f"@{whole} runs this somewhere nobody reads",
                    "call it where it happens", ""))
    return found


# --------------------------------------------------------------------------
# 17. Strangler pattern — the clause nothing decides
# --------------------------------------------------------------------------

def strangler_migration(source: dict) -> list[Finding] | None:
    """Never a verdict.

    A property of how a migration is sequenced over weeks. No file, and no set of files,
    carries the sequence of the work that produced them, so a pass here would be a claim
    nobody could support. It is the one clause excluded by its nature rather than by the
    reach of this reader."""
    return None


# --------------------------------------------------------------------------
# 18. Dispatch tables close open input
# --------------------------------------------------------------------------

def open_dispatch(source: dict) -> list[Finding] | None:
    """A `.get(key, default)` on a module-level table.

    The default files an input nobody wrote a rule for under an answer written for a
    different input, and re-opens the space while the code still reads closed. A subscript
    lets an unknown key raise, which records the gap in the table instead of hiding it."""
    tables = {name for name, value in _module_level(source).items()
              if isinstance(value, ast.Dict)}
    found: list[Finding] = []
    for node in ast.walk(source["tree"]):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "get" or len(node.args) < 2:
            continue
        # A default DERIVED FROM THE KEY records the gap rather than hiding it. The rule's
        # objection is that a default files an unknown input under an answer written for a
        # different input; `COPY.get(key, key)` and `REASONS.get(code, f"unknown {code}")`
        # do the opposite, and the unknown key comes back visible as itself.
        if _mentions(node.args[1], node.args[0]):
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id in tables:
            found.append(_finding(
                "L1.21.18", node.func.value.id, node.lineno,
                f"`{node.func.value.id}.get(key, default)` answers for an input nobody wrote "
                "a rule for",
                f"read it by subscript, `{node.func.value.id}[key]`, and record the unknown "
                "key as a gap in the table", ""))
    return found


# --------------------------------------------------------------------------
# 19. Atomic test-and-set over check-then-act
# --------------------------------------------------------------------------

def _mentions(default: ast.expr, key: ast.expr) -> bool:
    """Whether the default expression is built from the key it is standing in for."""
    wanted = ast.dump(key)
    return any(ast.dump(node) == wanted for node in ast.walk(default))


def check_then_act(source: dict) -> list[Finding] | None:
    """A read of a shared value followed by a write to it, inside one function.

    Between the read and the write another caller reads the same answer, and both proceed
    believing they hold the thing. An `await` in between makes the race certain rather than
    occasional, and the finding says which it found.

    Not decided: whether the value is genuinely shared across callers. A module-level
    container is the readable case; a row in a database is not in this file."""
    shared = {name for name, value in _module_level(source).items()
              if isinstance(value, (ast.Dict, ast.List, ast.Set))}
    found: list[Finding] = []
    for fn in _functions(source):
        for name in sorted(shared):
            read = _first_line(fn, name, ast.Load, subscript=False)
            write = _first_line(fn, name, ast.Store, subscript=True)
            if read is None or write is None or write <= read:
                continue
            awaited = any(isinstance(n, ast.Await) and read < n.lineno < write
                          for n in ast.walk(fn))
            certainty = "certain" if awaited else "occasional"
            found.append(_finding(
                "L1.21.19", f"{fn.name}({name})", read,
                f"reads `{name}` at line {read} and writes it at line {write}, so two "
                f"callers can both believe they hold it. The race is {certainty}"
                + (", because there is an await in between" if awaited else ""),
                "one operation whose return value distinguishes I took it from someone "
                "else holds it, carrying a token unique to the caller", ""))
    return found


def _first_line(fn: ast.FunctionDef, name: str, context: type, subscript: bool) -> int | None:
    """The first line where `name` is used in the given context, or None.

    A write through a subscript is a write to the container, so `LOCKS[key] = True` counts
    even though the Name node itself is being loaded."""
    for node in ast.walk(fn):
        if (subscript and isinstance(node, ast.Subscript) and isinstance(node.ctx, context)
                and isinstance(node.value, ast.Name) and node.value.id == name):
            return node.lineno
        if (not subscript and isinstance(node, ast.Name) and node.id == name
                and isinstance(node.ctx, context)):
            return node.lineno
    return None
