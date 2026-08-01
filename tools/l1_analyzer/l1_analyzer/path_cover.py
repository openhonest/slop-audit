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
from pathlib import Path
from typing import Any

from l1_analyzer.indicators import (
    _BODY_NODE_TYPES,
    _get_parser,
    _read_source_bytes,
    LANG_CFG,
)

_INF = 10 ** 9


# --------------------------------------------------------------------------
# Minimum path cover: fewest s->t walks that cover every edge at least once.
# --------------------------------------------------------------------------

def _add(graph: dict[Any, list[list[Any]]], u: Any, v: Any, cap: int) -> None:
    graph[u].append([v, cap, len(graph[v])])
    graph[v].append([u, 0, len(graph[u]) - 1])


def _max_flow(graph: dict[Any, list[list[Any]]], s: Any, t: Any) -> int:
    total = 0
    while True:
        parent: dict[Any, Any] = {s: None}
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


def min_path_cover(edges: list[tuple[Any, Any]], source: Any, sink: Any) -> int:
    """Fewest source->sink walks covering every edge at least once (edges may be
    reused across walks). Minimum flow with lower bound 1 per edge.

    Method: fold each lower bound into node demand, saturate demands with a
    super source/sink max flow (feasibility), then minimize the s->t flow by
    pushing back as much t->s flow as the real residual allows."""
    if not edges:
        return 0
    graph: dict[Any, list[list[Any]]] = collections.defaultdict(list)
    demand: dict[Any, int] = collections.defaultdict(int)
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


class _CFG:
    """Structured CFG builder. Straight-line statements are collapsed; only
    branches and loops create structure, which is all the edge cover depends on.
    `cur` is the current control point; None means control does not fall through
    (after return/break/continue)."""

    def __init__(self) -> None:
        self.edges: list[tuple[Any, Any]] = []
        self._n = 0

    def node(self) -> int:
        self._n += 1
        return self._n

    def edge(self, u: Any, v: Any) -> None:
        if u is not None and v is not None:
            self.edges.append((u, v))

    def build_block(self, block: Any, cur: Any, brk: Any, cont: Any) -> Any:
        for stmt in block.named_children if block is not None else []:
            if stmt.type in _SIMPLE_SKIP:
                continue
            cur = self.build_stmt(stmt, cur, brk, cont)
        return cur

    def build_stmt(self, stmt: Any, cur: Any, brk: Any, cont: Any) -> Any:
        kind = stmt.type
        if kind == "return_statement":
            self.edge(cur, _EXIT)
            return None
        if kind == "break_statement":
            self.edge(cur, brk)
            return None
        if kind == "continue_statement":
            self.edge(cur, cont)
            return None
        if kind == "if_statement":
            return self._if(stmt, cur, brk, cont)
        if kind in ("while_statement", "for_statement"):
            return self._loop(stmt, cur, brk, cont)
        if kind == "match_statement":
            return self._match(stmt, cur, brk, cont)
        if kind in ("try_statement", "with_statement"):
            body = stmt.child_by_field_name("body")
            return self.build_block(body, cur, brk, cont)
        return cur  # straight-line statement: collapsed

    def _if(self, stmt: Any, cur: Any, brk: Any, cont: Any) -> Any:
        merge = self.node()
        reached = [False]  # does any arm fall through to the merge?

        def arm(block_node: Any) -> None:
            start = self.node()
            self.edge(cur, start)
            end = self.build_block(block_node, start, brk, cont)
            if end is not None:
                self.edge(end, merge)
                reached[0] = True

        arm(stmt.child_by_field_name("consequence"))
        has_else = False
        for child in stmt.children:
            if child.type == "elif_clause":
                has_else = True
                arm(child.child_by_field_name("consequence"))
            elif child.type == "else_clause":
                has_else = True
                arm(child.child_by_field_name("body"))
        if not has_else:
            self.edge(cur, merge)  # the branch-not-taken edge
            reached[0] = True
        return merge if reached[0] else None

    def _loop(self, stmt: Any, cur: Any, brk: Any, cont: Any) -> Any:
        header = self.node()
        self.edge(cur, header)
        after = self.node()
        body = stmt.child_by_field_name("body")
        body_start = self.node()
        self.edge(header, body_start)     # enter the loop
        self.edge(header, after)          # skip / condition false
        body_end = self.build_block(body, body_start, brk=after, cont=header)
        self.edge(body_end, header)       # loop back
        return after

    def _match(self, stmt: Any, cur: Any, brk: Any, cont: Any) -> Any:
        merge = self.node()
        arms = 0
        body = stmt.child_by_field_name("body")
        for case in (body.named_children if body is not None else []):
            if case.type == "case_clause":
                arms += 1
                arm_start = self.node()
                self.edge(cur, arm_start)
                arm_body = case.child_by_field_name("consequence")
                self.edge(self.build_block(arm_body, arm_start, brk, cont), merge)
        if arms == 0:
            return cur
        self.edge(cur, merge)  # no case matched
        return merge


def function_cover(body: Any) -> int:
    """Minimum entry-to-exit walks covering every branch in one function body."""
    cfg = _CFG()
    end = cfg.build_block(body, _ENTRY, brk=_EXIT, cont=_ENTRY)
    cfg.edge(end, _EXIT)  # fall-through to exit
    if not cfg.edges:
        return 1
    return max(1, min_path_cover(cfg.edges, _ENTRY, _EXIT))


def cover_paths(repo: Path, lang: str) -> dict[str, Any]:
    """Repo-level minimum path cover: the attainable number of runs that walk
    every branch, testing each function at its own entry (per-function, summed).

    Interprocedural chaining (linking calls into one graph so runs thread through
    callees) lowers this further and is the next stage; see the module docstring.
    """
    if lang != "python":
        return {"value": "n/a", "band": "n/a", "details": f"path cover not implemented for {lang} yet (python only)"}
    cfg = LANG_CFG["python"]
    parser = _get_parser("python")
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))

    total = 0
    functions = 0
    for _path, src in files:
        root = parser.parse(src).root_node

        def walk(n: Any) -> None:
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
