"""Is this quantity one an empty input can drive to zero?

Split out of vacuity.py when that file crossed the god-file threshold this package gates
on. It is one question, asked six ways, and it is the question the whole check turns on: a
constant published behind a guard is a finding only when the guard's quantity can actually
reach zero.

The rules here are the ones a defect keeps arriving through. Each carries the measurement
that put it there, because the boundary between a size and a flag is where this check goes
wrong in both directions: too loose and every indicator that calls `band()` is convicted,
too tight and a real fabrication walks past.
"""

from __future__ import annotations

import ast

_TRANSPARENT_CALLS = frozenset({"int", "float", "round", "abs", "min", "max"})
_CONTAINER_CALLS = frozenset({"list", "dict", "set", "tuple", "sorted", "frozenset", "Counter"})
_SIZE_METHODS = frozenset({"count", "values", "keys", "items", "split", "splitlines",
                           "findall", "finditer", "readlines", "get"})
_SIZE_CALLS = frozenset({"len", "sum", "count"})
# Numeric coercions pass the question through: `int(totals.get("branches", 0))` is a count,
# `float(match.group(1))` is a parsed percentage and no empty input can move it.

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
        # ANY, not ALL. A counter is `n = 0` and then `n += <something>`, and demanding
        # every binding be a size read the increment as proof it was not a count.
        if any(_is_size(d, scope, depth + 1) for d in _assignments(scope, expr.id)):
            return True
        # THE MISSING LINK, closed 2026-08-19. A local whose definitions prove nothing used
        # to stop here at False, while a PARAMETER fell through to `_used_as_quantity` and
        # was judged by what the body does with it. So `files, _ = _read_text_files(...)`
        # was not a size, `if not files: raise` cleared nothing, and every constant below
        # that raise was convicted. Which side of a function boundary a quantity arrived on
        # decided whether its guard counted.
        #
        # Closing it was measured and declined once, on 2026-08-18: it cleared two findings
        # and added seven, in coverage_prove, python_coverage_prove and dead_code, where an
        # honest refusal dict carrying `"attempted": 0` beside its prose began reading as a
        # fabricated affirmative. Those seven were the refusal rule's fault, not this one's.
        # `_is_refusal_dict` now acquits a dict that SHOWS the result it did not produce and
        # says why, so the trade is gone: measured again on 2026-08-19, this clears the two
        # and adds nothing.
        #
        # A flag is still not a size. `higher_is_better` reads exactly like a tally to any
        # rule that goes by name, and treating it as one put a finding on every indicator
        # that calls `band()`; `_used_as_quantity` is what tells them apart, by asking
        # whether the body indexes, iterates, measures or does arithmetic with it.
        return _used_as_quantity(expr.id, scope)
    return False


def _read_as_a_number(subscript: ast.Subscript, scope: ast.AST) -> bool:
    """This subscript's RESULT is measured, not merely tested for truth.

    `counts["bad"] > 0` is a tally read: an empty input drives it to zero and the
    comparison decides a verdict. `facts["ruby_metaprogramming"]` is a flag read: it asks
    whether the repository has a property, which no empty input can change. Both are the
    same syntax, so the key cannot tell them apart, and excluding literal keys to try was
    measured on 2026-08-19 and blinded a real detection.

    What tells them apart is the same flag-versus-tally question this module already asks
    of parameters, one level down: does the body do arithmetic with it or compare it to a
    number, or does it only ask whether it is truthy?"""
    target = ast.dump(subscript)
    for node in ast.walk(scope):
        if isinstance(node, ast.BinOp) and target in (ast.dump(node.left), ast.dump(node.right)):
            return True
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(ast.dump(o) == target for o in operands) and any(
                    isinstance(o, ast.Constant) and isinstance(o.value, (int, float))
                    and not isinstance(o.value, bool) for o in operands):
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in _SIZE_CALLS \
                and any(ast.dump(a) == target for a in node.args):
            return True
    return False


def _is_the_iterable(name: str, iterated: ast.expr) -> bool:
    """The name IS what the loop walks, rather than merely appearing inside the expression.

    `for d in COLLECTORS[lang](root, src, relpath, facts)` does not walk `facts`; it walks
    whatever that call returns, and `facts` is one of four arguments. Counting any name
    referenced in the iterable made a dict of flags read as a size, which made the guard
    above it look like an emptiness guard and marked the rest of the function as the empty
    path. Five findings in one function came from that.

    A wrapper that preserves its argument is different: `sorted(items)` and `enumerate(xs)`
    walk what they were handed, so an argument to one of those is the iterable. An unknown
    call is opaque and no argument of it is."""
    if isinstance(iterated, ast.Name):
        return iterated.id == name
    if isinstance(iterated, (ast.Subscript, ast.Attribute)):
        return _is_the_iterable(name, iterated.value)
    if isinstance(iterated, ast.Tuple):
        return any(_is_the_iterable(name, e) for e in iterated.elts)
    if isinstance(iterated, ast.Call):
        if isinstance(iterated.func, ast.Name) and iterated.func.id in (_SIZE_CALLS | _CONTAINER_CALLS):
            return any(_is_the_iterable(name, a) for a in iterated.args)
        if isinstance(iterated.func, ast.Attribute) and iterated.func.attr in _SIZE_METHODS:
            return _is_the_iterable(name, iterated.func.value)
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
        if isinstance(node, ast.Subscript) and name in _referenced_names(node.value) \
                and _read_as_a_number(node, scope):
            return True
        if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)) \
                and _is_the_iterable(name, node.iter):
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


def _bound_names(node: ast.Assign) -> list[str]:
    return [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)]


def _referenced_names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
