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
# Calls whose bare name means I/O wherever it appears.
#
# `print` and `input` were missing, and that one absence produced two symptoms a peer found
# by running this and another checker over one codebase: 34 functions where this called a
# boundary declaration false and the other did not, and 28 declarations they had removed on
# this reader's word and then restored. Every case was a name absent here. Printing is
# output, and I/O at the Boundary is about I/O in both directions rather than intake alone.
#
# Adding them halved the findings on this package and the adopter's together, 62 to 31,
# because most of what they had produced was this clause calling a true declaration false.
_IO_CALLS = frozenset({
    "read_text", "read_bytes", "write_text", "write_bytes", "open", "iterdir", "glob",
    "Popen", "check_output", "urlopen", "execute", "fetchall", "fetchone", "commit",
    "listdir", "makedirs", "remove",
    "print", "input",
})
# Calls whose bare name is shared with something ordinary. `TABLE.get(key)` is a dict
# lookup and `requests.get(url)` fetches a page, and reading the bare name reported this
# tool's own suffix table as I/O. These are matched on the whole dotted call.
# Adding a bare `write` or `read` here instead more than doubled the findings on two real
# codebases, because those are ordinary method names on ordinary objects: `buffer.write(x)`
# is not I/O. As receivers they cost nothing measurable and close every gap the peer named.
_IO_RECEIVERS = frozenset({
    "requests", "httpx", "session", "client", "urllib", "aiohttp", "subprocess",
    "conn", "connection", "cursor", "db",
    "engine", "logging", "logger", "log",
})
# Receivers whose every call reaches outside the process. `os.path.join` is not one of
# these: the receiver there is `path`, not `os`, because the last segment is what is read.
_IO_MODULES = frozenset({
    "stdout", "stderr", "stdin",
    "psycopg2", "psycopg", "asyncpg", "sqlite3", "aiosqlite", "pymongo", "redis",
    "smtplib", "ftplib", "imaplib", "poplib",
})

# Named one call at a time rather than by their module, because most of what these modules
# hold is not I/O. `os.getenv` reads process state and `os.path.join` joins strings, and
# taking the whole of `os` reported both. `shutil.which` asks PATH whether a tool exists,
# which every tracer here does once, and taking the whole of `shutil` reported eight of them.
_IO_DOTTED = frozenset({
    "os.read", "os.write", "os.rename", "os.mkdir", "os.rmdir", "os.walk", "os.remove",
    "os.system", "os.popen", "os.fork", "os.execvp",
    "shutil.copy", "shutil.copyfile", "shutil.move", "shutil.rmtree",
    "socket.socket", "socket.create_connection", "socket.gethostbyname",
    "socket.gethostbyaddr", "socket.getaddrinfo", "socket.getfqdn", "socket.create_server",
    "tempfile.mkdtemp", "tempfile.NamedTemporaryFile", "tempfile.TemporaryDirectory",
    "mmap.mmap",
    # Ambient input a caller cannot see, and a module read off disk and executed. Named by
    # an adopter, alongside three this clause refuses: `asyncio.run`, `asyncio.create_task`
    # and `uuid.uuid4` are non-determinism and scheduling. Another checker treats those as a
    # boundary privilege beside I/O; this clause is about I/O alone, and folding them in
    # would make it a different rule wearing the same number.
    "environ.get", "environ.setdefault", "util.spec_from_file_location",
    "loader.exec_module", "spec.loader",
})

# Names that mean I/O only with a receiver that names a client. `TABLE.get(key)` is a dict
# lookup and `requests.get(url)` fetches a page.
#
# The logging calls are here rather than `logging` being a whole module, which is where they
# were until a peer found the same fault in their own list and checked mine. `getLogger`
# returns an object from a registry and reaches nothing, and taking the module whole made it
# I/O. A false entry is worse than a missing one: a missing entry leaves real I/O unmarked
# in the interior, and a false one demands a boundary declaration on a function that is
# pure, which is a suppression wearing a declaration's name.
_AMBIGUOUS_IO = frozenset({
    "get", "post", "put", "delete", "patch", "request", "run", "head",
    "debug", "info", "warning", "warn", "error", "exception", "critical", "basicConfig",
})
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
    called_by_siblings = _named_in_a_table(source)
    for fn in functions:
        called_by_siblings |= _called(fn) - {fn.name}
    # A function that CALLS a declared boundary is reaching an edge through the thing that
    # made the claim. An adopter measured 14 sites here and eight were the error-handling
    # layer directly above the I/O: a function whose whole job is catching what a boundary
    # raised, holding no I/O of its own.
    #
    # It was a real conflict rather than a preference. Another checker grants a boundary the
    # right to catch and refuses a non-boundary that catch, so such a function must carry
    # the marker there and must not carry it here, and no marking satisfied both.
    #
    # One step, not transitively. A declaration is a claim about the function carrying it,
    # and following further would let a declaration three calls away excuse a function that
    # reaches nothing.
    declared_here = {fn.name for fn in functions if _declares_a_boundary(fn)}
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
        if _declares_a_boundary(fn) and not _io_calls(fn) and not (_called(fn) & declared_here):
            found.append(_finding(
                "L1.21.4", fn.name, fn.lineno,
                "declares itself a boundary and makes no call this reader counts as I/O, "
                "so the declaration states an edge that is not there",
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


def _named_in_a_table(source: dict) -> set[str]:
    """Every bare name a map literal holds as a value, anywhere in the file.

    A function a dispatch table holds IS called: the table is how it is reached. Clause 4
    built its call graph from calls by name, so a function that is only ever a table value
    was reached by nothing as far as this reader could see, and it was silent in both
    directions on such a function.

    An adopter found it, and the irony is the point: this instrument tells people to replace
    if/elif chains with dispatch tables, and a reader following named calls only is blind to
    most of the interior of a codebase written that way.

    Only a bare name. A table of strings is data about names rather than a call graph, and
    reading one as an edge would reach anything a table happens to mention."""
    named: set[str] = set()
    for node in ast.walk(source["tree"]):
        if not isinstance(node, ast.Dict):
            continue
        named |= {value.id for value in node.values if isinstance(value, ast.Name)}
    return named


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
        if not isinstance(node.func, ast.Attribute):
            continue
        receiver = ast.unparse(node.func.value).split(".")[-1].lower()
        # A module that only does I/O makes every call on it I/O, whatever the call is
        # named: `os.walk`, `redis.Redis`, `sys.stderr.write`. Read from the receiver alone
        # because the names are open-ended and listing them would go stale by the next
        # release of any of these.
        if receiver in _IO_MODULES or f"{receiver}.{bare}" in _IO_DOTTED:
            touched.add(f"{receiver}.{bare}")
            continue
        if bare in _AMBIGUOUS_IO and receiver in _IO_RECEIVERS:
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

    This measures Trust the Contract in the Interior, not Type Declarations Over Imperative
    Validation, and it was named after the second until the two were separated upstream.
    They are different failures. This one is a branch nothing can reach: in a correct
    program the caller has already been excluded by the declaration, and in an incorrect one
    it fires where the type checker should have. The other is a hand-written check that
    copies a constraint declared somewhere else, a schema column or a form field, and drifts
    from it. Nothing here measures that one.

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
