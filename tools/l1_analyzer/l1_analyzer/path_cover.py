"""
Minimum end-to-end path cover (the "Eulerian walk" count).

The question this answers: how many runs from an entry point, each following
real control flow to an exit, do you need so that together they traverse every
branch at least once? Not the number of distinct paths (that multiplies, the
2**decisions figure), but the minimum number of walks that cover every edge. For
well-behaved code this is a small, attainable number.

The number is computed by minimum flow with a lower bound of 1 on every edge:
each edge must be walked at least once, and we minimize how many entry-to-exit
walks that takes. If a function's control-flow graph is Eulerian the answer is 1.

This module is intraprocedural for now (per function, then summed). Linking calls
into one interprocedural graph is the next stage; see the whole-program note.
"""

from __future__ import annotations

import collections
import itertools
from collections.abc import Iterator
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.indicators import (
    _BODY_NODE_TYPES,
    LANG_CFG,
    _get_parser,
    _read_source_bytes,
)
from l1_analyzer.scope import PRODUCTION

# A control-flow node: an integer basic-block id (from the counter), or the "entry"/
# "exit" string sentinel. Control that does not fall through is None.
CfgNode = int | str

_INF = 10 ** 9


# --------------------------------------------------------------------------
# Minimum path cover: fewest s->t walks that cover every edge at least once.
# --------------------------------------------------------------------------

def _add(graph: dict[CfgNode, list[list[CfgNode]]], u: CfgNode | None, v: CfgNode | None, cap: int) -> None:
    graph[u].append([v, cap, len(graph[v])])
    graph[v].append([u, 0, len(graph[u]) - 1])


def _max_flow(graph: dict[CfgNode, list[list[CfgNode]]], s: CfgNode, t: CfgNode) -> int:
    total = 0
    while True:
        parent: dict[CfgNode, tuple[CfgNode, int] | None] = {s: None}
        q = collections.deque([s])
        while q:
            u = q.popleft()
            if u == t:
                break
            for i, (v, cap, _rev) in enumerate(graph[u]):
                if cap > 0 and v not in parent:
                    parent[v] = (u, i)
                    q.append(v)
        if t not in parent:
            return total
        # bottleneck along the found path
        bottleneck = _INF
        v = t
        while parent[v] is not None:
            u, i = parent[v]
            bottleneck = min(bottleneck, graph[u][i][1])
            v = u
        v = t
        while parent[v] is not None:
            u, i = parent[v]
            graph[u][i][1] -= bottleneck
            back = graph[u][i][2]
            graph[v][back][1] += bottleneck
            v = u
        total += bottleneck


def min_path_cover(edges: list[tuple[CfgNode, CfgNode]], source: CfgNode, sink: CfgNode) -> int:
    """Fewest source->sink walks covering every edge at least once (edges may be
    reused across walks). Minimum flow with lower bound 1 per edge.

    Method: fold each lower bound into node demand, saturate demands with a
    super source/sink max flow (feasibility), then minimize the s->t flow by
    pushing back as much t->s flow as the real residual allows."""
    if not edges:
        return 0
    graph: dict[CfgNode, list[list[CfgNode]]] = collections.defaultdict(list)
    demand: dict[CfgNode, int] = collections.defaultdict(int)
    for u, v in edges:
        _add(graph, u, v, _INF)  # upper INF; lower bound 1 handled via demand
        demand[v] += 1
        demand[u] -= 1
    _add(graph, sink, source, _INF)          # circulation edge E carries the flow value
    e_owner, e_idx = sink, len(graph[sink]) - 1

    super_src, super_sink = ("__S__", "__T__")
    for node, d in demand.items():
        if d > 0:
            _add(graph, super_src, node, d)
        elif d < 0:
            _add(graph, node, super_sink, -d)
    _max_flow(graph, super_src, super_sink)  # saturate lower bounds (feasibility)

    flow_on_e = _INF - graph[e_owner][e_idx][1]
    # Disable the artificial edges (super nodes and E) so the pushback runs only
    # over the real residual; then minimize by pushing t->s.
    for owner in (super_src, super_sink):
        for entry in graph[owner]:
            v, _cap, rev = entry
            entry[1] = 0
            graph[v][rev][1] = 0
    e_rev = graph[e_owner][e_idx][2]
    graph[e_owner][e_idx][1] = 0
    graph[source][e_rev][1] = 0

    pushed = _max_flow(graph, sink, source)
    return flow_on_e - pushed


# --------------------------------------------------------------------------
# Control-flow graph, built from a tree-sitter function body.
# --------------------------------------------------------------------------

_ENTRY, _EXIT = "entry", "exit"
_SIMPLE_SKIP = frozenset({"comment", "newline", ":", "pass_statement"})


# The CFG is built by threading two accumulators explicitly: `edges` (the edge
# list) and `counter` (a fresh-node-id source, itertools.count). Every builder
# takes them as parameters and binds no instance or module state, so the analyzer
# stays clean under its own L1.18 (a stateful builder class would flag as mutable
# instance state). Straight-line statements are collapsed; only branches and loops
# create structure. `cur` is the current control point; None means control does
# not fall through (after return/break/continue).

def _cfg_edge(edges: list[tuple[CfgNode, CfgNode]], u: CfgNode | None, v: CfgNode | None) -> None:
    if u is not None and v is not None:
        edges.append((u, v))


def _build_block(edges: list, counter: Iterator[int], block: Node | None, cur: CfgNode | None, brk: CfgNode | None, cont: CfgNode | None) -> CfgNode | None:
    for stmt in block.named_children if block is not None else []:
        if stmt.type in _SIMPLE_SKIP:
            continue
        cur = _build_stmt(edges, counter, stmt, cur, brk, cont)
    return cur


def _build_stmt(edges: list, counter: Iterator[int], stmt: Node, cur: CfgNode | None, brk: CfgNode | None, cont: CfgNode | None) -> CfgNode | None:
    kind = stmt.type
    if kind == "return_statement":
        _cfg_edge(edges, cur, _EXIT)
        return None
    if kind == "break_statement":
        _cfg_edge(edges, cur, brk)
        return None
    if kind == "continue_statement":
        _cfg_edge(edges, cur, cont)
        return None
    if kind == "if_statement":
        return _cfg_if(edges, counter, stmt, cur, brk, cont)
    if kind in ("while_statement", "for_statement"):
        return _cfg_loop(edges, counter, stmt, cur, brk, cont)
    if kind == "match_statement":
        return _cfg_match(edges, counter, stmt, cur, brk, cont)
    if kind in ("try_statement", "with_statement"):
        body = stmt.child_by_field_name("body")
        return _build_block(edges, counter, body, cur, brk, cont)
    return cur  # straight-line statement: collapsed


def _cfg_if(edges: list, counter: Iterator[int], stmt: Node, cur: CfgNode | None, brk: CfgNode | None, cont: CfgNode | None) -> CfgNode | None:
    merge = next(counter)

    def arm(block_node: Node | None) -> bool:
        start = next(counter)
        _cfg_edge(edges, cur, start)
        end = _build_block(edges, counter, block_node, start, brk, cont)
        if end is not None:
            _cfg_edge(edges, end, merge)
            return True
        return False

    reached = arm(stmt.child_by_field_name("consequence"))
    has_else = False
    for child in stmt.children:
        if child.type == "elif_clause":
            has_else = True
            reached = arm(child.child_by_field_name("consequence")) or reached
        elif child.type == "else_clause":
            has_else = True
            reached = arm(child.child_by_field_name("body")) or reached
    if not has_else:
        _cfg_edge(edges, cur, merge)  # the branch-not-taken edge
        reached = True
    return merge if reached else None


def _cfg_loop(edges: list, counter: Iterator[int], stmt: Node, cur: CfgNode | None, brk: CfgNode | None, cont: CfgNode | None) -> CfgNode | None:
    header = next(counter)
    _cfg_edge(edges, cur, header)
    after = next(counter)
    body = stmt.child_by_field_name("body")
    body_start = next(counter)
    _cfg_edge(edges, header, body_start)     # enter the loop
    _cfg_edge(edges, header, after)          # skip / condition false
    body_end = _build_block(edges, counter, body, body_start, brk=after, cont=header)
    _cfg_edge(edges, body_end, header)       # loop back
    return after


def _cfg_match(edges: list, counter: Iterator[int], stmt: Node, cur: CfgNode | None, brk: CfgNode | None, cont: CfgNode | None) -> CfgNode | None:
    merge = next(counter)
    arms = 0
    body = stmt.child_by_field_name("body")
    for case in (body.named_children if body is not None else []):
        if case.type == "case_clause":
            arms += 1
            arm_start = next(counter)
            _cfg_edge(edges, cur, arm_start)
            arm_body = case.child_by_field_name("consequence")
            _cfg_edge(edges, _build_block(edges, counter, arm_body, arm_start, brk, cont), merge)
    if arms == 0:
        return cur
    _cfg_edge(edges, cur, merge)  # no case matched
    return merge


def function_cover(body: Node) -> int:
    """Minimum entry-to-exit walks covering every branch in one function body."""
    edges: list[tuple[CfgNode, CfgNode]] = []
    counter = itertools.count(1)
    end = _build_block(edges, counter, body, _ENTRY, brk=_EXIT, cont=_ENTRY)
    _cfg_edge(edges, end, _EXIT)  # fall-through to exit
    if not edges:
        return 1
    return max(1, min_path_cover(edges, _ENTRY, _EXIT))


class PathCover(TypedDict, total=False):
    """The repo-level path-cover result. total=False because the n/a branch carries only
    value, band and details; the measured branch adds the function count."""
    value: int | str
    band: str
    functions: int
    details: str


def cover_paths(repo: Path, lang: str) -> PathCover:
    """Repo-level minimum path cover: the attainable number of runs that walk
    every branch, testing each function at its own entry (per-function, summed).

    Interprocedural chaining (linking calls into one graph so runs thread through
    callees) lowers this further and is the next stage; see the module docstring.
    """
    if lang != "python":
        return {"value": "n/a", "band": "n/a", "details": f"path cover not implemented for {lang} yet (python only)"}
    cfg = LANG_CFG["python"]
    parser = _get_parser("python")
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION)

    total = 0
    functions = 0
    for _path, src in files:
        root = parser.parse(src).root_node

        def walk(n: Node) -> None:
            nonlocal total, functions
            if n.type in cfg["function_types"]:
                body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
                if body is not None:
                    functions += 1
                    total += function_cover(body)
            for c in n.children:
                walk(c)

        walk(root)

    return {
        "value": total,
        "band": "n/a",
        "functions": functions,
        "details": (
            f"{total:,} end-to-end runs cover every branch across {functions:,} functions "
            "(per-function edge cover, python)"
        ),
    }
