"""The state census: a second, independent count of state-bearing declarations.

Every self-disclosure number the classifier publishes - the silence index, the resolvable
fraction, the section-7 partition count - is computed over the state the classifier
RECOGNIZED. That denominator cannot see non-enumeration. A struct field the C enumerator
does not know about, a file the bucketer set aside, a construct no LANG_SPEC entry
mentions: none of them produce silence, because silence is measured over what was noticed.
Zero of zero undecided is 0%, so the silence floor structurally cannot fire on a repository
the classifier never read, and the card reads maximum confidence off an empty denominator.

This module supplies the denominator the classifier cannot supply for itself. It counts
DECLARATION SITES of state-bearing constructs straight from the parse tree - struct and
class fields, receiver-assigned attributes, instance variables, file-scope and
package-level bindings - and it does so without calling `_enum_module_state`,
`_enum_instance_state` or anything else on the classifier's recognition path. That
independence is the whole design: a shared enumerator would make the two counts agree by
construction and the gap would never open.

The defect that motivated it, exactly: an unbounded C cache reaches PROMISCUOUS (grade F)
when it is written `static int cache[256]` at file scope, and reaches an affirmative "none
of the data this code keeps can grow without limit" (grade A) when the identical array is
written `struct Store { int cache[256]; }`, because the C enumerator reads file-scope
declarations and nothing else. One syntactic level of hiding, five letter grades.

What the census is NOT. It is not a better classifier and it issues no verdict about any
piece of state. It answers one question - did the analysis look at this code at all - and
the only thing it can do to a report is withhold a grade. A declaration site here is a
place state is spelled, so the count is deliberately crude: it never follows a reference,
never resolves a type, and never decides whether the state is bounded.

Per-language limits are recorded against each extractor below, and the limits are real:
a language whose state hides somewhere the census does not look will report a small
denominator and let a thin analysis pass. The census narrows the blind spot; it does not
close it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tree_sitter import Node

from l1_analyzer.indicators import LANG_CFG, _get_parser, _read_source_bytes
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import text as _text

# One declaration site, keyed so the same slot spelled twice in one file counts once:
# `self.x = 0` in __init__ and `self.x = 1` in reset() are one piece of state, and a
# denominator that counted them twice would open a gap the code never had. The scope id is
# the enclosing record's byte offset, which keeps `A.x` and `B.x` apart without needing to
# resolve either name.
Site = tuple[str, str]      # (kind, scope-qualified name)


def _descendants(node: Node) -> list[Node]:
    out: list[Node] = []

    def walk(n: Node) -> None:
        out.append(n)
        for c in n.children:
            walk(c)

    walk(node)
    return out


def _of_type(root: Node, types: tuple[str, ...]) -> list[Node]:
    return [n for n in _descendants(root) if n.type in types]


def _enclosing(node: Node, types: tuple[str, ...]) -> Node | None:
    """The nearest ancestor of one of `types`, or None. Used to qualify a name by the
    record that owns it, so two classes with a field of the same name are two sites."""
    parent = node.parent
    while parent is not None:
        if parent.type in types:
            return parent
        parent = parent.parent
    return None


def _scope_key(node: Node, types: tuple[str, ...]) -> str:
    owner = _enclosing(node, types)
    return "-" if owner is None else str(owner.start_byte)


def _named_field(node: Node, names: tuple[str, ...]) -> str:
    """The first present name-ish field of a declaration node, as text."""
    for name in names:
        found = _field(node, name)
        if found is not None:
            return _text(found)
    return ""


# --------------------------------------------------------------------------
# Record fields. Every language in the table spells "a slot declared inside a
# record type" with its own node, and the classifier reads only some of them:
# LANG_SPEC leaves field_decl_types empty for C, Rust and Go entirely.
# --------------------------------------------------------------------------

# (field-declaration node types, name node types, declarator node types, record node types)
_FIELDS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    # C: the case the census exists for. A struct or union field is invisible to the
    # classifier, whose C enumerator reads file-scope declarations only.
    "c": (("field_declaration",), ("field_identifier",), (),
          ("struct_specifier", "union_specifier")),
    "rust": (("field_declaration",), ("field_identifier",), (), ("struct_item", "union_item")),
    "go": (("field_declaration",), ("field_identifier",), (), ("struct_type",)),
    "java": (("field_declaration",), (), ("variable_declarator",), ("class_declaration",)),
    # C# properties hold state as surely as fields do, and the classifier's field_decl_types
    # names only field_declaration, so an auto-property is state nobody counted.
    "csharp": (("field_declaration", "property_declaration"), ("identifier",),
               ("variable_declarator",), ("class_declaration", "record_declaration", "struct_declaration")),
    "typescript": (("public_field_definition",), (), (), ("class_declaration",)),
    "javascript": (("field_definition",), (), (), ("class_declaration",)),
    "python": ((), (), (), ("class_definition",)),
    "ruby": ((), (), (), ("class", "module")),
}
# The name-carrying field of a field declaration, tried in order.
_FIELD_NAME_FIELDS = ("name", "property", "declarator")


def _field_sites(root: Node, lang: str) -> list[Site]:
    decl_types, name_types, declarator_types, record_types = _FIELDS[lang]
    if not decl_types:
        return []
    sites: list[Site] = []
    for fd in _of_type(root, decl_types):
        scope = _scope_key(fd, record_types)
        declared = [_named_field(d, ("name",)) for d in _of_type(fd, declarator_types)] if declarator_types else []
        if not declared:
            direct = _named_field(fd, _FIELD_NAME_FIELDS)
            declared = [direct] if direct else [_text(n) for n in _of_type(fd, name_types)]
        sites += [("field", f"{scope}.{name}") for name in declared if name]
    return sites


# --------------------------------------------------------------------------
# Receiver-assigned attributes and instance variables: state that is never
# declared, only assigned, which is how Python, Ruby and untyped JS spell it.
# --------------------------------------------------------------------------

# (assignment node types, lvalue field, member node types, object field, attribute field,
#  receiver identifiers, record node types)
_RECEIVER: dict[str, tuple[tuple[str, ...], str, tuple[str, ...], str, str, frozenset[str], tuple[str, ...]]] = {
    "python": (("assignment",), "left", ("attribute",), "object", "attribute",
               frozenset({"self", "cls"}), ("class_definition",)),
    "javascript": (("assignment_expression",), "left", ("member_expression",), "object", "property",
                   frozenset({"this"}), ("class_declaration",)),
    "typescript": (("assignment_expression",), "left", ("member_expression",), "object", "property",
                   frozenset({"this"}), ("class_declaration",)),
    "rust": ((), "", (), "", "", frozenset(), ()),
    "java": ((), "", (), "", "", frozenset(), ()),
    "csharp": ((), "", (), "", "", frozenset(), ()),
    "go": ((), "", (), "", "", frozenset(), ()),
    "c": ((), "", (), "", "", frozenset(), ()),
    # Ruby names instance state with a node type of its own and no receiver, so the
    # member-access shape above does not apply and it is handled by _ruby_ivar_sites.
    "ruby": ((), "", (), "", "", frozenset(), ()),
}


def _receiver_sites(root: Node, lang: str) -> list[Site]:
    assign_types, lvalue, member_types, obj_field, attr_field, receivers, record_types = _RECEIVER[lang]
    if not assign_types:
        return []
    sites: list[Site] = []
    for assign in _of_type(root, assign_types):
        left = _field(assign, lvalue)
        if left is None or left.type not in member_types:
            continue
        obj = _field(left, obj_field)
        if obj is None or _text(obj) not in receivers:
            continue
        attr = _field(left, attr_field)
        if attr is not None:
            sites.append(("attribute", f"{_scope_key(assign, record_types)}.{_text(attr)}"))
    return sites


def _ruby_ivar_sites(root: Node) -> list[Site]:
    """Ruby instance variables, counted where they are ASSIGNED. A read of an ivar that is
    never written in this file is state declared elsewhere, and counting it here would
    charge one file for another file's slot."""
    sites: list[Site] = []
    for assign in _of_type(root, ("assignment", "operator_assignment")):
        left = _field(assign, "left")
        if left is not None and left.type == "instance_variable":
            sites.append(("attribute", f"{_scope_key(assign, ('class', 'module'))}.{_text(left)}"))
    return sites


# --------------------------------------------------------------------------
# Top-level bindings. Read from the root's own children, so a name bound inside a
# function is a local and never reaches the census.
# --------------------------------------------------------------------------

def _py_toplevel(root: Node) -> list[Site]:
    """Module-level bindings, plus class-body attributes. Both are state whose lifetime is
    the process, and neither is a local."""
    sites: list[Site] = []
    for stmt in root.children:
        if stmt.type != "expression_statement":
            continue
        for assign in _of_type(stmt, ("assignment",)):
            left = _field(assign, "left")
            if left is not None and left.type == "identifier":
                sites.append(("module", _text(left)))
    for cls in _of_type(root, ("class_definition",)):
        body = _field(cls, "body")
        for stmt in (body.children if body is not None else []):
            if stmt.type != "expression_statement":
                continue
            for assign in _of_type(stmt, ("assignment",)):
                left = _field(assign, "left")
                if left is not None and left.type == "identifier":
                    sites.append(("field", f"{cls.start_byte}.{_text(left)}"))
    return sites


def _js_toplevel(root: Node) -> list[Site]:
    """Top-level `let` / `var` / `const` declarators. `const` is included where the
    classifier excludes it: a const binding to a mutable object is state, and the census
    asks what was declared, not what can be reassigned."""
    sites: list[Site] = []
    for decl in root.children:
        if decl.type not in ("lexical_declaration", "variable_declaration"):
            continue
        for vd in _of_type(decl, ("variable_declarator",)):
            name = _field(vd, "name")
            if name is not None and name.type == "identifier":
                sites.append(("module", _text(name)))
    return sites


def _rust_toplevel(root: Node) -> list[Site]:
    """`static` items. A plain `static` is immutable and the classifier skips it; the
    census counts it, because immutability is a verdict about the state and the census
    issues none."""
    return [("module", _named_field(st, ("name",)))
            for st in root.children if st.type == "static_item" and _named_field(st, ("name",))]


def _go_toplevel(root: Node) -> list[Site]:
    sites: list[Site] = []
    for decl in root.children:
        if decl.type != "var_declaration":
            continue
        for spec in _of_type(decl, ("var_spec",)):
            name = _field(spec, "name")
            if name is not None:
                sites.append(("module", _text(name)))
    return sites


def _c_declarator_name(node: Node | None) -> str:
    """The identifier a C declarator binds, unwrapping init / array / pointer declarators.
    Deliberately re-derived here rather than imported from state_bounds: the census is the
    second reading, and a shared helper is a shared blind spot."""
    if node is None:
        return ""
    if node.type == "identifier":
        return _text(node)
    if node.type == "function_declarator":
        return ""
    if node.type in ("init_declarator", "array_declarator", "pointer_declarator"):
        return _c_declarator_name(_field(node, "declarator"))
    return ""


def _c_toplevel(root: Node) -> list[Site]:
    sites: list[Site] = []
    for decl in root.children:
        if decl.type != "declaration" or any(c.type == "type_definition" for c in decl.children):
            continue
        for child in decl.children:
            name = _c_declarator_name(child)
            if name:
                sites.append(("module", name))
    return sites


def _no_toplevel(root: Node) -> list[Site]:
    """Java, C# and Ruby have no module scope worth counting: their state is fields and
    instance variables, both already counted above."""
    return []


_TOPLEVEL: dict[str, Callable[[Node], list[Site]]] = {
    "python": _py_toplevel, "javascript": _js_toplevel, "typescript": _js_toplevel,
    "rust": _rust_toplevel, "go": _go_toplevel, "c": _c_toplevel,
    "java": _no_toplevel, "csharp": _no_toplevel, "ruby": _no_toplevel,
}


def _file_sites(root: Node, lang: str) -> set[Site]:
    sites = _field_sites(root, lang) + _receiver_sites(root, lang) + _TOPLEVEL[lang](root)
    if lang == "ruby":
        sites += _ruby_ivar_sites(root)
    return set(sites)


def count(repo: Path, lang: str) -> dict[str, object]:
    """The census over a repository, in the same scope the classifier uses.

    `declared` is None, never 0, for a language with no census spec. A confident zero is
    exactly the failure this module exists to stop: it would let an unread repository
    report a full denominator and pass. None says "not counted here", which withholds the
    gap check rather than faking it."""
    if lang not in _FIELDS or lang not in LANG_CFG:
        return {"declared": None, "by_kind": {}, "files": 0}
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION_WITHOUT_CONFORMANCE)
    by_kind: dict[str, int] = {"field": 0, "attribute": 0, "module": 0}
    declared = 0
    for _path, src in files:
        for kind, _name in _file_sites(parser.parse(src).root_node, lang):
            by_kind[kind] += 1
            declared += 1
    return {"declared": declared, "by_kind": by_kind, "files": len(files)}


def compare(repo: Path, lang: str, admitted: int) -> dict[str, object]:
    """The census beside what the classifier admitted, which is the only comparison that
    can see non-enumeration.

    `admitted_fraction` is None when nothing was declared or the language has no census.
    Those two are not a ratio of zero; they are the absence of a ratio, and a caller that
    reads them as 0.0 would refuse a grade to every repository the census cannot count."""
    census = count(repo, lang)
    declared = census["declared"]
    fraction = None
    if isinstance(declared, int) and declared > 0:
        fraction = round(min(admitted / declared, 1.0), 3)
    return {**census, "admitted": admitted, "admitted_fraction": fraction}
