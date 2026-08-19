"""Which references actually denote a piece of state.

One question, asked before any verdict is reached: this identifier's text matches the
state's name, but does it MEAN the state? Three ways it does not, and each was found by
a repository reading wrong rather than by inspection: the name is part of an import or
package path and binds nothing here; the name is a TYPE that a field happens to share;
a nearer parameter binds it, so the reference belongs to the parameter.

Split out of state_bounds.py on 2026-08-18 when following a value into a local pushed
that module past the thousand-line god-file threshold this repository publishes. The
group is cohesive on its own terms and had grown by one rule that day, so it is the
piece that leaves. Splitting by responsibility rather than shaving lines to pass the
gate is the rule the methodology gives an adopter.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import text as _text

IMPORT_PATH_TYPES = ("import", "using_directive", "package_declaration", "package_clause")


def under_import_path(node: Node) -> bool:
    """True when the identifier is part of an import or package path, so it binds nothing
    here and is not a reference to same-named state."""
    parent = node.parent
    while parent is not None:
        if any(marker in parent.type for marker in IMPORT_PATH_TYPES):
            return True
        parent = parent.parent
    return False


def in_type_position(node: Node) -> bool:
    """True when the identifier is naming a TYPE rather than referring to state.

    `private static readonly Encoding Encoding = null;` names a type and then a field,
    both `Encoding`. References are collected by matching identifier text, so the type
    occurrence was collected as a reference to the field, and no dispatch row covers an
    identifier in a declaration's type slot: it surfaced as `identifier in
    variable_declaration`, which reads as a missing rule when the reference should never
    have been collected at all.

    The test is the grammar's own `type` field, which is the convention across every
    grammar in the table rather than a per-language spelling, so this needs no vocabulary
    entry. The walk is bounded to the enclosing type expression: a nullable, generic or
    array type wraps the name in one or two more nodes before the field appears, and
    stopping at the first non-type ancestor keeps `Foo.Bar` on the value side out of it."""
    node_, parent = node, node.parent
    while parent is not None:
        field = parent.child_by_field_name("type")
        if field is not None and field.id == node_.id:
            return True
        if "type" not in parent.type:
            return False
        node_, parent = parent, parent.parent
    return False


def shadowing_scope(node: Node, key: str, sp: LangSpec) -> Node | None:
    """The nearest enclosing function that BINDS `key` itself, or None.

    A parameter named `app` and a module variable named `app` are different objects, and
    the classifier treated them as one because their text matched. A reference inside a
    function whose own parameter list declares that name belongs to the parameter, so it
    is not evidence about the module variable. Ablation that isolated this: renaming the
    parameter, and changing nothing else, flipped the file's verdict.

    Only the parameter list is consulted. A local assignment shadows too, in Python and
    in most of the nine, but the rules diverge per language (Python's `global`, Ruby's
    block scoping), and a parameter is unambiguous everywhere. Narrow on purpose."""
    parent = node.parent
    while parent is not None:
        if parent.type in sp["func_types"]:
            for params in parent.children:
                if params.type not in sp["arglist_types"] and "param" not in params.type:
                    continue
                for declared in _refs(params, lambda n: n.type == "identifier"):
                    if _text(declared) == key:
                        return parent
        parent = parent.parent
    return None


def bound_to(refs: list[Node], key: str, sp: LangSpec) -> list[Node]:
    """The references that actually denote `key`, dropping the three ways a matching name
    does not: it names a package, it names a type, or a nearer parameter binds it.

    Both collection sites go through this. Module state and class state used to collect
    references separately, so a filter applied to one silently missed the other."""
    return [n for n in refs
            if not under_import_path(n) and not in_type_position(n)
            and shadowing_scope(n, key, sp) is None]
