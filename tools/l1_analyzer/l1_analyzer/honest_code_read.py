"""How L1.21 reads one source, and the vocabulary its clauses read it through.

Every clause needs a source in front of it, and there are two ways to have one. A clause
ported to the shared per-language node vocabulary reads a tree-sitter tree and can be
decided for any language that vocabulary covers. A clause still written against Python's
own parser reads an `ast` module and can be decided for Python alone.

This module holds both, so a clause holds neither. It exists because eighteen clauses are
still to be ported and each of them will read from here; splitting it out is a seam rather
than a way to get a file under a line count.
"""

import ast
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.lang_spec import LANG_SPEC


# How a project declares that a function IS an edge. Clause 4's rule is that I/O belongs at
# the boundary, so a function saying it is the boundary and then doing I/O is conforming.
#
# This is not a suppression. A suppression silences a rule; a boundary decorator states
# where the project's edges are, which is the thing the rule is about, and in at least one
# adopter it is already load-bearing in another checker. The clause INFERS the boundary
# from the call graph when nothing says. A declaration is better evidence than an
# inference, so where both exist the declaration wins.
class Finding(TypedDict):
    """One site a clause found, readable at the file and line it names.

    `file` is filled in by the runner rather than by the checker, because a checker reads a
    tree and the tree does not know where it came from. It has to be there: a line number
    with no file is not a finding anyone can act on, and the repository path was flattening
    them and dropping it."""

    file: str
    clause: str
    symbol: str
    line: int
    detail: str
    instead: str
    undecided: str


def read_tree(text: str, language: str) -> dict:
    """One source, parsed by the grammar for its language, with that language's vocabulary.

    A clause reads node types from the spec rather than naming them, which is what lets one
    implementation serve every language the spec covers. Two implementations of one rule
    would be a value with two owners and nothing checking they agree.

    An unknown language is refused rather than parsed as something else: a tree read with
    the wrong grammar produces findings about a file nobody read."""
    from l1_analyzer.indicators import _get_parser

    spec = LANG_SPEC[language]
    raw = text.encode()
    return {"language": language, "spec": spec, "text": text, "raw": raw,
            "root": _get_parser(language).parse(raw).root_node}


def node_text(node: Node | None, raw: bytes) -> str:
    """The source a node covers. Absent nodes read as nothing, which is what an optional
    field yields when the grammar did not fill it."""
    return "" if node is None else raw[node.start_byte:node.end_byte].decode(errors="replace")


def walk(node: Node) -> list[Node]:
    """Every node under this one, this one included."""
    seen, stack = [], [node]
    while stack:
        current = stack.pop()
        seen.append(current)
        stack.extend(current.children)
    return seen


def _finding(clause: str, symbol: str, line: int, detail: str, instead: str,
             undecided: str) -> Finding:
    """One finding. `undecided` is required rather than defaulted: this module's own clause
    14 flagged the default, and it was right. Every caller now states whether the clause
    read the whole rule or half of it, so nobody can forget to say."""
    return {"file": "", "clause": clause, "symbol": symbol, "line": line, "detail": detail,
            "instead": instead, "undecided": undecided}


def _functions(source: dict) -> list[ast.FunctionDef]:
    return [n for n in ast.walk(source["tree"])
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _classes(source: dict) -> list[ast.ClassDef]:
    return [n for n in ast.walk(source["tree"]) if isinstance(n, ast.ClassDef)]


def _methods(node: ast.ClassDef) -> list[ast.FunctionDef]:
    return [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _called(node: ast.AST) -> set[str]:
    from l1_analyzer.facets import called_name
    return {called_name(n) for n in ast.walk(node) if isinstance(n, ast.Call)}


def _base_names(node: ast.ClassDef) -> list[str]:
    return [ast.unparse(base).split("[")[0].split(".")[-1] for base in node.bases]
