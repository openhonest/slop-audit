"""Closeable facets and the Silence index, for one module and its test file.

Umbra's core measurement, in Slop Audit. The panel this package already reports is a
repository-wide reading of twenty indicators, and no panel can say which function in which
module carries an unasserted branch. This can, because it takes the pair Umbra takes: the
module, and the test file that is supposed to have evidence about it.

The vocabulary is Umbra's own, from its glossary rather than reinvented:

  closeable facet    one deterministic audit opportunity the suite can close with evidence
  closeable silence  a closeable facet for which the current suite lacks that evidence
  Silence index      the percentage of closeable facets that are closeable silences
  undeclared domain  an argument the code never types; closed by declaring a type, not a test

**Coverage and silence are different measures, and the distinction is the whole point.**
Coverage records what RAN. Silence records evidence the suite LACKS. A branch that executed
and was never asserted on is covered and silent at once, and only the second number says
so. Reporting one without the other is how a suite that touches every line while asserting
almost nothing reads as thorough.

**Why a share of no facets is None rather than zero.** Zero is the CLEAN end of this scale.
A module nobody could enumerate would otherwise read as fully evidenced, which is the
unmeasured-read-as-clean shape this whole package exists to name.

An UNDECLARED parameter is not a silence. Umbra's glossary is explicit that you close an
undeclared domain by declaring a type, and counting it here would blame the test suite for
a gap in the signature. They are reported separately so the reader sees them without the
index charging the wrong person.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

# The five kinds, named as a closed set. A facet nobody wrote a rule for must be absent
# loudly rather than missing from the denominator, which would raise the evidenced share.
FACET_KINDS = (
    "unexercised_branch",
    "candidate_input_region",
    "unasserted_return_contract",
    "exception_path",
    "runtime_property",
)

# Boundary-bearing regions of a declared value space. Canonical rather than exhaustive:
# these are the partitions a reader would name for the type, and a type with no entry here
# contributes no region rather than a guessed one.
_REGIONS: dict[str, tuple[str, ...]] = {
    "int": ("zero", "negative", "positive"),
    "float": ("zero", "negative", "positive"),
    "str": ("empty", "non-empty"),
    "bytes": ("empty", "non-empty"),
    "list": ("empty", "non-empty"),
    "dict": ("empty", "non-empty"),
    "set": ("empty", "non-empty"),
    "tuple": ("empty", "non-empty"),
    "bool": ("true", "false"),
}


class Facet(TypedDict):
    """One audit opportunity, and whether the suite has evidence for it."""
    kind: str
    function: str
    line: int
    detail: str
    silent: bool


class Undeclared(TypedDict):
    """A domain the code never typed. Closed by declaring a type, not by a test."""
    kind: str
    function: str
    line: int
    detail: str


class Audit(TypedDict):
    """What one module-and-test-file pair yields.

    `silence_index` is None when nothing was enumerable, and `unusable_reason` says why.
    `coverage_percent` is None when the suite produced no coverage data, which is a
    different absence and is reported as its own."""
    module: str
    tests: str
    facets: list[Facet]
    undeclared: list[Undeclared]
    total_checkable_facets: int
    closeable_silence_sites: int
    silence_index: float | None
    coverage_percent: float | None
    coverage_measured: bool
    suite_succeeded: bool
    unusable_reason: str


def _functions(tree: ast.AST) -> list[ast.FunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def is_declared(node: ast.expr | None) -> bool:
    """Whether a type was declared at all, which is a different question from which one.

    `_annotation` used to answer both and returned the empty string for each, so a type it
    could not read was indistinguishable from no type. Every parameter typed `ast.AST`,
    `ast.expr` or `int | None` was reported as an UNDECLARED DOMAIN, which blames the
    author for a gap in the reader. Two questions, two functions."""
    return node is not None


def _annotation(node: ast.expr | None) -> str:
    """The bare name of a declared type, or the empty string when there is no single one.

    A union has no one name and no one region table, so it reads empty here. `is_declared`
    is what keeps it out of the undeclared list."""
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _annotation(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.split("[")[0].strip('"\'')
    return ""


def _names(target: ast.expr) -> list[str]:
    """Every name an assignment target binds, unpacking tuples and lists."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in _names(element)]
    return []


def asserted_calls(tests: ast.AST) -> set[str]:
    """Functions whose RESULT a test asserts on.

    A call inside an `assert`, or bound to a name the test later asserts about, is
    evidence. A bare call statement is not: it proves the function runs and nothing about
    what it returns, which is exactly the gap `unasserted_return_contract` names."""
    asserted: set[str] = set()
    bound: dict[str, str] = {}
    for node in ast.walk(tests):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            name = _called_name(node.value)
            for target in node.targets:
                # A tuple target binds every name in it to the same call. Reading only the
                # plain-name form meant `a, b = f()` followed by `assert a == 1` was not
                # counted, so a function whose result the test unpacks and asserts on read
                # as having no evidence at all.
                for bindable in _names(target):
                    if name:
                        bound[bindable] = name
        if isinstance(node, ast.Assert):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    called = _called_name(inner)
                    if called:
                        asserted.add(called)
                if isinstance(inner, ast.Name) and inner.id in bound:
                    asserted.add(bound[inner.id])
    return asserted


def expected_exceptions(tests: ast.AST) -> set[str]:
    """Functions a test calls inside a `pytest.raises` block.

    That block IS the assertion: it fails when nothing is raised, so it is evidence about
    the exception path in a way a bare call never is."""
    expecting: set[str] = set()
    for node in ast.walk(tests):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        managers = [item.context_expr for item in node.items]
        if not any("raises" in ast.unparse(manager) for manager in managers):
            continue
        # The manager's own call is not evidence about anything the block tests. Collecting
        # it put `raises` in the set, so a module holding a function of that name had its
        # exception path read as asserted by any raises block anywhere in the suite.
        for inner in ast.walk(node):
            if inner in managers or any(inner in ast.walk(m) for m in managers):
                continue
            if isinstance(inner, ast.Call):
                called = _called_name(inner)
                if called:
                    expecting.add(called)
    return expecting


def bound_regions(tests: ast.AST) -> dict[str, set[str]]:
    """Local names in the test file that carry a literal, and the regions those land in.

    Two sources, and the first matters most. A parametrised test supplies its literals in
    the DECORATOR rather than at the call, so reading call sites alone reported `region
    zero` silent on functions whose own tests pass zero repeatedly. Most well-tested suites
    are parametrised, so that overstated silence and pointed a reader at regions already
    covered, which is worse than a number that is merely high: it sends them to fix
    something that is not broken.

    The second is a plain assignment, which is the same reasoning one step smaller.

    A name can carry several regions, because a parametrised case list is exactly a set of
    values for one name, and every one of them is evidence."""
    bound: dict[str, set[str]] = {}

    for node in ast.walk(tests):
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Constant, ast.UnaryOp,
                                                                   ast.List, ast.Set, ast.Tuple,
                                                                   ast.Dict)):
            region = _region_of(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name) and region:
                    bound.setdefault(target.id, set()).add(region)
        for decorator in getattr(node, "decorator_list", []):
            for name, region in _parametrized(decorator):
                bound.setdefault(name, set()).add(region)
    return bound


def _parametrized(decorator: ast.expr) -> list[tuple[str, str]]:
    """The (parameter name, region) pairs a `parametrize` decorator supplies.

    Both spellings: one name as a string, or several as a comma-separated string or a
    tuple. A case whose value is not a literal contributes nothing rather than a guess."""
    if not (isinstance(decorator, ast.Call) and "parametrize" in ast.unparse(decorator.func)):
        return []
    if len(decorator.args) < 2:
        return []
    spec, cases = decorator.args[0], decorator.args[1]
    if isinstance(spec, ast.Constant) and isinstance(spec.value, str):
        names = [part.strip() for part in spec.value.split(",")]
    elif isinstance(spec, (ast.Tuple, ast.List)):
        names = [e.value for e in spec.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    else:
        return []
    if not isinstance(cases, (ast.List, ast.Tuple)):
        return []

    out: list[tuple[str, str]] = []
    for case in cases.elts:
        values = case.elts if isinstance(case, (ast.Tuple, ast.List)) else [case]
        for name, value in zip(names, values):
            region = _region_of(value)
            if region:
                out.append((name, region))
    return out


def supplied_regions(tests: ast.AST) -> dict[str, set[str]]:
    """For each function a test calls, the regions its LITERAL arguments land in.

    Keyed by `function/parameter-position`, because a region belongs to one parameter and
    evidence for the first argument says nothing about the second.

    Only literals. A value assembled at runtime cannot be attributed to a region from the
    source, and guessing which one it lands in would count evidence nobody produced. Such a
    call leaves its regions silent, which is the honest reading: the suite may well cover
    them and this rule cannot see that it does."""
    supplied: dict[str, set[str]] = {}
    bound = bound_regions(tests)
    for node in ast.walk(tests):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node)
        if not name:
            continue
        for position, argument in enumerate(node.args):
            supplied.setdefault(f"{name}/{position}", set()).update(regions_of(argument, bound))
        for keyword in node.keywords:
            if keyword.arg:
                supplied.setdefault(f"{name}/{keyword.arg}",
                                    set()).update(regions_of(keyword.value, bound))
    return supplied


def regions_of(node: ast.expr, bound: dict[str, set[str]]) -> set[str]:
    """A literal's own region, or every region a name bound in the test file carries.

    Module level rather than a closure over `bound`: a nested function cannot be called by
    a test, so its own return contract was unassertable by construction."""
    direct = _region_of(node)
    if direct:
        return {direct}
    return bound.get(node.id, set()) if isinstance(node, ast.Name) else set()


def _region_of(node: ast.expr) -> str:
    """Which boundary region a literal argument lands in, or nothing when it is not one."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _region_of(node.operand)
        return "negative" if inner in ("positive", "zero") else ""
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return "zero" if value == 0 else ("positive" if value > 0 else "negative")
        if isinstance(value, (str, bytes)):
            return "empty" if len(value) == 0 else "non-empty"
        return ""
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return "empty" if not node.elts else "non-empty"
    if isinstance(node, ast.Dict):
        return "empty" if not node.values else "non-empty"
    # `set()` and `dict()` are how an empty collection is usually written, and reading them
    # as unreadable reported a region silent that the test right in front of it supplies.
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in ("set", "dict", "list", "tuple", "frozenset", "bytes", "str"):
            return "empty" if not (node.args or node.keywords) else "non-empty"
        if node.func.id in ("int", "float"):
            return "zero" if not node.args else ""
    return ""


def _called_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _branch_facets(fn: ast.FunctionDef, uncovered: frozenset[int]) -> list[Facet]:
    """Every reachable branch, silent when coverage never entered it."""
    out: list[Facet] = []
    for node in ast.walk(fn):
        if not isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.Match)):
            continue
        # Every one of these nodes has a non-empty body in any tree the parser accepts, so
        # a guard here would be a check against a shape that cannot arrive.
        entry = node.body[0].lineno
        out.append({
            "kind": "unexercised_branch", "function": fn.name, "line": node.lineno,
            "detail": f"{type(node).__name__.lower()} at line {node.lineno}",
            "silent": entry in uncovered,
        })
    return out


def _region_facets(fn: ast.FunctionDef,
                   supplied: dict[str, set[str]]) -> tuple[list[Facet], list[Undeclared]]:
    """One facet per boundary-bearing region of each DECLARED parameter type.

    An undeclared parameter yields no facet and one `undeclared_domain` instead, because
    the glossary is explicit that you close that by declaring a type. Charging the suite
    for it would blame the wrong person and would raise the silence index for a defect a
    test cannot fix."""
    out: list[Facet] = []
    undeclared: list[Undeclared] = []
    positional = [a for a in fn.args.args if a.arg not in ("self", "cls")]
    for arg in fn.args.args + fn.args.kwonlyargs:
        if arg.arg in ("self", "cls"):
            continue
        position = positional.index(arg) if arg in positional else None
        evidence = supplied.get(f"{fn.name}/{arg.arg}", set())
        if position is not None:
            evidence = evidence | supplied.get(f"{fn.name}/{position}", set())
        declared = _annotation(arg.annotation)
        if not is_declared(arg.annotation):
            undeclared.append({
                "kind": "undeclared_domain", "function": fn.name, "line": fn.lineno,
                "detail": f"parameter `{arg.arg}` has no declared type",
            })
            continue
        for region in _REGIONS.get(declared, ()):
            out.append({
                "kind": "candidate_input_region", "function": fn.name, "line": fn.lineno,
                "detail": f"`{arg.arg}: {declared}` region {region}",
                "silent": region not in evidence,
            })
    return out, undeclared


def _return_facet(fn: ast.FunctionDef, asserted: set[str]) -> list[Facet]:
    """A declared return type is a contract, and an unasserted result is no evidence."""
    if _annotation(fn.returns) in ("", "None"):
        return []
    return [{
        "kind": "unasserted_return_contract", "function": fn.name, "line": fn.lineno,
        "detail": f"declares `-> {ast.unparse(fn.returns)}` and no test asserts its result",
        "silent": fn.name not in asserted,
    }]


def _exception_facets(fn: ast.FunctionDef, expecting: set[str]) -> list[Facet]:
    """Every explicit raise. A bare `raise` re-raises and is the same path as its cause."""
    out: list[Facet] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Raise) and node.exc is not None:
            out.append({
                "kind": "exception_path", "function": fn.name, "line": node.lineno,
                "detail": f"raises {ast.unparse(node.exc).split('(')[0]}",
                "silent": fn.name not in expecting,
            })
    return out


def import_root(module: Path) -> Path:
    """The directory the module's package is importable FROM.

    Walk up while `__init__.py` exists, so `pkg/sub/m.py` is imported from the parent of
    `pkg`. Running pytest in the module's own directory instead is what produced a null
    coverage reading on every real package: the test says `from pkg import m` and the
    interpreter, started inside `pkg`, cannot see it. The suite then errors on import,
    coverage records nothing, and the audit reports no measurement at all.

    That is the failure this whole measure exists to name, in the measure itself: a null
    where a number was available, and nothing saying the run never started."""
    directory = module.parent
    while (directory / "__init__.py").exists() and directory.parent != directory:
        directory = directory.parent
    return directory


def _coverage(module: Path, tests: tuple[Path, ...]) -> tuple[frozenset[int], float | None, bool]:
    """Uncovered lines, the branch percentage, and whether the suite succeeded.

    Coverage data goes to a temp directory so the target's own settings and data are
    untouched: an audit that writes into the tree it measures has changed it."""
    with tempfile.TemporaryDirectory(prefix="l1-facets-") as directory:
        data = Path(directory) / "data"
        report = Path(directory) / "coverage.json"
        run = subprocess.run(
            [sys.executable, "-m", "coverage", "run", "--branch", f"--data-file={data}",
             f"--include={module}", "-m", "pytest", *[str(t) for t in tests],
             "-q", "-p", "no:cacheprovider"],
            cwd=import_root(module), capture_output=True, text=True, timeout=600, check=False)
        made = subprocess.run(
            [sys.executable, "-m", "coverage", "json", f"--data-file={data}", "-o", str(report)],
            cwd=import_root(module), capture_output=True, text=True, timeout=300, check=False)
        # Exit 0 is a green suite and 1 is a red one; both RAN, so their coverage is a
        # reading. Anything else is a collection error, a usage error or an empty run, and
        # the percentage it leaves behind is not evidence about what the tests reach. A
        # module that raised on import reported 100% covered, which is this instrument's
        # own bug category turned on itself: unmeasured read as clean.
        if run.returncode not in (0, 1):
            return frozenset(), None, False
        if made.returncode != 0 or not report.exists():
            return frozenset(), None, run.returncode == 0
        payload = json.loads(report.read_text())
        files = payload.get("files", {})
        entry = next((v for k, v in files.items() if Path(k).name == module.name), None)
        if entry is None:
            return frozenset(), None, run.returncode == 0
        pct = entry["summary"].get("percent_covered")
        return frozenset(entry.get("missing_lines", [])), pct, run.returncode == 0


def audit(module: Path, tests: Path | tuple[Path, ...]) -> Audit:
    """Every closeable facet of one module, and how many the suite leaves silent.

    Several test files are read as one body of evidence. Reading only one meant a suite
    split across two files reported the evidence in the sibling as absent, which points a
    reader at facets that are already closed."""
    module = Path(module)
    tests = (Path(tests),) if isinstance(tests, (str, Path)) else tuple(Path(t) for t in tests)
    module_tree = ast.parse(module.read_text())
    tests_tree = ast.Module(
        body=[node for path in tests for node in ast.parse(path.read_text()).body],
        type_ignores=[])
    uncovered, coverage_percent, succeeded = _coverage(module, tests)
    asserted = asserted_calls(tests_tree)
    expecting = expected_exceptions(tests_tree)
    supplied = supplied_regions(tests_tree)

    found: list[Facet] = []
    undeclared: list[Undeclared] = []
    for fn in _functions(module_tree):
        regions, missing_types = _region_facets(fn, supplied)
        found += _branch_facets(fn, uncovered) + regions
        found += _return_facet(fn, asserted) + _exception_facets(fn, expecting)
        undeclared += missing_types

    silent = [f for f in found if f["silent"]]
    reason = ""
    if not found:
        reason = ("no closeable facet was enumerated in this module, so a silence index "
                  "would be a share of nothing")
    elif coverage_percent is None:
        reason = "coverage produced no data, so branch facets are reported unmeasured"

    return {
        "module": str(module), "tests": ", ".join(str(t) for t in tests),
        "facets": found, "undeclared": undeclared,
        "total_checkable_facets": len(found),
        "closeable_silence_sites": len(silent),
        "silence_index": round(len(silent) / len(found) * 100, 1) if found else None,
        "coverage_percent": round(coverage_percent, 1) if coverage_percent is not None else None,
        "coverage_measured": coverage_percent is not None,
        "suite_succeeded": succeeded,
        "unusable_reason": reason,
    }
