"""Clauses this reader still reads through Python's own parser.

Every clause here is one the port has not reached. It reads `source["tree"]`, which the
runner fills only for Python, so it reports `unreadable` on every other language and says
why. A clause moves out of this module when it learns to read the shared node vocabulary in
`lang_spec`, and this module disappears when the last one has.

That is the seam, and it is the one the growth actually follows. Splitting `honest_code_rules`
by clause number or by size would have put a boundary where nothing changes; this one encodes
the migration and deletes itself at the end of it.
"""

import ast

from l1_analyzer.honest_code_read import (
    Finding,
    _called,
    _classes,
    _finding,
    _functions,
    _methods,
)
from l1_analyzer.honest_code_rules import (
    BOUNDARY_DECORATORS,
    RESOURCE_CALLS,
)

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
_MOCK_NAMES = frozenset({"Mock", "MagicMock", "AsyncMock", "patch", "mock_open", "NonCallableMock"})
_MOCK_LIMIT = 3
_HOOK_CALLS = frozenset({"register", "signal", "on_event", "add_event_handler", "atexit"})
_HOOK_DECORATORS = frozenset({"atexit", "on_event", "listens_for", "add_event_handler",
                              "before_request", "after_request", "receiver"})
_HOOK_MODULES = frozenset({"atexit", "signal"})
_STEP_DECORATORS = frozenset({"given", "when", "then", "step"})
_STEP_LIMIT = 30
_TYPED_SCALARS = frozenset({"int", "str", "float", "bool", "bytes", "list", "dict", "set", "tuple"})
_UNPROFILED = ("whether the query was profiled first is not readable from any file, so "
               "only the cache itself was checked")



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
        # A DECLARATION THAT IS NOT TRUE. The decorator says this function is an edge, and
        # a function reaching nothing outside the process is not one. Nothing reported it
        # before: the clause never fires on such a function anyway, so the declaration
        # silenced nothing and sat there looking like a fact.
        #
        # This is the one case where a stamp is computable. Telling a real declaration from
        # a stamp in general is not, which the boundary module's own docstring says. A peer
        # maintaining the write hook built a detector that counted markers rather than
        # markers that withheld anything, found it wrong three times in four, and removed
        # it. Reported whether or not a sibling calls it: the uncalled-function exemption
        # exists because such a function may be the entry point, and an entry point that
        # obtains nothing is still not an edge.
        if _declares_a_boundary(fn) and not _io_calls(fn):
            found.append(_finding(
                "L1.21.4", fn.name, fn.lineno,
                "declares itself a boundary and obtains nothing outside the process, so "
                "the declaration states an edge that is not there",
                "take the decorator off, or move the read or the call this function was "
                "meant to be the edge for into it", ""))
            continue
        if fn.name not in called_by_siblings:
            continue
        touched = sorted(_io_calls(fn))
        if touched:
            # Emitted and marked, not dropped. A suppression that suppresses nothing is
            # invisible from outside the analyzer, so a consumer counting declarations had
            # to infer from the presence of a decorator and was wrong three times in four.
            withheld = "declaration" if _declares_a_boundary(fn) else ""
            finding = _finding(
                "L1.21.4", fn.name, fn.lineno,
                f"performs I/O ({', '.join(touched)}) and is called by another function here",
                "take the data as a parameter and let the caller at the edge do the I/O", "")
            finding["withheld_by"] = withheld
            found.append(finding)
    return found


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
                            "make the resource a context manager and take it in a `with` block, so it is released on the path that raises as well as the one that returns", ""))
    return found


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
                "call the work directly at the point it is needed, so the sequence is visible at the call site rather than in a registration", ""))
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
                    "call the work directly at the point it is needed, so a reader sees it in the flow rather than in a registration that runs later", ""))
    return found


def strangler_migration(source: dict) -> list[Finding] | None:
    """Never a verdict, and never called.

    A property of how a migration is sequenced over weeks. No file, and no set of files,
    carries the sequence of the work that produced them, so a pass here would be a claim
    nobody could support. It is the one clause excluded by its nature rather than by the
    reach of this reader.

    The gate answers `never` for this clause before any checker runs, so this body is
    unreachable. It used to return None, which reads to a caller exactly like a clause that
    ran and found nothing; reaching it means that gate has stopped working, and a silent
    None would let the failure arrive somewhere else as a clean result."""
    raise NotImplementedError(
        "clause 17 has no checker: nothing decides the strangler pattern, and the gate "
        "should have answered `never` before reaching this")


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
