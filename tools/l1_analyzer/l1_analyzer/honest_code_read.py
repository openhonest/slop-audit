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

from l1_analyzer.lang_spec import COMPARISON_OPS, LANG_SPEC, LangSpec


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
    # What kept this finding off the violation list, or the empty string when nothing did.
    # "declaration" means a boundary decorator; an allow comment is recorded separately,
    # because the two are different acts: a comment carries a written reason and a
    # declaration carries an architectural claim.
    withheld_by: str
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
    return {"file": "", "withheld_by": "", "clause": clause, "symbol": symbol, "line": line,
            "detail": detail, "instead": instead, "undecided": undecided}


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


# ---------------------------------------------------------------------------
# Reading one language's shapes through its own vocabulary
#
# These take a node and a spec and name nothing about any language. They live here
# rather than beside the clauses because every clause ported to the shared vocabulary
# adds more of them, so this is the seam the growth actually follows.
# ---------------------------------------------------------------------------

# An option passed where the bases go. Not a base, in any language that allows one.
_OPTION_TYPES = ("keyword_argument", "named_argument", "assignment_expression")

_BASE_HOLDERS = ("argument_list", "class_heritage", "superclass", "extends_clause",
                 "type_parameters", "implements_clause")


def is_chain_arm(node: Node) -> bool:
    """Whether this branch is the `else if` of another, rather than the head of a chain.

    Without it a three-armed chain reports three times, once from each arm it is also the
    head of."""
    parent = node.parent
    while parent is not None and parent.type in ("else_clause", "elif_clause"):
        parent = parent.parent
    return parent is not None and parent.type == node.type


def chain_subjects(node: Node, spec: LangSpec, raw: bytes) -> list[str]:
    """The name each arm of one if chain compares against a literal.

    A bounds check, a null guard and ordinary boolean logic contribute nothing: the rule
    says so itself, and a clause firing on every function with a condition teaches a reader
    to ignore the number."""
    subjects: list[str] = []
    for arm in _chain_arms(node, spec):
        test = arm.child_by_field_name(spec["branch_cond"])
        while test is not None and test.type == "parenthesized_expression":
            test = next(iter(test.named_children), None)
        name = _equality_subject(test, spec, raw)
        if not name:
            return []
        subjects.append(name)
    return subjects


def _chain_arms(node: Node, spec: LangSpec) -> list[Node]:
    """Every arm of one if chain, in source order, whichever way the grammar spells it.

    The two shapes are read from structure rather than from a language name. Python hangs
    its `elif` arms off the head as children; JavaScript nests each `else if` inside the
    previous one's alternative. A reader keyed to either shape alone sees a one-armed chain
    in the other language and reports nothing."""
    arms = [node]
    arms += [c for c in node.children if c.type == "elif_clause"]
    current = node
    while True:
        alternative = current.child_by_field_name("alternative")
        if alternative is None:
            return arms
        nested = alternative if alternative.type in spec["branch_types"] else next(
            (c for c in alternative.named_children if c.type in spec["branch_types"]), None)
        if nested is None:
            return arms
        arms.append(nested)
        current = nested


def _equality_subject(test: Node | None, spec: LangSpec, raw: bytes) -> str:
    """The name on one side of an equality test whose other side is a literal."""
    if test is None or test.type not in spec["comparison_types"]:
        return ""
    children = [c for c in test.children if c.is_named or c.type in COMPARISON_OPS]
    operators = [node_text(c, raw) for c in test.children if not c.is_named]
    if not any(op in ("==", "===", "is") for op in operators):
        return ""
    named = [c for c in children if c.is_named]
    if len(named) != 2:
        return ""
    left, right = named
    if right.type in spec["literal_types"] and left.type == "identifier":
        return node_text(left, raw)
    if left.type in spec["literal_types"] and right.type == "identifier":
        return node_text(right, raw)
    return ""


def base_names(node: Node, spec: LangSpec, raw: bytes) -> list[str]:
    """The classes one definition inherits from, however the grammar spells it.

    Python parenthesises its bases as an argument list and JavaScript names a heritage
    clause, so the holder is found by node type and neither language appears in the rule.

    A base defined in another module is only a name here, which is the half this clause
    cannot decide and says so.

    An option passed beside the bases is not one of them. Python puts `total=False` in the
    same argument list as `TypedDict`, and reading every identifier under the holder made
    this package's own vocabulary look like it inherited from something called `total`."""
    names: list[str] = []
    for child in node.children:
        if child.type not in _BASE_HOLDERS:
            continue
        for base in child.named_children:
            if base.type in _OPTION_TYPES:
                continue
            for inner in walk(base):
                if inner.type not in ("identifier", "type_identifier", "member_expression",
                                      "attribute"):
                    continue
                text = node_text(inner, raw).split(".")[-1].strip()
                if text and text not in names:
                    names.append(text)
    return names


def first_name(node: Node, raw: bytes) -> str:
    """The class's own name, for a grammar that does not field it."""
    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return node_text(child, raw)
    return ""


def class_nodes(root: Node, spec: LangSpec) -> list[Node]:
    """Every class definition in the tree, by this language's own node types."""
    return [n for n in walk(root) if n.type in spec["class_types"]]


def method_nodes(node: Node, spec: LangSpec) -> list[Node]:
    """The definitions directly in a class body.

    Directly, not by walking: a function defined inside a method is not a method, and
    counting it as one would make a class holding one closure look like a class of two.
    Java and C# spell the constructor as its own node type, so those types are collected
    here alongside the ordinary ones rather than left for the caller to remember."""
    body = node.child_by_field_name("body")
    if body is None:
        return []
    wanted = (*spec["func_types"], *spec["constructor_types"])
    return [child for child in body.named_children if child.type in wanted]


def is_constructor(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether a definition is the one that runs when the class is instantiated.

    Two languages name it and two spell it as a node type. Both are read here so no clause
    has to know which kind its language is."""
    if node.type in spec["constructor_types"]:
        return True
    return node_text(node.child_by_field_name("name"), raw) in spec["constructor_names"]


def reaches_receiver(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether anything inside reads `self` or `this` at all."""
    return any(_receiver_of(n, spec, raw) is not None for n in walk(node))


def writes_receiver(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether anything inside assigns to the receiver, or calls a method on it.

    Either one is work a free function taking the data could not do, which is what
    separates an object from a record. Reading `self.x` is not: the value could have been
    a parameter."""
    for n in walk(node):
        if n.type in spec["assign_types"]:
            left = n.child_by_field_name(spec["assign_left"])
            if left is not None and _receiver_of(left, spec, raw) is not None:
                return True
        if n.type in spec["call_types"]:
            fn = n.child_by_field_name(spec["call_fn"])
            if fn is not None and _receiver_of(fn, spec, raw) is not None:
                return True
    return False


def _receiver_of(node: Node, spec: LangSpec, raw: bytes) -> Node | None:
    """The member access whose object is this language's receiver, or nothing."""
    if node.type not in spec["member_types"]:
        return None
    obj = node.child_by_field_name("object") or node.child_by_field_name("value")
    if obj is None or node_text(obj, raw) not in spec["this_idents"]:
        return None
    return node
