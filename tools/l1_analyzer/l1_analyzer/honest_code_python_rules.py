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
    _finding,
    _functions,
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


# Names that mean I/O only with a receiver that names a client. `TABLE.get(key)` is a dict
# lookup and `requests.get(url)` fetches a page.
#
_CACHE_NAMES = frozenset({"redis", "memcache", "memcached", "pylibmc", "diskcache", "aiocache"})
_CACHE_DECORATORS = frozenset({"lru_cache", "cache", "cached", "memoize", "cached_property"})
_STEP_DECORATORS = frozenset({"given", "when", "then", "step"})
_STEP_LIMIT = 30
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


def _bare_name(call: ast.Call) -> str:
    return ast.unparse(call.func).split(".")[-1]


def _is_test_file(path: str) -> bool:
    name = path.replace("\\", "/").split("/")[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in path


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
