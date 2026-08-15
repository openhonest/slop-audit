"""Paths where a check publishes a property it never measured, stated only in the negative.

The shape, which was found eleven times in this package and its neighbours in two days:
**a denominator that can be zero, feeding an output that asserts a property.** L1.16 and
L1.17 divide by a file count and substitute 0.0 when there is no file. `absolute_paths`
reads `count == 0` as clean, which is the same number whether it scanned a thousand files
or none. A wrapper swallowed a scanner's non-zero exit to an empty string, and a repository
holding live credentials read Healthy off the count of nothing.

L1.15 was the fourth live instance and the headline one, and it was fixed on 2026-08-15:
it handed back 0.0 and Healthy for any repository or file under a thousand production
lines, which made it the only one of the four that fabricated over a NON-empty input as
well as an empty one. The floor is gone and the zero-line case refuses, so this rule no
longer finds it. That transition is the intended use of a checker like this one: it named
the path before anyone went looking, and its silence on that path afterwards is the
evidence, independent of the tests written to drive the change.

**Why this module can say nothing good.** Every instance above is a positive claim
manufactured from an empty input. A checker with an affirmative output can manufacture one
the same way, and would then certify itself, so this one has no band, no verdict and no
pass. Zero findings is not a clean bill; it renders as a negation carrying its own reach -
*no vacuous path found, under N rules, across M emission points, in 1 of 9 languages* - and
the numbers are the disclosure. A reader who wants to know what the silence is worth can
see how much was looked at, which is the thing every other check here has failed to say.

The poka-yoke answer. For the audited code, none: a detector prevents nothing. For this
checker, one, and it is the point. A tool with no affirmative field cannot fabricate an
affirmative value into it. `VacuityResult` has two keys and neither can hold Healthy.

## The rule

One predicate, spelled over Python's four branch forms:

> **A branch an empty input takes publishes a constant that is not a refusal.**

Deciding the branch needs no reachability analysis and no solver. Substitute zero for the
guarded quantity and evaluate the test. `total > 0` sends zero to the else. `total > 1000`
sends zero to the else as well, which is why a threshold guard is not a second rule - a
floor above zero only widens the set of inputs that reach the constant. `not findings`
sends an empty list to the body. That is the whole decision procedure.

Two constraints keep a finding a proof rather than a guess, and both were added because
the first draft produced false positives on this package:

- **The quantity must be a size.** `run.returncode == 0` compares against zero and is not
  an emptiness test: a process that ran and succeeded returns zero too. `_is_size` decides
  from how the quantity is built - a `len`, a `sum`, a counter initialised to zero, a
  collection - and not from its name.
- **The constant must be a token, not prose.** A number, a bool, or a single-word verdict
  is a property. A sentence cannot be told from a refusal mechanically, and guessing would
  put a word list at the centre of the rule, so prose fields are declined and counted in
  `fields_declined` rather than convicted or cleared.

## What it does not find

Two of the eleven share no signature with the rest, and this module does not pretend
otherwise. A parity differ that compares the intersection of two key sets reports 16/16
over a set that excludes the headline indicator: the denominator is drawn from the subject
instead of from the reference, and there is no guard and no constant anywhere in it. A
portable binary that emits fifteen rows against a reference's twenty-one is the same defect
across two artefacts. Both are a **self-referential denominator**, which is a different
shape and wants a different check; neither is a vacuous path in the sense used here.

Python only. The other eight grammars are read through tree-sitter, which reports node
types and not the emptiness semantics this rule evaluates, and a zero value in Go, a
`None` in Rust and an uninitialised read in C do not mean the same thing. Publishing over
them would put this check's own recognition set in place of the code, which is the defect
one level up. They are named in `REFUSED` and counted in the reach.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypedDict

# The eight grammars this rule declines. Named rather than skipped: "no vacuous path in
# 1 of 9 languages" is a different sentence from "no vacuous path", and the reader is
# owed the second number.
REFUSED = ("rust", "go", "java", "csharp", "c", "ruby", "javascript", "typescript")
LANGUAGES_TOTAL = 9

# Constants that decline to assert. A branch reaching one of these did not manufacture a
# measurement, it refused to make one, and that is the repair this check must not convict.
# `None` counts: a nullable field is the typed spelling of the same refusal.
REFUSALS = frozenset({
    "n/a", "na", "none", "unknown", "unmeasured", "not measured", "unread", "not run",
    "not applicable", "skipped", "no data", "indeterminate", "unavailable", "not measurable",
})
_REFUSAL_NAMES = frozenset({"NA", "UNREAD", "UNKNOWN", "UNMEASURED", "NOT_RUN", "NOT_MEASURED"})

# Calls whose result is a size, and calls that build a container. A quantity assembled
# from one of these can be driven to zero by an empty input; a status code or a flag
# cannot, and treating one as a cardinality is where a finding stops being a proof.
_SIZE_CALLS = frozenset({"len", "sum", "count"})
# Numeric coercions pass the question through: `int(totals.get("branches", 0))` is a count,
# `float(match.group(1))` is a parsed percentage and no empty input can move it.
_TRANSPARENT_CALLS = frozenset({"int", "float", "round", "abs", "min", "max"})
_CONTAINER_CALLS = frozenset({"list", "dict", "set", "tuple", "sorted", "frozenset", "Counter"})
_SIZE_METHODS = frozenset({"count", "values", "keys", "items", "split", "splitlines",
                           "findall", "finditer", "readlines", "get"})

_RULE_NAMES = ("threshold", "truthiness", "negation", "compound", "handler",
               "nested-conditional", "fall-through", "call-hop")
RULES = len(_RULE_NAMES)


class VacuousPath(TypedDict):
    """One path, and the reason it is a proof rather than an opinion. `guard` is the
    source line that selects the branch, so a reader can check the claim in one look."""
    file: str
    function: str
    field: str
    line: int
    guard: str
    constant: str
    rule: str


class Reach(TypedDict):
    """How much was looked at. This is what a zero-finding run is worth, and stating it
    is the only way an absence of findings can be read honestly."""
    rules: int
    emission_points: int
    files_read: int
    files_unparsed: int
    fields_declined: int
    languages_read: int
    languages_total: int


class VacuityResult(TypedDict):
    """Two keys, and neither can hold an affirmative value. There is deliberately no
    `band`, no `verdict` and no `value`: see the module docstring."""
    findings: list[VacuousPath]
    reach: Reach


# --- is the quantity a size ----------------------------------------------------------

def _assignments(scope: ast.AST, name: str) -> list[ast.expr]:
    """Every expression bound to `name` inside `scope`, plain and augmented."""
    out: list[ast.expr] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign) and name in _bound_names(node) or isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == name and node.value is not None:
            out.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == name and node.value is not None:
            out.append(node.value)          # `findings: list[Finding] = []` builds a size
    return out




_SIZE_EXPR: dict[type, str] = {
    ast.ListComp: "container", ast.SetComp: "container", ast.DictComp: "container",
    ast.GeneratorExp: "container", ast.List: "container", ast.Dict: "container",
    ast.Set: "container", ast.Tuple: "container",
}


def _is_size(expr: ast.expr, scope: ast.AST, depth: int) -> bool:
    """The quantity can be driven to zero by an empty input.

    Decided from construction, never from the name: a counter initialised to zero and
    incremented, a `len`, a `sum`, a comprehension, a container literal. An attribute
    read with no local definition is not a size, which is what keeps `run.returncode == 0`
    out of the finding list - it compares against zero and means the opposite thing."""
    if depth > 3:
        return False
    if type(expr) in _SIZE_EXPR:
        return True
    if isinstance(expr, ast.Call):
        func = expr.func
        if isinstance(func, ast.Name):
            if func.id in _TRANSPARENT_CALLS:
                return any(_is_size(a, scope, depth + 1) for a in expr.args)
            return func.id in (_SIZE_CALLS | _CONTAINER_CALLS)
        return isinstance(func, ast.Attribute) and func.attr in _SIZE_METHODS
    if isinstance(expr, ast.Constant):
        return isinstance(expr.value, (int, float)) and not isinstance(expr.value, bool)
    if isinstance(expr, ast.BinOp):
        # A literal operand does not make the expression a size. `0` alone is a counter
        # being initialised, but the `100` in `covered / total * 100` is a scale factor,
        # and counting it made every arithmetic expression in the tree look like a count.
        return any(_is_size(operand, scope, depth + 1)
                   for operand in (expr.left, expr.right)
                   if not isinstance(operand, ast.Constant))
    if isinstance(expr, ast.UnaryOp):
        # `parsed += not root.has_error` is the counter idiom for "how many succeeded".
        return isinstance(expr.op, (ast.Not, ast.USub, ast.UAdd))
    if isinstance(expr, ast.Subscript):
        # Indexing a size gives a size: a tally read as `counts["promiscuous"]` is one.
        # Indexing a module table is NOT - `cfg["type_escape_patterns"]` asks whether the
        # language has a rule, which no empty repository can change. Reading every
        # subscript as a size made a config guard look like a refusal and cut a live
        # finding out of the list.
        return _is_size(expr.value, scope, depth + 1)
    if isinstance(expr, ast.Name):
        defs = _assignments(scope, expr.id)
        if defs:
            # ANY, not ALL. A counter is `n = 0` and then `n += <something>`, and demanding
            # every binding be a size read the increment as proof it was not a count.
            return any(_is_size(d, scope, depth + 1) for d in defs)
        # No local definition: a parameter is whatever the caller passed and may be an
        # empty tally - but only if the body treats it as one. `higher_is_better` is a
        # flag, and reading it as a size made `band()` itself look like it published a
        # constant from nothing, which put a finding on every indicator that calls it.
        return expr.id in _parameters(scope) and _used_as_quantity(expr.id, scope)
    return False


def _used_as_quantity(name: str, scope: ast.AST) -> bool:
    """The body indexes, iterates, measures or does arithmetic with this name.

    That is the evidence an empty input can drive it to zero. A name the body only ever
    tests for truth is a flag - `higher_is_better` reads exactly like a tally otherwise,
    and treating it as one put a finding on every indicator that calls `band()`. The
    arithmetic arm matters just as much: a count handed in as a parameter and divided by
    is a size even though the body never indexes it."""
    for node in ast.walk(scope):
        if isinstance(node, ast.BinOp) and name in (_referenced_names(node.left)
                                                    | _referenced_names(node.right)):
            return True
        if isinstance(node, ast.Subscript) and name in _referenced_names(node.value):
            return True
        if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)) \
                and name in _referenced_names(node.iter):
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in (_SIZE_CALLS | _CONTAINER_CALLS) \
                    and any(name in _referenced_names(a) for a in node.args):
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr in _SIZE_METHODS \
                    and name in _referenced_names(node.func.value):
                return True
    return False


def _parameters(scope: ast.AST) -> frozenset[str]:
    args = getattr(scope, "args", None)
    if args is None:
        return frozenset()
    every = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    every += [a for a in (args.vararg, args.kwarg) if a is not None]
    return frozenset(a.arg for a in every)


# --- which branch an empty input takes -----------------------------------------------

_COMPARISONS = {
    ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
    ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
    ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
}
BODY, ORELSE = "body", "orelse"
_FLIP = {BODY: ORELSE, ORELSE: BODY}


def _threshold_branch(test: ast.Compare, scope: ast.AST) -> str | None:
    """A size compared against a numeric literal. Substitute zero and evaluate - that
    settles the branch for `> 0`, `== 0`, `< 1` and `> 1000` with one arithmetic step
    and no case analysis."""
    if len(test.ops) != 1:
        return None
    operator = _COMPARISONS.get(type(test.ops[0]))
    if operator is None:
        return None
    for quantity, literal, reversed_ in ((test.left, test.comparators[0], False),
                                         (test.comparators[0], test.left, True)):
        if not (isinstance(literal, ast.Constant)
                and isinstance(literal.value, (int, float))
                and not isinstance(literal.value, bool)):
            continue
        if not _is_size(quantity, scope, 0):
            return None
        holds = operator(literal.value, 0) if reversed_ else operator(0, literal.value)
        return BODY if holds else ORELSE
    return None


def refusal_branch(test: ast.expr) -> str | None:
    """The branch taken when the UPSTREAM refused, or None.

    `surface["verdict"] == UNREAD` asks whether the input measured anything. It decides
    nothing about a value - a repository can be empty on either side of it - so it never
    selects a constant. It does decide a cut: a check that refuses here has passed the
    input's refusal through instead of inventing a reading, and reading this test as
    undecidable reported that repair as though it had never happened."""
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], (ast.Eq, ast.NotEq))):
        return None
    if not any(_is_refusal_constant(c) for c in [test.left] + list(test.comparators)):
        return None
    return BODY if isinstance(test.ops[0], ast.Eq) else ORELSE


def empty_branch(test: ast.expr, scope: ast.AST) -> str | None:
    """`body` or `orelse`: the branch an empty or zero input takes, or None when the test
    is not decided by emptiness. An undecided test is not a finding and not a clearance;
    the caller descends into both arms and lets an inner guard decide."""
    if isinstance(test, ast.Compare):
        return _threshold_branch(test, scope)
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        inner = empty_branch(test.operand, scope)
        return None if inner is None else _FLIP[inner]
    if isinstance(test, ast.BoolOp):
        sides = [empty_branch(v, scope) for v in test.values]
        if any(s is None for s in sides):
            return None
        # `and` takes the body only if every arm does; `or` if any arm does. Reading a
        # compound guard as undecidable reported every check that refuses on two
        # conditions at once as though it had never been repaired.
        satisfied = all(s == BODY for s in sides) if isinstance(test.op, ast.And) \
            else any(s == BODY for s in sides)
        return BODY if satisfied else ORELSE
    return ORELSE if _is_size(test, scope, 0) else None


# --- is the published constant a refusal, a property, or prose ------------------------

def _is_refusal_constant(node: ast.expr) -> bool:
    """The value declines to assert. `None` and `False` count: a nullable field and a
    `measured: False` flag are the typed and the boolean spellings of the same refusal,
    and this package uses both. `True` does not count - it asserts."""
    if isinstance(node, ast.Constant):
        if node.value is None or node.value is False:
            return True
        if not isinstance(node.value, str):
            return False
        word = node.value.strip().lower()
        # The `error` family by morphology rather than by listing the words. A token that
        # names a failure to complete is a refusal whatever the module chose to call it,
        # and enumerating them one at a time is the habit this whole check exists against.
        return word in REFUSALS or word == "error" or word.endswith(("_error", " error"))
    if isinstance(node, ast.Attribute):
        return node.attr.upper() in _REFUSAL_NAMES      # `thread_surface.UNREAD`
    return isinstance(node, ast.Name) and node.id.upper() in _REFUSAL_NAMES


def _is_prose(node: ast.expr) -> bool:
    """A sentence, which this check declines to judge. A refusal and a fabricated clean
    are both spelled as English here, and separating them mechanically would need a word
    list - the enumeration this rule exists to avoid."""
    if isinstance(node, ast.JoinedStr):
        return True                                     # an f-string is a sentence
    return isinstance(node, ast.Constant) and isinstance(node.value, str) \
        and " " in node.value.strip()


def _is_property_constant(node: ast.expr, tokens: frozenset[str]) -> bool:
    """A number or a single-word verdict token: something a reader takes as a measurement.

    `tokens` are the module's own constants bound to a scalar - `CLEAN = "clean"` is a
    verdict a reader will act on, while a constant bound to a table of specifications is
    a choice of layout and asserts nothing about the code. Reading every upper-case name
    as a verdict convicted the picking of a spec table."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float, str))
    if isinstance(node, ast.Name):
        return node.id in tokens
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _is_property_constant(node.operand, tokens)
    return False


def _verdict_tokens(tree: ast.Module) -> frozenset[str]:
    """Module constants bound to a scalar literal. These are the verdict words a check
    publishes; a constant bound to a list or a dict is a table, not a verdict."""
    out = set()
    for stmt in tree.body:
        if not (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant)):
            continue
        if isinstance(stmt.value.value, (str, int, float)) and not isinstance(stmt.value.value, bool):
            out.update(n for n in _bound_names(stmt) if n.isupper() and len(n) > 1)
    return frozenset(out)


class _Path(TypedDict):
    """What one pass over a function body collects.

    `vacuous` maps a name to the statement that bound it to a constant an empty input
    reaches, and to the rule that decided it. `declined` counts prose fields the check
    refused to judge; they belong in the published reach, not in the finding list."""
    vacuous: dict[str, tuple[ast.AST, str, str, frozenset[str]]]
    guard_roots: frozenset[str]
    tokens: frozenset[str]
    origins: dict[str, frozenset[str]]
    declined: int
    emissions: int
    findings: list[VacuousPath]


class _Context(TypedDict):
    """The read-only surroundings of a walk: where the source came from, and what the
    module's other functions were found to hand back."""
    path: Path
    source: list[str]
    function: str
    scope: ast.AST
    vacuous_calls: dict[str, str]
    refusing_calls: frozenset[str]
    returned_names: frozenset[str]


def _bound_names(node: ast.Assign) -> list[str]:
    return [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)]


def _writes_a_container(node: ast.Assign) -> bool:
    """`counts[key] = ...` fills a tally; it does not bind a constant to `counts`. Reading
    the two as the same thing convicted an empty tally, which asserts nothing."""
    return any(isinstance(t, (ast.Subscript, ast.Attribute)) for t in node.targets)


def _guard_rule(test: ast.expr) -> str:
    """Which of the named rules decided this branch. Published with every finding so a
    reader can see which spelling of the one predicate fired."""
    if isinstance(test, ast.BoolOp):
        return "compound"
    if isinstance(test, ast.UnaryOp):
        return "negation"
    return "threshold" if isinstance(test, ast.Compare) else "truthiness"


def derivation_map(scope: ast.AST) -> dict[str, frozenset[str]]:
    """Every locally bound name mapped to the names it is derived from, transitively.

    Built once per function in a single pass. The first version asked the question per
    name and rewalked the whole body each time, which turned one file into a minute."""
    direct: dict[str, set[str]] = {}

    def note(name: str, source: ast.AST) -> None:
        direct.setdefault(name, set()).update(_referenced_names(source))

    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for name in _bound_names(node):
                note(name, node.value)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and node.value is not None:
            if isinstance(node.target, ast.Name):
                note(node.target.id, node.value)
            for name in _referenced_names(node.target):
                note(name, node.value)              # `counts[k] += 1` binds through counts
        elif isinstance(node, ast.For):
            for name in _referenced_names(node.target):
                note(name, node.iter)
            # A tally filled inside the loop is a fact about what the loop walked.
            for inner in ast.walk(node):
                targets = (inner.targets if isinstance(inner, ast.Assign)
                           else [inner.target] if isinstance(inner, (ast.AugAssign, ast.AnnAssign))
                           else [])
                for tgt in targets:
                    if isinstance(tgt, (ast.Subscript, ast.Attribute)):
                        for name in _referenced_names(tgt):
                            note(name, node.iter)
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                        and inner.func.attr in _FILL_METHODS:
                    for name in _referenced_names(inner.func.value):
                        note(name, node.iter)

    for _ in range(3):                              # transitive closure, capped
        for name, sources in direct.items():
            direct[name] = sources | {s for src in list(sources) for s in direct.get(src, ())}
    return {name: frozenset(sources) for name, sources in direct.items()}


_FILL_METHODS = frozenset({"append", "extend", "add", "update", "insert", "setdefault"})


def _roots(expr: ast.expr, origins: dict[str, frozenset[str]]) -> frozenset[str]:
    """The names a quantity is built from, followed through local assignments.

    This is what keys the cut. A check that refuses when the language has no scanner has
    NOT repaired a later division by a finding count, and closing the whole function on
    the first refusal lost exactly that finding. Two guards close each other only when
    they are about the same quantity."""
    names = _referenced_names(expr)
    return frozenset(names | {s for n in names for s in origins.get(n, ())})


def _vacuous_constant(expr: ast.expr, guarded: bool, scope: ast.AST,
                      path: _Path) -> tuple[ast.expr, str, frozenset[str]] | None:
    """The constant an empty input publishes through `expr`, with the rule that decided
    it, or None. Descends through nested conditionals: an outer test the rule cannot
    decide can hide an inner one that it can, and refusing to descend lost the guard."""
    if isinstance(expr, ast.IfExp):
        side = empty_branch(expr.test, scope)
        arms = [expr.body if side == BODY else expr.orelse] if side else [expr.body, expr.orelse]
        for arm in arms:
            hit = _vacuous_constant(arm, guarded or side is not None, scope, path)
            if hit is not None:
                return (hit[0], _guard_rule(expr.test) if side else "nested-conditional",
                        hit[2] | (_roots(expr.test, path["origins"]) if side else frozenset()))
        return None
    if not guarded or _is_refusal_constant(expr):
        return None
    if _is_prose(expr):
        path["declined"] += 1
        return None
    if not _is_property_constant(expr, path["tokens"]):
        return None
    return (expr, "threshold", path["guard_roots"])


def _is_refusal_dict(node: ast.expr, scope: ast.AST) -> bool:
    """A published dict that declines to assert: at least one field refuses, and no field
    holds a property constant. The second half is what stops `{"value": 0.0, "band": "n/a"}`
    from reading as a refusal - it publishes a measured-looking zero beside the refusal,
    which is the half-repair this check has to keep convicting. A field carrying a name
    rather than a constant is the reason string, and neither asserts nor refuses."""
    if isinstance(node, ast.DictComp):
        # A panel refused row by row: `{f"L1.{i}": {...n/a...} for i in range(1, 9)}`.
        return _is_refusal_dict(node.value, scope)
    if not (isinstance(node, ast.Dict) and node.values):
        return False
    if any(isinstance(v, ast.Constant) and (v.value is False or v.value is None)
           for v in node.values):
        # An explicit did-not-measure flag settles it. The sentinel fields beside it -
        # a -1 exit status, an empty output - are the shape of the refusal, not separate
        # claims, and convicting them reported the repair as the defect.
        return True
    # Otherwise every field has to be a refusal, the reason for it, or an empty shell.
    # "At least one refusal and no obvious measurement" was too loose: a full result dict
    # carrying `"band": "n/a"` beside a fabricated fraction read as a refusal whole, and
    # the fraction escaped. A refusal dict measures NOTHING.
    return any(_is_refusal_constant(v) for v in node.values) and all(
        _is_refusal_constant(v) or _is_prose(v) or _is_reason(v, scope) for v in node.values)


def _is_reason(node: ast.expr, scope: ast.AST) -> bool:
    """The explanatory payload of a refusal: the argument it was handed, or an empty
    shell standing in for the result it did not produce."""
    if isinstance(node, ast.Name):
        return node.id in _parameters(scope)
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.Tuple)):
        return True
    if isinstance(node, ast.Constant) and node.value in (0, "", -1):
        # A sentinel beside an explicit refusal - zero files parsed, a -1 exit - discloses
        # that nothing was measured. This is the one place the check trades a miss for a
        # false positive on purpose: a half-repair that publishes 0.0 beside `band: n/a`
        # reads as a refusal here and is NOT reported.
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _is_reason(node.operand, scope)
    # A refusal spells its detail with a helper as often as with a literal. The
    # refusal marker elsewhere in the dict is the evidence; this field is the reason.
    return isinstance(node, ast.Call)


def _refuses(stmts: list[ast.stmt], refusing_calls: frozenset[str], scope: ast.AST) -> bool:
    """The branch declines to publish and returns. A path ending in a refusal is not a
    vacuous path, and everything below it is unreachable on an empty input - which is
    exactly the repair this check must not convict. A dict of nothing but refusals and
    prose counts, because that is how every fixed check in this package spells it."""
    if not stmts or not isinstance(stmts[-1], ast.Return):
        return False
    value = stmts[-1].value
    if value is None or _is_refusal_constant(value):
        return True
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return value.func.id in refusing_calls
    return _is_refusal_dict(value, scope)


def _terminates(stmts: list[ast.stmt]) -> bool:
    return bool(stmts) and isinstance(stmts[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break))


def _record(ctx: _Context, path: _Path, field: str, at: ast.AST, rule: str,
            constant: str) -> None:
    line = getattr(at, "lineno", 1)
    source = ctx["source"]
    path["findings"].append({
        "file": str(ctx["path"]), "function": ctx["function"], "field": field, "line": line,
        "guard": source[line - 1].strip()[:140] if 0 < line <= len(source) else "",
        "constant": constant, "rule": rule})


def _emit(node: ast.Dict, guarded: bool, refused: frozenset[str], ctx: _Context,
          path: _Path) -> None:
    """One published dict: count its string-keyed fields as emission points, and record
    the ones an empty input reaches with a constant. `cut` means an earlier guard already
    sent the empty input away with a refusal, so nothing below it is reachable when empty."""
    refusing = _is_refusal_dict(node, ctx["scope"])
    for key, value in zip(node.keys, node.values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        path["emissions"] += 1
        # A dict that carries its own did-not-measure flag is a refusal whole. Judging its
        # fields one at a time convicted the sentinel exit status and the empty output
        # that ARE the refusal.
        if refusing or _is_prose(value):
            continue
        carried = sorted(_referenced_names(value) & set(path["vacuous"]))
        hopped = sorted(_called_names(value) & set(ctx["vacuous_calls"]))
        if carried:
            origin, rule, constant, roots = path["vacuous"][carried[0]]
            if not (roots & refused):
                _record(ctx, path, key.value, origin, rule, constant)
            continue
        if hopped and not refused:
            _record(ctx, path, key.value, value, ctx["vacuous_calls"][hopped[0]], "")
            continue
        inline = _vacuous_constant(value, guarded, ctx["scope"], path)
        if inline is not None and not (inline[2] & refused):
            _record(ctx, path, key.value, value, inline[1], ast.unparse(inline[0]))


def _published_dict(stmt: ast.stmt, ctx: _Context) -> ast.Dict | None:
    """The dict this statement publishes, if any. A panel entry assigned as
    `results["L1.17"] = {...}` is published exactly as a returned literal is."""
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
        return stmt.value
    if (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Dict)
            and (_writes_a_container(stmt) or set(_bound_names(stmt)) & ctx["returned_names"])):
        return stmt.value
    return None


def _walk_body(stmts: list[ast.stmt], guarded: bool, refused: frozenset[str],
               ctx: _Context, path: _Path) -> frozenset[str]:
    """Collect the vacuous names and the published fields an empty input reaches.

    Two flags carry the whole analysis. `guarded` says the statements being read are on
    the branch an empty input takes; it is set by an emptiness guard, by an exception
    handler, and by falling past a not-empty guard that returns - the guard-chain form,
    where a function refuses twice and then publishes an affirmative token with no `else`
    in sight. `cut` says an empty input was already sent away with a refusal, so nothing
    below can be reached with one. Without `cut` this check convicted every repair as
    loudly as every defect, which would have made the finding list useless."""
    scope = ctx["scope"]
    for stmt in stmts:
        published = _published_dict(stmt, ctx)
        if published is not None:
            _emit(published, guarded, refused, ctx, path)
        if isinstance(stmt, ast.Assign):
            writes = _writes_a_container(stmt)
            hit = _vacuous_constant(stmt.value, guarded, scope, path)
            if hit is not None and not writes and not (hit[2] & refused):
                for name in _bound_names(stmt):
                    path["vacuous"].setdefault(name, (stmt, hit[1], ast.unparse(hit[0]), hit[2]))
            hopped = sorted(_called_names(stmt.value) & set(ctx["vacuous_calls"]))
            if hopped and not writes and not refused:
                for name in _bound_names(stmt):     # one call hop, carrying the callee's rule
                    path["vacuous"].setdefault(
                        name, (stmt, ctx["vacuous_calls"][hopped[0]], "", frozenset()))
            carried = sorted(_referenced_names(stmt.value) & set(path["vacuous"]))
            if carried and not writes:
                origin = path["vacuous"][carried[0]]  # a count over a vacuous value is vacuous
                for name in _bound_names(stmt):
                    path["vacuous"].setdefault(name, origin)
        elif isinstance(stmt, ast.Return) and stmt.value is not None \
                and not isinstance(stmt.value, ast.Dict):
            hit = _vacuous_constant(stmt.value, guarded, scope, path)
            if hit is not None and not (hit[2] & refused):
                _record(ctx, path, "<return>", stmt, hit[1], ast.unparse(hit[0]))
        elif isinstance(stmt, ast.If):
            side = empty_branch(stmt.test, scope)
            # The cut reads a refusal guard as well as an emptiness guard; `guarded` reads
            # only the emptiness guard, because a refusal comparison says nothing about
            # whether the input was empty.
            closes = side if side is not None else refusal_branch(stmt.test)
            body_refuses = _refuses(stmt.body, ctx["refusing_calls"], scope)
            else_refuses = _refuses(stmt.orelse, ctx["refusing_calls"], scope)
            quantity = _roots(stmt.test, path["origins"])
            outer_roots = path["guard_roots"]
            path["guard_roots"] = outer_roots | (quantity if side == BODY else frozenset())
            # Entering the arm an empty input does NOT take proves the quantity is
            # non-zero there, so `guarded` is cleared rather than inherited. Inheriting it
            # attributed the finding to the first branch of a verdict chain instead of to
            # the final else, which is the only arm an empty input reaches.
            _walk_body(stmt.body, True if side == BODY else (False if side == ORELSE else guarded),
                       refused | (quantity if closes == ORELSE and else_refuses else frozenset()),
                       ctx, path)
            path["guard_roots"] = outer_roots | (quantity if side == ORELSE else frozenset())
            _walk_body(stmt.orelse, True if side == ORELSE else (False if side == BODY else guarded),
                       refused | (quantity if closes == BODY and body_refuses else frozenset()),
                       ctx, path)
            path["guard_roots"] = outer_roots
            if (closes == BODY and body_refuses) or (closes == ORELSE and else_refuses):
                refused = refused | quantity     # refused about THIS quantity: that path closed
            elif side == ORELSE and not stmt.orelse and _terminates(stmt.body):
                guarded = True                       # fall-through: the rest is the empty path
        elif isinstance(stmt, ast.Try):
            # A refusal inside the block still closes the path after it: control leaves the
            # function either way, and losing that at a `with` boundary reported three
            # coverage harnesses as unrepaired.
            refused = _walk_body(stmt.body, guarded, refused, ctx, path)
            for handler in stmt.handlers:            # the handler IS the did-not-measure branch
                _walk_body(handler.body, True, refused, ctx, path)
            refused = _walk_body(stmt.orelse, guarded, refused, ctx, path)
            refused = _walk_body(stmt.finalbody, guarded, refused, ctx, path)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            refused = _walk_body(stmt.body, guarded, refused, ctx, path)
        elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
            _walk_body(stmt.body, guarded, refused, ctx, path)
    return refused


# --- module-level assembly -------------------------------------------------------------

def _called_names(node: ast.AST) -> set[str]:
    return {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Name)}


def _referenced_names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _returned_names(fn: ast.AST) -> frozenset[str]:
    return frozenset(n.value.id for n in ast.walk(fn)
                     if isinstance(n, ast.Return) and isinstance(n.value, ast.Name))


def _functions(tree: ast.Module) -> list[ast.AST]:
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _blank_path(tokens: frozenset[str], scope: ast.AST) -> _Path:
    """The derivation map is built here, once per function, and read from `_Path` after.
    It used to sit in a module-level cache, which is hidden state the package's own L1.18
    counts against it - and did, the first time this module was added to the tree."""
    return {"vacuous": {}, "tokens": tokens, "origins": derivation_map(scope),
            "guard_roots": frozenset(), "declined": 0, "emissions": 0, "findings": []}


def _context(fn: ast.AST, file_path: Path, source: list[str],
             vacuous_calls: dict[str, str], refusing_calls: frozenset[str]) -> _Context:
    return {"path": file_path, "source": source, "function": getattr(fn, "name", "<module>"),
            "scope": fn, "vacuous_calls": vacuous_calls, "refusing_calls": refusing_calls,
            "returned_names": _returned_names(fn)}


def _classify_helpers(fns: list[ast.AST], file_path: Path, source: list[str],
                      tokens: frozenset[str]) -> tuple[dict[str, str], frozenset[str]]:
    """Which helpers hand a vacuous constant back, and which hand a refusal back.

    Both are read from the callee's body, so neither depends on what the helper is
    called: a refusal helper earns its meaning by returning refusals, not by being named
    `_na`. The vacuous set carries the rule that fired inside the callee, so a finding at
    the call site still names the exception handler that produced the empty string."""
    vacuous: dict[str, str] = {}
    refusing: set[str] = set()
    for fn in fns:
        name = getattr(fn, "name", "")
        ctx = _context(fn, file_path, source, {}, frozenset())
        path = _blank_path(tokens, fn)
        _walk_body(getattr(fn, "body", []), False, frozenset(), ctx, path)
        returns = [f for f in path["findings"] if f["field"] == "<return>"]
        if returns:
            vacuous[name] = "handler" if _returns_from_a_handler(fn) else returns[0]["rule"]
        if _refuses_outright(fn):
            refusing.add(name)
    return vacuous, frozenset(refusing)


def _returns_from_a_handler(fn: ast.AST) -> bool:
    return any(isinstance(s, ast.Return) for h in ast.walk(fn)
               if isinstance(h, ast.ExceptHandler) for s in ast.walk(h))


def _refuses_outright(fn: ast.AST) -> bool:
    for stmt in ast.walk(fn):
        if not (isinstance(stmt, ast.Return) and stmt.value is not None):
            continue
        if _is_refusal_constant(stmt.value) or _is_refusal_dict(stmt.value, fn):
            return True
    return False


def scan_function(fn: ast.AST, file_path: Path, source: list[str],
                  vacuous_calls: dict[str, str], refusing_calls: frozenset[str],
                  tokens: frozenset[str], counters: dict[str, int]) -> list[VacuousPath]:
    """Vacuous paths published by one function. `counters` accumulates the reach."""
    ctx = _context(fn, file_path, source, vacuous_calls, refusing_calls)
    path = _blank_path(tokens, fn)
    _walk_body(getattr(fn, "body", []), False, frozenset(), ctx, path)
    counters["emission_points"] += path["emissions"]
    counters["fields_declined"] += path["declined"]
    return [f for f in path["findings"] if f["field"] != "<return>"]


def scan_module(tree: ast.Module, file_path: Path, source: list[str]) -> list[VacuousPath]:
    """Vacuous paths in one parsed module. Pure: no I/O, so a caller can hand it a
    snippet and read the answer without putting a file on disk."""
    return _scan_counting(tree, file_path, source,
                          {"emission_points": 0, "fields_declined": 0}, frozenset())


def _scan_counting(tree: ast.Module, file_path: Path, source: list[str],
                   counters: dict[str, int], imported_refusals: frozenset[str]) -> list[VacuousPath]:
    fns = _functions(tree)
    tokens = _verdict_tokens(tree)
    vacuous_calls, refusing_calls = _classify_helpers(fns, file_path, source, tokens)
    # A refusal helper defined in one module and imported into another is the same helper.
    # Reading it per-module reported eight coverage harnesses as unrepaired because their
    # `_na` lives next door.
    refusing_calls = refusing_calls | imported_refusals
    found: list[VacuousPath] = []
    seen: set[tuple[str, int, str]] = set()
    for fn in fns:
        for finding in scan_function(fn, file_path, source, vacuous_calls,
                                     refusing_calls, tokens, counters):
            key = (finding["function"], finding["line"], finding["field"])
            if key not in seen:
                seen.add(key)
                found.append(finding)
    return found


_IGNORED_PARTS = frozenset({".venv", "__pycache__", ".git", "build", "dist", "target",
                            "node_modules", ".mypy_cache", ".pytest_cache", ".ruff_cache"})


def _python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if not (_IGNORED_PARTS & set(p.parts)))



def check(root: Path) -> VacuityResult:
    """Every vacuous path under `root`, with the reach that says what the answer is worth.

    There is no band and no verdict in the return type, and that is not an omission. See
    the module docstring: an affirmative field is a field that can hold a fabricated
    affirmative value, and this check would then be its own first finding."""
    counters = {"emission_points": 0, "fields_declined": 0}
    findings: list[VacuousPath] = []
    parsed: list[tuple[Path, ast.Module, list[str]]] = []
    unparsed = 0
    for path in _python_files(root):
        try:
            text = path.read_text(encoding="utf8")
            tree = ast.parse(text)
        except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
            unparsed += 1
            continue
        parsed.append((path, tree, text.splitlines()))
    # First pass: every refusal helper in the tree, because a check imports its refusal
    # from wherever it is defined and the cut has to follow it there.
    refusals = frozenset(getattr(fn, "name", "") for _p, tree, _s in parsed
                         for fn in _functions(tree) if _refuses_outright(fn))
    for path, tree, lines in parsed:
        findings.extend(_scan_counting(tree, path, lines, counters, refusals))
    read = len(parsed)
    reach: Reach = {"rules": RULES, "emission_points": counters["emission_points"],
                    "files_read": read, "files_unparsed": unparsed,
                    "fields_declined": counters["fields_declined"],
                    "languages_read": 1, "languages_total": LANGUAGES_TOTAL}
    return {"findings": findings, "reach": reach}


def render(result: VacuityResult) -> str:
    """The report. Zero findings is a negation carrying its reach, never a pass, and a
    finding is a withdrawal - what can no longer be relied on - never a fault."""
    reach = result["reach"]
    scope = (f"under {reach['rules']} rules, across {reach['emission_points']} emission "
             f"points in {reach['files_read']} files, "
             f"in {reach['languages_read']} of {reach['languages_total']} languages")
    declined = (f"\n{reach['fields_declined']} prose field(s) were declined rather than "
                f"judged; {reach['files_unparsed']} file(s) could not be parsed.")
    if not result["findings"]:
        return (f"no vacuous path found, {scope}."
                f"\nThis is the reach of the search, not a statement about the code.{declined}")
    withdrawal = ("Each is a withdrawal: the named output cannot be relied on when the input "
                  "is empty, and the guard below is the path.")
    lines = [f"{len(result['findings'])} vacuous path(s) found, {scope}.", withdrawal, ""]
    for f in sorted(result["findings"], key=lambda d: (d["file"], d["line"])):
        lines.append(f"  {Path(f['file']).name}:{f['line']} {f['function']}() "
                     f"-> '{f['field']}' cannot be relied on when the input is empty "
                     f"[{f['rule']}]")
        lines.append(f"      {f['guard']}")
    lines.append(declined.strip())
    return "\n".join(lines)
