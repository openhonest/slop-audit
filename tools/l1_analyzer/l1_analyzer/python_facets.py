"""Native Python facet location for the coverage-gap prove loop - the pytest counterpart
to rust_facets.

Turns a coverage run into specific, provable gaps: parse the module with tree-sitter,
enumerate each function's decision branches (if / elif / else / for / while / match case),
and cross-reference their body-entry lines against the lines coverage.py marked never
executed. An uncovered branch body is a decision no test ever reached - a proof request the
model can be asked to close.

This is slop-audit's own code, mirroring rust_facets one-for-one in shape; nothing is shared
at runtime beyond the tree-sitter parser. Unlike Rust, Python needs no concrete return type
to be proof-ready (calls are dynamic), but the parameter names and any annotations are
carried so the generated test can build arguments, and `is_method` warns when the first
parameter is self/cls so a caller knows an instance is needed.
"""

from __future__ import annotations

from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.indicators import _get_parser
from l1_analyzer.ts_nodes import slice_text as _text


class PyParam(TypedDict):
    name: str
    annotation: str | None


class PyBranch(TypedDict):
    kind: str
    line: int
    body_line: int | None


class PyFunction(TypedDict):
    name: str
    source: str
    parameters: list[PyParam]
    is_method: bool
    branches: list[PyBranch]




def _first_block(node: Node) -> Node | None:
    """A branch construct's body block, by field when available else the first `block` child."""
    for field in ("consequence", "body"):
        blk = node.child_by_field_name(field)
        if blk is not None and blk.type == "block":
            return blk
    return next((c for c in node.named_children if c.type == "block"), None)


def _first_executable_line(block: Node | None) -> int | None:
    """The 1-based line of a branch body's first real statement - the line coverage.py
    attributes the branch's execution to. Skips leading comments and bare docstrings."""
    if block is None:
        return None
    stmts = [c for c in block.named_children if c.type != "comment"]
    node = stmts[0] if stmts else block
    return node.start_point[0] + 1


def _branches(fn_body: Node) -> list[PyBranch]:
    out: list[PyBranch] = []

    def add(kind: str, construct: Node, block: Node | None) -> None:
        out.append({"kind": kind, "line": construct.start_point[0] + 1, "body_line": _first_executable_line(block)})

    def walk(n: Node) -> None:
        if n.type == "function_definition":
            return  # nested function: its branches belong to it, not to us
        if n.type == "if_statement":
            add("if", n, _first_block(n))
            alt = n.child_by_field_name("alternative")
            for clause in n.named_children if alt is None else [c for c in n.named_children if c.type in ("elif_clause", "else_clause")]:
                if clause.type == "elif_clause":
                    add("elif", clause, _first_block(clause))
                elif clause.type == "else_clause":
                    add("else", clause, _first_block(clause))
        elif n.type in ("for_statement", "while_statement"):
            add(n.type.split("_")[0], n, _first_block(n))
        elif n.type == "match_statement":
            body = n.child_by_field_name("body")
            for case in (c for c in body.named_children if c.type == "case_clause") if body else ():
                add("case", case, _first_block(case))
        for c in n.named_children:
            walk(c)

    for c in fn_body.named_children:
        walk(c)
    return out


def _parameters(src: bytes, params: Node | None) -> list[PyParam]:
    if params is None:
        return []
    out: list[PyParam] = []
    for p in params.named_children:
        if p.type == "identifier":
            out.append({"name": _text(src, p) or "_", "annotation": None})
        elif p.type in ("typed_parameter", "typed_default_parameter"):
            name = next((c for c in p.named_children if c.type == "identifier"), None)
            out.append({"name": _text(src, name) or "_", "annotation": _text(src, p.child_by_field_name("type"))})
        elif p.type == "default_parameter":
            out.append({"name": _text(src, p.child_by_field_name("name")) or "_", "annotation": None})
    return out


def module_functions(source: str) -> list[PyFunction]:
    """Every non-test function in the module (module-level or method), with its parameters,
    source text, and decision branches. Functions named test* are subjects to skip."""
    src = source.encode("utf8")
    root = _get_parser("python").parse(src).root_node
    out: list[PyFunction] = []

    def walk(n: Node) -> None:
        if n.type == "function_definition":
            name = _text(src, n.child_by_field_name("name"))
            body = n.child_by_field_name("body")
            if name is not None and body is not None and not name.startswith("test"):
                params = _parameters(src, n.child_by_field_name("parameters"))
                out.append({
                    "name": name,
                    "source": _text(src, n) or "",
                    "parameters": params,
                    "is_method": bool(params) and params[0]["name"] in ("self", "cls"),
                    "branches": _branches(body),
                })
        for c in n.named_children:
            walk(c)

    walk(root)
    return out


class CoverageGap(TypedDict):
    function: str
    kind: str
    line: int
    function_source: str
    parameters: list[PyParam]
    is_method: bool


def uncovered_gaps(functions: list[PyFunction], uncovered_lines: frozenset[int]) -> list[CoverageGap]:
    """A branch whose body-entry line was never executed is an uncovered decision, and a
    proof request. Every function with branches is proof-ready; the generated test either
    calls it or fails to, and the failure classification handles the un-constructible ones."""
    gaps: list[CoverageGap] = []
    for fn in functions:
        for b in fn["branches"]:
            if b["body_line"] is not None and b["body_line"] in uncovered_lines:
                gaps.append({
                    "function": fn["name"], "kind": b["kind"], "line": b["line"],
                    "function_source": fn["source"], "parameters": fn["parameters"], "is_method": fn["is_method"],
                })
    return gaps
