"""Native Rust facet location for the coverage-gap prove loop.

Turns a coverage run into specific, provable gaps: parse the module with tree-sitter,
enumerate each function's decision branches (if / else / match arm / while / for), and
cross-reference their body-entry lines against the lines cargo-llvm-cov marked
uncovered. An uncovered branch body is a decision no test ever reached - a proof
request the model can be asked to close.

This is slop-audit's own code. Umbra's rust_structural was the reference for the AST
shapes (function_item, if_expression, match_arm, the body-entry span); nothing is
imported from it.
"""

from __future__ import annotations

from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.indicators import _get_parser

_BRANCH_BODY = {
    "if_expression": ("consequence",),
    "while_expression": ("body",),
    "for_expression": ("body",),
}


def _cfg_inner(attr_text: str) -> str | None:
    """The predicate inside a `#[cfg(...)]` attribute, balancing nested parentheses, or
    None for any other attribute. `#[cfg(not(target_os = "linux"))]` -> `not(target_os = "linux")`."""
    start = attr_text.find("cfg(")
    if start < 0:
        return None
    depth, i = 0, start + 3
    for j in range(start + 3, len(attr_text)):
        if attr_text[j] == "(":
            depth += 1
        elif attr_text[j] == ")":
            depth -= 1
            if depth == 0:
                return attr_text[i + 1:j]
    return None


def _enclosing_cfg(src: bytes, node: Node) -> str | None:
    """Every `#[cfg(...)]` predicate that gates this node - its own preceding attributes and
    those of each enclosing item - combined with `all(...)`, since all must hold for the host
    to compile it. None when nothing gates it. This is how a host-dead branch is spotted
    before a proof is ever spent on it."""
    preds: list[str] = []
    cur: Node | None = node
    while cur is not None:
        prev = cur.prev_sibling
        while prev is not None and prev.type in ("attribute_item", "line_comment", "block_comment"):
            if prev.type == "attribute_item":
                inner = _cfg_inner(_text(src, prev) or "")
                if inner is not None:
                    preds.append(inner.strip())
            prev = prev.prev_sibling
        cur = cur.parent
    if not preds:
        return None
    return preds[0] if len(preds) == 1 else "all(" + ", ".join(preds) + ")"


class RustParam(TypedDict):
    name: str
    type: str | None


class RustBranch(TypedDict):
    kind: str
    line: int          # 1-based source line of the branch construct
    body_line: int | None   # 1-based line of the branch body's first executable statement
    cfg: str | None    # the `#[cfg(...)]` predicate gating this branch, or None


class RustFunction(TypedDict):
    name: str
    source: str
    parameters: list[RustParam]
    return_type: str | None
    branches: list[RustBranch]


def _text(src: bytes, node: Node | None) -> str | None:
    return None if node is None else src[node.start_byte:node.end_byte].decode("utf8", errors="ignore")


def _is_test_scoped(src: bytes, node: Node) -> bool:
    """A function under #[cfg(test)] or annotated #[test] is test code, not a subject."""
    cur = node
    while cur is not None:
        prev = cur.prev_sibling
        while prev is not None and prev.type in ("attribute_item", "line_comment", "block_comment"):
            if prev.type == "attribute_item" and ("test" in (_text(src, prev) or "")):
                return True
            prev = prev.prev_sibling
        cur = cur.parent
    return False


def _first_executable_line(body: Node | None) -> int | None:
    """The 1-based line of a branch body's first real statement - the line llvm-cov
    attributes the branch's execution to. For a block, its first named child; the block
    itself otherwise."""
    if body is None:
        return None
    node = body
    if body.type == "block":
        stmts = [c for c in body.named_children if c.type not in ("line_comment", "block_comment")]
        node = stmts[0] if stmts else body
    return node.start_point[0] + 1


def _branches(src: bytes, fn_body: Node) -> list[RustBranch]:
    out: list[RustBranch] = []

    def walk(n: Node) -> None:
        if n.type == "function_item":
            return  # nested fn: its branches belong to it, not to us
        if n.type == "if_expression":
            cons = n.child_by_field_name("consequence")
            out.append({"kind": "if", "line": n.start_point[0] + 1,
                        "body_line": _first_executable_line(cons), "cfg": _enclosing_cfg(src, n)})
            alt = n.child_by_field_name("alternative")
            if alt is not None:
                # else / else-if: the alternative is a block or another if_expression
                blk = next((c for c in alt.named_children if c.type == "block"), None)
                out.append({"kind": "else", "line": alt.start_point[0] + 1,
                            "body_line": _first_executable_line(blk), "cfg": _enclosing_cfg(src, n)})
        elif n.type == "match_expression":
            body = n.child_by_field_name("body")
            for arm in (c for c in body.named_children if c.type == "match_arm") if body else ():
                out.append({"kind": "match_arm", "line": arm.start_point[0] + 1,
                            "body_line": _first_executable_line(arm.child_by_field_name("value")),
                            "cfg": _enclosing_cfg(src, arm)})
        elif n.type in _BRANCH_BODY:
            body = n.child_by_field_name(_BRANCH_BODY[n.type][0])
            out.append({"kind": n.type.split("_")[0], "line": n.start_point[0] + 1,
                        "body_line": _first_executable_line(body), "cfg": _enclosing_cfg(src, n)})
        for c in n.named_children:
            walk(c)

    for c in fn_body.named_children:
        walk(c)
    return out


def _parameters(src: bytes, params: Node | None) -> list[RustParam]:
    nodes = [] if params is None else [c for c in params.named_children if c.type == "parameter"]
    return [{"name": _text(src, p.child_by_field_name("pattern")) or "_", "type": _text(src, p.child_by_field_name("type"))} for p in nodes]


def module_functions(source: str) -> list[RustFunction]:
    """Every non-test free function in the module, with its parameters, return type,
    source text, and decision branches."""
    src = source.encode("utf8")
    root = _get_parser("rust").parse(src).root_node
    out: list[RustFunction] = []

    def walk(n: Node) -> None:
        if n.type == "function_item" and not _is_test_scoped(src, n):
            name = _text(src, n.child_by_field_name("name"))
            body = n.child_by_field_name("body")
            if name is not None and body is not None:
                out.append({
                    "name": name,
                    "source": _text(src, n) or "",
                    "parameters": _parameters(src, n.child_by_field_name("parameters")),
                    "return_type": _text(src, n.child_by_field_name("return_type")),
                    "branches": _branches(src, body),
                })
        for c in n.named_children:
            walk(c)

    walk(root)
    return out


class CoverageGap(TypedDict):
    function: str
    kind: str
    line: int
    cfg: str | None
    function_source: str
    parameters: list[RustParam]
    return_type: str | None


def uncovered_gaps(functions: list[RustFunction], uncovered_lines: frozenset[int]) -> list[CoverageGap]:
    """A branch whose body-entry line was never executed is an uncovered decision. Only
    functions with a concrete return type and fully-typed parameters are proof-ready: the
    renderer needs the types to build a calling test."""
    gaps: list[CoverageGap] = []
    for fn in functions:
        if fn["return_type"] is None or any(p["type"] is None for p in fn["parameters"]):
            continue
        for b in fn["branches"]:
            if b["body_line"] is not None and b["body_line"] in uncovered_lines:
                gaps.append({
                    "function": fn["name"], "kind": b["kind"], "line": b["line"], "cfg": b["cfg"],
                    "function_source": fn["source"], "parameters": fn["parameters"], "return_type": fn["return_type"],
                })
    return gaps
