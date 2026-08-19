"""Per-language definition collectors for L1.12 (see dead_code.py for the indicator).

One function per language, registered in `COLLECTORS`. Each takes a parsed tree and
returns every definition the detector will reason about, already carrying the verdict
the LANGUAGE forces regardless of how the repository references it:

- `candidate`   - the reference scan decides whether this is dead.
- `undecidable` - the language or the framework can reach this name by a route a
                  syntactic scan cannot follow (reflection, dynamic registration,
                  linkage, publication). Named, counted, never called dead.
- `excluded`    - a runtime entry point (`main`, `init`, `TestXxx`, a dunder). Not a
                  finding and not an unknown; the runtime references it by definition.

The split exists because the failure mode of a native dead-code pass is not missing a
dead symbol, it is reporting a framework entry point as dead. That is the tool
reporting its own blind spot as a defect in someone's code. Every case a syntactic
scan cannot settle is therefore routed to `undecidable` and disclosed, and the ratio
is published as a lower bound.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.ts_nodes import text as _text

CANDIDATE = "candidate"
UNDECIDABLE = "undecidable"
EXCLUDED = "excluded"


class Definition(TypedDict):
    """One named definition and everything the classifier needs to judge it."""
    name: str
    kind: str
    line: int          # 1-based first line
    end_line: int      # 1-based last line
    start_byte: int
    end_byte: int
    status: str        # CANDIDATE / UNDECIDABLE / EXCLUDED
    reason: str


class RepoFacts(TypedDict):
    """Repository-level facts a single file cannot answer for itself."""
    rust_is_library: bool
    js_entry_files: frozenset[str]
    ruby_metaprogramming: str




def _named_child_of_type(node: Node, types: tuple[str, ...]) -> Node | None:
    for child in node.named_children:
        if child.type in types:
            return child
    return None


def _mk(name_node: Node, item: Node, kind: str, status: str, reason: str) -> Definition:
    return {
        "name": _text(name_node),
        "kind": kind,
        "line": item.start_point[0] + 1,
        "end_line": item.end_point[0] + 1,
        "start_byte": item.start_byte,
        "end_byte": item.end_byte,
        "status": status,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

_DUNDER = re.compile(r"^__\w+__$")

# Names a Python runner calls by convention, never by an import. `test_x` and `TestX` are
# collected by pytest and unittest; `pytest_x` is a plugin hook pytest looks up by name;
# the setup/teardown pair is the xunit-style fixture protocol. Caught on umbra, where
# `pytest_configure` and `pytest_sessionfinish` are the whole point of a shipped plugin
# module and this pass called them dead.
_PYTHON_RUNNER_NAMES = re.compile(r"^(?:test_|pytest_|Test[A-Z_]|setup_(?:module|function)$|teardown_(?:module|function)$)")


def _python_all_exports(root: Node) -> frozenset[str]:
    """The names listed in a module-level `__all__`, which are the module's declared
    public surface. A name a package publishes is reachable from outside the tree."""
    for stmt in root.named_children:
        assign = stmt if stmt.type == "assignment" else _named_child_of_type(stmt, ("assignment",))
        if assign is None or _text(assign.child_by_field_name("left")) != "__all__":
            continue
        right = assign.child_by_field_name("right")
        if right is None:
            continue
        return frozenset(
            _text(s).strip("\"'")
            for s in right.named_children
            if "string" in s.type
        )
    return frozenset()


def _python(root: Node, src: bytes, relpath: str, facts: RepoFacts) -> list[Definition]:
    exports = _python_all_exports(root)
    out: list[Definition] = []

    def add(name_node: Node | None, item: Node, kind: str, decorated: bool) -> None:
        if name_node is None:
            return
        name = _text(name_node)
        if _DUNDER.match(name):
            out.append(_mk(name_node, item, kind, EXCLUDED, "dunder name bound by the interpreter"))
        elif _PYTHON_RUNNER_NAMES.match(name):
            out.append(_mk(name_node, item, kind, EXCLUDED, "test-runner or pytest plugin hook name"))
        elif decorated:
            out.append(_mk(name_node, item, kind, UNDECIDABLE,
                           "decorated (a decorator can register the name with a framework)"))
        elif name in exports:
            out.append(_mk(name_node, item, kind, UNDECIDABLE, "exported via __all__"))
        else:
            out.append(_mk(name_node, item, kind, CANDIDATE, ""))

    for stmt in root.named_children:
        node, decorated = stmt, False
        if stmt.type == "decorated_definition":
            inner = stmt.child_by_field_name("definition")
            if inner is None:
                continue
            node, decorated = inner, True
        if node.type == "function_definition":
            add(node.child_by_field_name("name"), node, "function", decorated)
        elif node.type == "class_definition":
            add(node.child_by_field_name("name"), node, "class", decorated)
        elif node.type == "expression_statement":
            assign = _named_child_of_type(node, ("assignment",))
            if assign is not None:
                left = assign.child_by_field_name("left")
                if left is not None and left.type == "identifier":
                    add(left, node, "constant", False)
    return out


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------

_RUST_ITEMS = {
    "function_item": "function", "struct_item": "type", "enum_item": "type",
    "union_item": "type", "trait_item": "trait", "type_item": "type",
    "const_item": "constant", "static_item": "constant",
}
_RUST_NAME_TYPES = ("identifier", "type_identifier")


def _rust_attribute_before(item: Node) -> str:
    """The attribute attached to `item`, read from the preceding sibling. A Rust
    attribute is a sibling of the item it decorates, not a parent, so `#[derive]`,
    `#[no_mangle]` and a proc-macro attribute are only visible by looking back."""
    prev = item.prev_named_sibling
    while prev is not None and prev.type in ("line_comment", "block_comment"):
        prev = prev.prev_named_sibling
    return _text(prev) if prev is not None and prev.type == "attribute_item" else ""


def _rust(root: Node, src: bytes, relpath: str, facts: RepoFacts) -> list[Definition]:
    out: list[Definition] = []

    def visit(container: Node) -> None:
        for item in container.named_children:
            if item.type == "mod_item":
                body = item.child_by_field_name("body")
                if body is not None and "cfg(test)" not in _rust_attribute_before(item).replace(" ", ""):
                    visit(body)
                continue
            kind = _RUST_ITEMS.get(item.type)
            if kind is None:
                continue
            name_node = _named_child_of_type(item, _RUST_NAME_TYPES)
            if name_node is None:
                continue
            name = _text(name_node)
            attribute = _rust_attribute_before(item)
            is_pub = _named_child_of_type(item, ("visibility_modifier",)) is not None
            if name == "main":
                out.append(_mk(name_node, item, kind, EXCLUDED, "crate entry point"))
            elif attribute:
                out.append(_mk(name_node, item, kind, UNDECIDABLE,
                               f"carries the attribute {attribute.splitlines()[0]}"))
            elif is_pub and facts["rust_is_library"]:
                out.append(_mk(name_node, item, kind, UNDECIDABLE,
                               "public item of a library crate (may be used by a dependent crate)"))
            else:
                out.append(_mk(name_node, item, kind, CANDIDATE, ""))

    visit(root)
    return out


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

_GO_ENTRY = re.compile(r"^(Test|Benchmark|Example|Fuzz)[A-Z_]")


def _go_package(root: Node) -> str:
    clause = _named_child_of_type(root, ("package_clause",))
    return _text(_named_child_of_type(clause, ("package_identifier",))) if clause else ""


def _go(root: Node, src: bytes, relpath: str, facts: RepoFacts) -> list[Definition]:
    package = _go_package(root)
    out: list[Definition] = []

    def add(name_node: Node | None, item: Node, kind: str) -> None:
        if name_node is None:
            return
        name = _text(name_node)
        if name in ("main", "init", "_") or _GO_ENTRY.match(name):
            out.append(_mk(name_node, item, kind, EXCLUDED, "runtime or test-runner entry point"))
        elif name[:1].isupper() and package != "main":
            out.append(_mk(name_node, item, kind, UNDECIDABLE,
                           "exported identifier of an importable package (may be used by another module)"))
        else:
            out.append(_mk(name_node, item, kind, CANDIDATE, ""))

    for item in root.named_children:
        if item.type == "function_declaration":
            add(item.child_by_field_name("name"), item, "function")
        elif item.type == "type_declaration":
            for spec in item.named_children:
                add(_named_child_of_type(spec, ("type_identifier",)), item, "type")
        elif item.type in ("var_declaration", "const_declaration"):
            for spec in item.named_children:
                add(_named_child_of_type(spec, ("identifier",)), item, "constant")
    return out


# ---------------------------------------------------------------------------
# Java and C#: same shape, different node and modifier spellings
# ---------------------------------------------------------------------------

class _MemberCfg(TypedDict):
    types: tuple[str, ...]
    members: dict[str, str]
    body: tuple[str, ...]
    annotation_types: tuple[str, ...]


_JAVA_CFG: _MemberCfg = {
    "types": ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration"),
    "members": {"method_declaration": "method", "field_declaration": "field"},
    "body": ("class_body", "interface_body", "enum_body", "class_body_declaration"),
    "annotation_types": ("annotation", "marker_annotation"),
}
_CSHARP_CFG: _MemberCfg = {
    "types": ("class_declaration", "interface_declaration", "struct_declaration",
              "enum_declaration", "record_declaration"),
    "members": {"method_declaration": "method", "field_declaration": "field",
                "property_declaration": "property"},
    "body": ("declaration_list",),
    "annotation_types": ("attribute_list",),
}


# Members the Java serialization runtime reads by name through reflection. Nothing in
# the source references them, which is exactly why they read as dead. JUnit's
# `Result.serialPersistentFields` was flagged on the corpus run.
_JVM_RUNTIME_MEMBERS = frozenset({
    "serialVersionUID", "serialPersistentFields", "readObject", "writeObject",
    "readObjectNoData", "readResolve", "writeReplace",
})


def _is_extension_container(node: Node) -> bool:
    """True for a C# static class holding extension methods.

    An extension method is called as `receiver.Method()`, so the class that declares it is
    never named at any call site and reads as unreferenced. All ten of RestSharp's
    `unreferenced type` findings were extension containers: `CollectionExtensions`,
    `HttpHeadersExtensions`, and eight more, every one of them in daily use.

    Both spellings count: the classic `this`-modified first parameter, and the newer
    `extension(Receiver r) { ... }` member block, which the grammar parses as a
    constructor named `extension`.
    """
    if "static" not in _modifier_text(node):
        return False
    body = _named_child_of_type(node, ("declaration_list",))
    if body is None:
        return False
    for member in body.named_children:
        if (member.type == "constructor_declaration"
                and _text(_named_child_of_type(member, ("identifier",))) == "extension"):
            return True
        params = member.child_by_field_name("parameters")
        if params is None:
            continue
        first = next((p for p in params.named_children), None)
        if first is not None and any(_text(c) == "this" for c in first.children):
            return True
    return False


def _modifier_text(node: Node) -> str:
    """Every modifier keyword on a declaration, in either grammar's spelling. Java
    groups them under one `modifiers` node; C# emits a `modifier` node each."""
    parts = [_text(c) for c in node.named_children if c.type in ("modifiers", "modifier")]
    return " ".join(parts)


def _annotation_on(node: Node, annotation_types: tuple[str, ...]) -> str:
    """The first annotation or attribute on a declaration. An annotated member is
    reachable through a framework (injection, serialization, a test runner) that no
    syntactic scan can follow, so it is undecidable rather than dead."""
    for child in node.named_children:
        if child.type in annotation_types:
            return _text(child).splitlines()[0]
        if child.type == "modifiers":
            for inner in child.named_children:
                if inner.type in annotation_types:
                    return _text(inner).splitlines()[0]
    return ""


def _member_language(cfg: _MemberCfg) -> Callable[[Node, bytes, str, RepoFacts], list[Definition]]:
    def collect(root: Node, src: bytes, relpath: str, facts: RepoFacts) -> list[Definition]:
        out: list[Definition] = []

        def member_name(node: Node) -> Node | None:
            if node.type in ("field_declaration",):
                declarator = _named_child_of_type(node, ("variable_declarator",))
                if declarator is not None:
                    return _named_child_of_type(declarator, ("identifier",)) or declarator.child_by_field_name("name")
            return node.child_by_field_name("name") or _named_child_of_type(node, ("identifier",))

        def visit(node: Node, inside_type: bool) -> None:
            for child in node.named_children:
                if child.type in cfg["types"]:
                    name_node = child.child_by_field_name("name")
                    annotation = _annotation_on(child, cfg["annotation_types"])
                    if name_node is not None:
                        if annotation:
                            out.append(_mk(name_node, child, "type", UNDECIDABLE,
                                           f"annotated {annotation} (framework-reachable)"))
                        elif _is_extension_container(child):
                            out.append(_mk(name_node, child, "type", UNDECIDABLE,
                                           "extension-method container (dispatched on the receiver's type, "
                                           "so the class name never appears at a call site)"))
                        elif "public" in _modifier_text(child):
                            out.append(_mk(name_node, child, "type", UNDECIDABLE,
                                           "public type (may be consumed outside the repository)"))
                        else:
                            out.append(_mk(name_node, child, "type", CANDIDATE, ""))
                    visit(child, True)
                elif child.type in cfg["members"] and inside_type:
                    name_node = member_name(child)
                    if name_node is None:
                        continue
                    kind = cfg["members"][child.type]
                    annotation = _annotation_on(child, cfg["annotation_types"])
                    modifiers = _modifier_text(child)
                    if _text(name_node) in ("main", "Main"):
                        out.append(_mk(name_node, child, kind, EXCLUDED, "program entry point"))
                    elif _text(name_node) in _JVM_RUNTIME_MEMBERS:
                        out.append(_mk(name_node, child, kind, EXCLUDED,
                                       "read by the serialization runtime through reflection"))
                    elif annotation:
                        out.append(_mk(name_node, child, kind, UNDECIDABLE,
                                       f"annotated {annotation} (framework-reachable)"))
                    elif "private" in modifiers:
                        out.append(_mk(name_node, child, kind, CANDIDATE, ""))
                    else:
                        out.append(_mk(name_node, child, kind, UNDECIDABLE,
                                       "non-private member (may be overridden or dispatched through an interface)"))
                else:
                    visit(child, inside_type)

        visit(root, False)
        return out

    return collect


# ---------------------------------------------------------------------------
# TypeScript and JavaScript
# ---------------------------------------------------------------------------

_JS_DECLS = {
    "function_declaration": "function", "generator_function_declaration": "function",
    "class_declaration": "class", "interface_declaration": "interface",
    "type_alias_declaration": "type", "enum_declaration": "enum",
    "abstract_class_declaration": "class",
}
_JS_NAME_TYPES = ("identifier", "type_identifier")


def _js(root: Node, src: bytes, relpath: str, facts: RepoFacts) -> list[Definition]:
    is_entry = relpath in facts["js_entry_files"]
    out: list[Definition] = []

    def add(name_node: Node | None, item: Node, kind: str, exported: bool, default: bool) -> None:
        if name_node is None:
            return
        if default:
            out.append(_mk(name_node, item, kind, UNDECIDABLE,
                           "default export (an importer binds it under any name)"))
        elif exported and is_entry:
            out.append(_mk(name_node, item, kind, UNDECIDABLE,
                           "named in package.json as a package entry point"))
        else:
            out.append(_mk(name_node, item, kind, CANDIDATE, ""))

    def declaration(node: Node, exported: bool, default: bool, item: Node) -> None:
        kind = _JS_DECLS.get(node.type)
        if kind is not None:
            add(node.child_by_field_name("name") or _named_child_of_type(node, _JS_NAME_TYPES),
                item, kind, exported, default)
        elif node.type in ("lexical_declaration", "variable_declaration"):
            for declarator in node.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name_node = declarator.child_by_field_name("name")
                if name_node is not None and name_node.type == "identifier":
                    add(name_node, item, "variable", exported, default)

    for stmt in root.named_children:
        if stmt.type == "export_statement":
            default = any(_text(c) == "default" for c in stmt.children)
            inner = stmt.child_by_field_name("declaration")
            if inner is not None:
                declaration(inner, True, default, stmt)
        else:
            declaration(stmt, False, False, stmt)
    return out


# ---------------------------------------------------------------------------
# C
# ---------------------------------------------------------------------------

def _c_declared_identifier(node: Node) -> Node | None:
    """Descend a C declarator (pointer, array, function) to the identifier NODE it names.

    Named apart from ts_nodes.c_declarator_name, which it used to share a name with. They
    answer different questions and must: this one descends THROUGH a function_declarator to
    reach the function's name, because a definition is what L1.12 is enumerating; that one
    returns nothing for a function_declarator, because a function is not a state binding.
    One name over two rules is how a caller reaches for the wrong one and gets a plausible
    answer."""
    current: Node | None = node
    while current is not None:
        if current.type == "identifier":
            return current
        nxt = current.child_by_field_name("declarator")
        if nxt is None:
            return _named_child_of_type(current, ("identifier",))
        current = nxt
    return None


def _c(root: Node, src: bytes, relpath: str, facts: RepoFacts) -> list[Definition]:
    out: list[Definition] = []
    for item in root.named_children:
        if item.type == "function_definition":
            name_node = _c_declared_identifier(item.child_by_field_name("declarator"))
            kind = "function"
        elif item.type == "declaration":
            declarator = _named_child_of_type(item, ("init_declarator",))
            name_node = _c_declared_identifier(declarator) if declarator is not None else None
            kind = "variable"
        else:
            continue
        if name_node is None:
            continue
        is_static = any(_text(c) == "static" for c in item.named_children
                        if c.type == "storage_class_specifier")
        if _text(name_node) == "main":
            out.append(_mk(name_node, item, kind, EXCLUDED, "program entry point"))
        elif is_static:
            out.append(_mk(name_node, item, kind, CANDIDATE, ""))
        else:
            out.append(_mk(name_node, item, kind, UNDECIDABLE,
                           "external linkage (may be called from a translation unit outside this repository)"))
    return out


# ---------------------------------------------------------------------------
# Ruby
# ---------------------------------------------------------------------------

_RUBY_HOOKS = frozenset({
    "initialize", "method_missing", "respond_to_missing?", "to_s", "to_str", "inspect",
    "each", "call", "==", "<=>", "coerce", "hash", "eql?", "included", "extended", "inherited",
})


def _ruby(root: Node, src: bytes, relpath: str, facts: RepoFacts) -> list[Definition]:
    """Top-level methods, classes, modules and constants only.

    A method defined inside a class is deliberately not analyzed: Ruby dispatches it on
    a receiver whose type is not known statically, so an unreferenced name inside a
    class is not evidence of anything. The repository-level metaprogramming gate in
    dead_code.py decides whether even this much is publishable."""
    out: list[Definition] = []
    for item in root.named_children:
        if item.type in ("method", "singleton_method"):
            name_node = item.child_by_field_name("name")
            if name_node is None:
                continue
            status = EXCLUDED if _text(name_node) in _RUBY_HOOKS else CANDIDATE
            out.append(_mk(name_node, item, "method", status,
                           "interpreter hook method" if status == EXCLUDED else ""))
        elif item.type in ("class", "module"):
            name_node = item.child_by_field_name("name")
            if name_node is not None:
                out.append(_mk(name_node, item, item.type, CANDIDATE, ""))
        elif item.type == "assignment":
            left = item.child_by_field_name("left")
            if left is not None and left.type == "constant":
                out.append(_mk(left, item, "constant", CANDIDATE, ""))
    return out


COLLECTORS: dict[str, Callable[[Node, bytes, str, RepoFacts], list[Definition]]] = {
    "python": _python,
    "rust": _rust,
    "go": _go,
    "java": _member_language(_JAVA_CFG),
    "csharp": _member_language(_CSHARP_CFG),
    "typescript": _js,
    "javascript": _js,
    "c": _c,
    "ruby": _ruby,
}
