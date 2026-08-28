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


def called_spelling(call, spec: dict, raw: bytes) -> str:
    """What a call is called, reduced to the one word a vocabulary can hold.

    Four grammars spell the same idea four ways: Python writes `Mock()`, JavaScript
    `jest.fn()`, Java `Mockito.mock()` and C# `Substitute.For<IStore>()`. Taking the tail
    after the last dot and dropping any type arguments leaves `Mock`, `fn`, `mock` and
    `For`, so one list per language can name them without a branch per grammar."""
    named = call.child_by_field_name(spec["call_fn"])
    text = node_text(named, raw) if named is not None else (node_text(call, raw) or "")
    return text.split("(")[0].split("<")[0].split("::")[-1].split(".")[-1].strip()


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

# A statement declaring that a name belongs to the enclosing scope rather than to this
# function. Python needs one to rebind a module-level name; most languages need none, and
# their absence is not a missing shape but a different rule about the same write.
_SCOPE_DECLARATIONS = ("global_statement", "nonlocal_statement")

# Bases that make a class a list of signatures rather than an implementation.
_SIGNATURE_ONLY_BASES = frozenset({"Protocol", "ABC", "ABCMeta"})

# How a project says a function is one of its edges, in a decorator's name or the
# function's own. The framework's architecture format uses the name, which is the spelling
# every language has.
_BOUNDARY_MARKERS = frozenset({"boundary", "boundary_in", "boundary_out", "edge",
                               "entrypoint", "entry_point"})

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
        if test is None:
            # A ternary fields nothing in some grammars: Python's `conditional_expression`
            # names none of its three children, so asking for the condition by name got
            # nothing and every chain of ternaries read as no chain at all.
            test = next((c for c in arm.named_children
                         if c.type in spec["comparison_types"]), None)
        while test is not None and test.type == "parenthesized_expression":
            test = next(iter(test.named_children), None)
        name = _equality_subject(test, spec, raw)
        if not name:
            return []
        subjects.append(name)
    return subjects


def _chain_arms(node: Node, spec: LangSpec) -> list[Node]:
    """Every arm of one if chain, in source order, whichever way the grammar spells it.

    THREE shapes, read from structure rather than from a language name. Python hangs its
    `elif` arms off the head as children; JavaScript nests each `else if` inside the
    previous one's alternative; and a chain of ternaries in either language nests the next
    one as its own last child, with no field naming it. A reader keyed to any one of them
    sees a one-armed chain in the others and reports nothing, which is how a chain of
    ternaries went unread here.

    Found after a neighbouring project's check for if-statements reported zero against
    seventy-six standing in the code, having learned one spelling and never the other."""
    arms = [node]
    arms += [c for c in node.children if c.type == "elif_clause"]
    current = node
    while True:
        alternative = current.child_by_field_name("alternative")
        if alternative is None:
            # The ternary shape: the rest of the chain is the last child and nothing names
            # it, so there is no field to follow.
            tail = current.named_children[-1] if current.named_children else None
            if tail is not None and tail.type in spec["branch_types"]:
                arms.append(tail)
                current = tail
                continue
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


# honest-code-allow: L1.21.1 - class_nodes and function_nodes differ by which vocabulary key they read. Collapsing them means passing that key as a string at every call site, which moves a name the checker verifies into text it cannot
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


def in_a_test_module(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether this node sits inside a module of tests kept in the file it tests.

    Rust does that and nothing else here does, so its tests carry a production file's name
    and the scope module, which tells tests from production by path, cannot see them. A
    language keeping its tests elsewhere names no marker and nothing is excluded for it.

    The marker is a preceding SIBLING of the module it marks, not a parent of it, which is
    the same shape a decorator takes. Searching the text of each ancestor instead found the
    marker somewhere in the whole file and excluded the file's own code with its tests."""
    if not spec["test_module_markers"]:
        return False
    holder = node.parent
    while holder is not None:
        marking = holder.prev_named_sibling
        if marking is not None and any(marker in node_text(marking, raw)
                                       for marker in spec["test_module_markers"]):
            return True
        holder = holder.parent
    return False


def function_nodes(root: Node, spec: LangSpec) -> list[Node]:
    """Every function definition in the tree, by this language's own node types.

    Methods included: a method is a function that happens to sit in a class body, and every
    clause reading this wants both.

    A function inside a test module kept in the file it tests is NOT included. Every clause
    reading this is a production clause, and grading a repository's own tests as its code
    measures the fixtures: the first Rust file this tool read reported three of its own test
    functions as three functions of one shape, which is what a table of cases looks like."""
    raw = root.text or b""
    return [n for n in walk(root)
            if n.type in spec["func_types"] and not in_a_test_module(n, spec, raw)]


def module_level_bindings(root: Node, spec: LangSpec, raw: bytes) -> dict[str, Node]:
    """The names bound at the top of the file, and what each was bound to.

    Two shapes, because languages use two. Python binds by plain assignment and carries no
    declarator, so the assignment's own left side is the name; the rest declare a binding
    site and name it in a field. Both are read here so no clause has to know which kind its
    language is.

    Only the top level. A name bound inside a function is that function's own, and reading
    it is not reaching past a signature. The walk therefore stops at every function and
    class body: a function definition IS a top-level statement, so walking each statement
    to its leaves made every local variable in the file read as module scope, and reported
    three of this package's own locals as configuration somebody turns."""
    bound: dict[str, Node] = {}
    for statement in root.named_children:
        for node in _walk_own_scope(statement, spec):
            site = spec["binding_sites"].get(node.type)
            if site is not None:
                name = node.child_by_field_name(site)
                value = node.child_by_field_name("value")
                if name is not None:
                    bound[node_text(name, raw)] = value if value is not None else node
                continue
            if node.type in spec["assign_types"]:
                left = node.child_by_field_name(spec["assign_left"])
                right = node.child_by_field_name(spec["assign_right"])
                if left is not None and left.type == "identifier":
                    bound[node_text(left, raw)] = right if right is not None else node
    return bound


def _walk_own_scope(node: Node, spec: LangSpec) -> list[Node]:
    """Every node under this one that belongs to the same scope, this one included.

    A function or class body opens a new scope, so the walk records the definition and
    stops there rather than descending. Exempting the starting node from that rule was the
    first attempt and it defeated the whole purpose: the statement handed in IS the
    function, so the walk descended into exactly the scope it was written to stay out of."""
    seen, stack = [], [node]
    boundaries = (*spec["func_types"], *spec["class_types"], *spec["constructor_types"])
    while stack:
        current = stack.pop()
        seen.append(current)
        if current.type in boundaries:
            continue
        stack.extend(current.children)
    return seen


def names_written_in(node: Node, spec: LangSpec, raw: bytes) -> set[str]:
    """The names this function rebinds, writes by subscript, or mutates by method call.

    A declaration that the name belongs to the enclosing scope counts too. Python needs one
    to rebind and JavaScript does not, so the languages differ in whether the statement is
    present rather than in what the write means."""
    written: set[str] = set()
    for inner in walk(node):
        if inner.type in _SCOPE_DECLARATIONS:
            written |= {node_text(c, raw) for c in inner.named_children}
        if inner.type in spec["assign_types"]:
            left = inner.child_by_field_name(spec["assign_left"])
            if left is not None:
                written |= _written_name(left, spec, raw)
        if inner.type in spec["call_types"]:
            fn = inner.child_by_field_name(spec["call_fn"])
            if fn is None or fn.type not in spec["member_types"]:
                continue
            if node_text(fn, raw).split(".")[-1] not in spec["write_methods"]:
                continue
            obj = fn.child_by_field_name("object") or fn.child_by_field_name("value")
            if obj is not None and obj.type == "identifier":
                written.add(node_text(obj, raw))
    return written


def _written_name(target: Node, spec: LangSpec, raw: bytes) -> set[str]:
    """The name a write lands on, reaching through a subscript to the thing subscripted.

    `TABLE[key] = value` writes TABLE. Reading only the whole target would record the
    subscript expression, which is not a name any other function can mention."""
    if target.type == "identifier":
        return {node_text(target, raw)}
    if target.type in spec["subscript_types"]:
        inner = target.child_by_field_name("object") or target.child_by_field_name("value")
        if inner is not None and inner.type == "identifier":
            return {node_text(inner, raw)}
    return set()


def handler_body(node: Node, spec: LangSpec) -> Node | None:
    """The node holding one handler's own statements.

    The one shape these grammars disagree about. JavaScript, Java and C# name a `body`
    field; Python and Ruby do not, and their block is an ordinary child. Both are read here
    so no clause has to know which kind its language is."""
    named = node.child_by_field_name("body")
    if named is not None:
        return named
    return next((c for c in node.children if c.type in spec["handler_body_types"]), None)


def sends_failure_onward(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether anything under this node raises, throws, or re-raises.

    Ruby spells its raise as an ordinary call, so the names are read as well as the node
    types. Reading only the types would have made every Ruby handler that re-raises look
    like one that swallowed."""
    for inner in walk(node):
        if inner.type in spec["raise_types"]:
            return True
        if inner.type in spec["call_types"] and spec["raise_names"]:
            fn = inner.child_by_field_name(spec["call_fn"])
            if fn is not None and node_text(fn, raw).split(".")[-1] in spec["raise_names"]:
                return True
    return False


def is_absent_value(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether a value is indistinguishable from a successful empty result.

    Nothing, false, zero, an empty string, an empty container. A caller receiving one cannot
    tell "there were none" from "I could not look". A TRUTHY constant is a report rather
    than a stand-in: `return "could not query rustup toolchains"` names the failure and
    hands it to a caller that discloses it."""
    if node.type in spec["absent_types"]:
        return True
    if node.type in spec["container_literal_types"]:
        return not node.named_children
    if node.type in spec["literal_types"]:
        return node_text(node, raw).strip("\"'`") in ("", "0")
    return False


def names_a_table_holds(root: Node, spec: LangSpec, raw: bytes) -> set[str]:
    """Every name used as a VALUE in a map literal anywhere in this file.

    A function a table names is that table's row. An adopter classified all 71 sites clause
    1 reported in their source and 46 were the two halves of a two-entry table: the clause
    saw two functions with one shape and told them to build a table, and they were already
    its rows.

    Anywhere, not only at the top: a table built inside a function is still a table, and
    scoping this to module level would have exempted only some of them for a reason nobody
    could see from the finding."""
    named: set[str] = set()
    for node in walk(root):
        if node.type not in spec["container_literal_types"]:
            continue
        for pair in node.named_children:
            value = pair.child_by_field_name("value")
            if value is not None and value.type == "identifier":
                named.add(node_text(value, raw))
    return named


def declares_only_signatures(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether a class is a list of method signatures rather than an implementation.

    Every method in one has the shape of every other by construction, so reporting them as
    one shape asks an author to collapse the interface they were declaring. Read from the
    bases, which is where a language says it: `Protocol` and `ABC` in Python, and the same
    names anywhere else that borrows them."""
    return bool(set(base_names(node, spec, raw)) & _SIGNATURE_ONLY_BASES)


def io_calls_in(node: Node, spec: LangSpec, raw: bytes) -> set[str]:
    """The I/O this node performs, by name.

    Four readings, because a name means different things in different company. An
    unambiguous name counts on its own. A call on a module that only reaches outside counts
    whatever it is called, since a database driver's names are open-ended. A call named one
    at a time counts where most of its module is NOT I/O: `os.getenv` reads process state
    and `os.path.join` joins strings, and taking the whole of `os` doubled the findings on
    two real codebases. And an ambiguous name counts only beside a receiver that names a
    client, because `TABLE.get(key)` is a dict lookup and `requests.get(url)` fetches a
    page."""
    touched: set[str] = set()
    for inner in walk(node):
        if inner.type not in spec["call_types"]:
            continue
        called = inner.child_by_field_name(spec["call_fn"])
        if called is None:
            continue
        bare = node_text(called, raw).rsplit(".", 1)[-1].strip()
        if bare in spec["io_calls"]:
            touched.add(bare)
            continue
        if called.type not in spec["member_types"]:
            continue
        receiver = called.child_by_field_name("object") or called.child_by_field_name("value")
        if receiver is None:
            continue
        name = node_text(receiver, raw).rsplit(".", 1)[-1].strip()
        if (name in spec["io_modules"] or f"{name}.{bare}" in spec["io_dotted"]
                or (bare in spec["io_ambiguous"] and name in spec["io_receivers"])):
            touched.add(f"{name}.{bare}")
    return touched


def called_names_in(node: Node, spec: LangSpec, raw: bytes) -> set[str]:
    """Every function name this node calls, by the bare name at the call site."""
    names: set[str] = set()
    for inner in walk(node):
        if inner.type not in spec["call_types"]:
            continue
        called = inner.child_by_field_name(spec["call_fn"])
        if called is not None:
            names.add(node_text(called, raw).rsplit(".", 1)[-1].strip())
    return names


def names_handed_on(node: Node, spec: LangSpec, raw: bytes) -> set[str]:
    """Every bare name handed to a call as an argument.

    Passing a function by name reaches it, the same static fact as holding it in a dispatch
    table. `skus.map(price)` calls `price` for every element and the call graph saw only
    `map`, so a function reached only that way was reached by nothing as far as this reader
    could tell."""
    handed: set[str] = set()
    for inner in walk(node):
        if inner.type not in spec["call_types"]:
            continue
        arguments = inner.child_by_field_name(spec["call_args"])
        if arguments is None:
            continue
        handed |= {node_text(a, raw) for a in arguments.named_children
                   if a.type == "identifier"}
    return handed


def declares_a_boundary(node: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether this function says it is one of the project's own edges.

    Two spellings, because a decorator is Python's and most languages have none. The Honest
    Framework's own architecture format puts the same fact in the function's NAME, as a
    `boundary_in` or `boundary_out` prefix, and a name is something every language has.

    Read from what a decorator NAMES rather than from its text: a parametrize carrying the
    word as test data is not a declaration, which is the lesson another clause learned from
    one carrying an exit handler."""
    name = node_text(node.child_by_field_name("name"), raw) or first_name(node, raw)
    # A PREFIX, with the separator. Accepting the bare marker as well reported every
    # project's own `def boundary(fn)` as a declared edge that reaches nothing, which is
    # the marker itself rather than a function carrying it. Six of nine findings on this
    # repository were that.
    if any(name.startswith(f"{marker}_") for marker in _BOUNDARY_MARKERS):
        return True
    # The decorators of a function, which are its siblings rather than its children: Python
    # wraps both in a `decorated_definition`, so reading the function's own children found
    # none and every decorated declaration read as undeclared.
    decorated = node.parent
    around = decorated.children if decorated is not None else ()
    for child in (*node.children, *around):
        if child.type not in spec["decorator_types"]:
            continue
        called = next((n for n in walk(child) if n.type in spec["call_types"]), None)
        named = called.child_by_field_name(spec["call_fn"]) if called is not None else None
        text = node_text(named if named is not None else child, raw).lstrip("@")
        if set(text.split(".")) & _BOUNDARY_MARKERS:
            return True
    return False
