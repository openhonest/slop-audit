"""Record-field state: slots declared inside a record type, which no reference can reach.

The two enumerators in state_bounds both work from a REFERENCE. `_enum_module_state` reads
the bindings at the root of a file, and `_enum_instance_state` reads the names a method
assigns through its receiver. Between them sits a construct neither one touches: a slot
declared once, inside the record that owns it, and thereafter only used. A name bound in a
Python class body, a field inside a C struct, a C# auto-property. Each is a place a program
keeps data for the life of a process, and for each the classifier had no rule capable of
matching the declaration.

That is not a small miss, because nothing computed over the recognized set can see it. The
silence index, the resolvable fraction and the section-7 partition count are all measured
over state the classifier admitted, so a repository that spells its state this way produced
zero silence, a resolvable fraction of 1.0, and a card claiming none of its data can grow
without limit. The claim was made about code nothing had read. `state_census` was built to
detect exactly that, and it named these three kinds on every report it touched.

This module is the rule the census was asking for. It is separate from state_bounds for two
reasons: that file sits against the god-file line the meter enforces on itself, and record
fields are one idea per language that a dispatch table holds better than three more branches
in `_enum_instance_state`.

WHAT EVERY FINDER RETURNS, and why it is a slot rather than a key. The existing enumerators
hand back keys and let `_state_refs` find the references by matching the key's TEXT against
member-access nodes. That works when the declaration and the reference are spelled the same
way, and a record field is exactly the case where they are not: `cache = {}` is declared as
a bare identifier and used as `self.cache` or `Store.cache`, and a C struct field is declared
as `int cache[256]` and used as `s->cache`. A finder that returned only a name would collect
no references and report nothing, which is how a rule passes a capability probe and still
reads nothing. So each finder returns the references with the key and owns both halves.

REFERENCES ARE COLLECTED PER FILE, as they are for every other state in this classifier. A C
struct declared in a header and used in another translation unit is out of reach, and the
finder reports nothing for it rather than inventing a verdict over zero references. That is a
real limit and it is not small in C, where the header/source split is the normal shape; it is
recorded here rather than left for a reader to discover from a suspiciously clean report.

WHAT THESE RULES COST THE CENSUS, said plainly because nothing else says it. Capability is
recorded per (language, declaration kind), and a kind is now readable if ONE fixture of that
kind can be read. Every one of libuv's 1,345 field declarations therefore counts as
`reachable`, while the classifier reaches 373 of them, because the rest are declared in a
header this file-at-a-time reading never joins to their uses. The refusal the census can
issue - no grade when nothing declared here is of a readable kind - is correspondingly
weaker for C than it was. What still discloses the gap is `admitted_fraction`, which divides
by `declared` and reports 0.277 where `reachable` would flatter it to 1.0. A finer kind,
splitting a field declared and used in one translation unit from one that is not, is the fix;
it is not made here, and until it is, `reachable` overstates C.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import text as _text


class Slot(TypedDict):
    """One record-declared state, with everything the classifier needs to judge it.

    `writers_enumerable` is the premise the compositional call-target rule rests on, and it
    differs between the two record kinds here, which is why it travels with the slot rather
    than being decided once at the call site. A Python class attribute is written by the
    methods of its own class, so an invoked slot can be proved to hold what was injected. A
    C struct field has no such boundary: any translation unit that can see the struct can
    assign a function pointer into it, so a called field is undecidable and must fail closed
    rather than earn NEUTRAL from a premise that does not hold."""
    state: str
    refs: list[Node]
    writers_enumerable: bool


def _descend(node: Node, types: tuple[str, ...], stop: tuple[str, ...]) -> list[Node]:
    """Descendants of `node` whose type is in `types`, never entering a nested record.

    A record nested inside another owns its own fields and is enumerated as its own scope,
    so the outer walk must stop at it. Without the stop, `struct A { struct B { int x; } b; }`
    charges A with B's field and the same slot is counted twice."""
    out: list[Node] = []

    def walk(n: Node, is_root: bool) -> None:
        if not is_root and n.type in stop:
            return
        if n.type in types:
            out.append(n)
        for c in n.children:
            walk(c, False)

    walk(node, True)
    return out


def _by_attr(nodes: list[Node], attr_field: str) -> dict[str, list[Node]]:
    """Member accesses indexed by the name they reach for, built once per scope.

    A C header can declare a thousand fields and mention as many members, and rescanning the
    member list once per field name turns one file into a million string comparisons with a
    fresh utf-8 decode inside each one."""
    out: dict[str, list[Node]] = {}
    for n in nodes:
        out.setdefault(_text(_field(n, attr_field)), []).append(n)
    return out


# --------------------------------------------------------------------------
# Python: a name bound in a class body.
# --------------------------------------------------------------------------

def _py_class_body_bindings(cls: Node) -> list[tuple[str, Node]]:
    """(name, binding identifier) for each name bound at the top level of a class body.

    Only the body's own statements are read, so a name bound inside a method is a local and
    never reaches here. A bare annotation (`name: str`) is kept alongside a value-bearing
    binding: tree-sitter spells both as an `assignment`, and the two cannot be separated on
    the merits anyway. `items: list[int]` in a dataclass IS a slot, filled by a generated
    __init__, and dropping annotations to keep TypedDict fields out would drop it too. What
    keeps a TypedDict field out of the findings is that nothing references it."""
    body = _field(cls, "body")
    out: list[tuple[str, Node]] = []
    for stmt in (body.children if body is not None else []):
        if stmt.type != "expression_statement":
            continue
        for assign in [c for c in stmt.children if c.type == "assignment"]:
            left = _field(assign, "left")
            if left is not None and left.type == "identifier":
                out.append((_text(left), left))
    return out


def _py_receivers(cls: Node) -> frozenset[str]:
    """The names a class attribute can be reached through inside its own class: the two
    receivers, and the class's own name. `Store.cache[k] = v` is the spelling that makes a
    class-body binding shared mutable state rather than a per-instance default, so a rule
    that matched `self.` alone would enumerate the slot and then find nothing using it."""
    name = _field(cls, "name")
    return frozenset({"self", "cls"}) | ({_text(name)} if name is not None else frozenset())


def _python_class_body(root: Node, sp: LangSpec, already: Callable[[Node], list[str]]) -> list[Slot]:
    """Class-body bindings, minus the ones the receiver rule already reports.

    The subtraction is what keeps this additive. A default declared in the class body and
    rebound per instance (`cache = {}` beside `self.cache = {}`) is ONE slot, and publishing
    a second finding about it would inflate every count computed over findings - the verdict
    distribution, the resolvable fraction, the silence denominator - without a single new
    piece of state being read. The receiver rule keeps it, because it was there first and its
    reference matching is narrower; this rule takes only what nothing else claims."""
    found: list[Slot] = []
    for cls in _descend(root, sp["class_types"], ()):
        enumerated = set(already(cls))
        receivers = _py_receivers(cls)
        members = _by_attr(_descend(cls, sp["member_types"], sp["class_types"]), sp["mem_attr"])
        for name, binding in _py_class_body_bindings(cls):
            if any(f"{ident}.{name}" in enumerated for ident in sp["this_idents"]):
                continue
            # The binding site leads the reference list so `_binding_line` sends a reader to
            # the declaration rather than to the first place the name is used.
            refs = [binding] + [m for m in members.get(name, [])
                                if _text(_field(m, sp["mem_object"])) in receivers]
            if len(refs) > 1:
                found.append({"state": f"{_text(_field(cls, 'name'))}.{name}",
                              "refs": refs, "writers_enumerable": True})
    return found


# --------------------------------------------------------------------------
# C: a field declared inside a struct or a union.
#
# The case the census was built to expose. The identical unbounded cache reached PROMISCUOUS
# (grade F) written `static int cache[256]` at file scope and an affirmative "none of the
# data this code keeps can grow without limit" (grade A) written
# `struct Store { int cache[256]; }`, because the C enumerator read file-scope declarations
# and nothing else. One syntactic level of hiding, five letter grades.
# --------------------------------------------------------------------------

_C_RECORDS = ("struct_specifier", "union_specifier")
# Declarator wrappers between a field declaration and the name it binds. Whitelisted rather
# than unwrapped by "take the first named child", which would walk into an anonymous member's
# struct body and return a field of the wrong record as this record's name.
_C_DECLARATORS = ("array_declarator", "pointer_declarator", "function_declarator",
                  "parenthesized_declarator", "attributed_declarator", "init_declarator")


def _c_field_name(node: Node | None) -> str:
    """The identifier a C field declarator binds. `int cache[256]`, `char *name` and
    `void (*cb)(int)` each declare one slot, behind one to three wrappers."""
    if node is None:
        return ""
    if node.type == "field_identifier":
        return _text(node)
    if node.type not in _C_DECLARATORS:
        return ""
    inner = _field(node, "declarator")
    if inner is None:
        inner = next((c for c in node.children if c.is_named), None)
    return _c_field_name(inner)


def _c_struct_field(root: Node, sp: LangSpec, already: Callable[[Node], list[str]]) -> list[Slot]:
    """Struct and union fields, with every same-file member access that names them.

    TWO LIMITS, both real, both consequences of what C does not give a reader. The first is
    that a field has no owner at the point of use: `s->cache` says nothing about which struct
    `s` is, and resolving it needs type inference this analyzer does not do. So references are
    matched on the field NAME, and a name declared by two records in one file is reported once,
    against the record that declared it first, carrying both records' references. That is
    conservative in the direction that matters - it never invents a slot - but it does merge
    two slots into one finding, and the merged finding is the wrong shape when one record's
    use is bounded and the other's is not.

    The second is that references are collected per file. A struct declared in a header and
    used in another translation unit has no same-file reference, so nothing is reported for
    it: the classifier reads one file at a time and a cross-unit rule is a different piece of
    work. In C that is not a corner case, it is the normal shape of a library, and it means
    this rule reads the structs a file both declares and uses and stays blind to the rest.
    The census keeps counting all of them, so the gap stays on the report rather than closing
    on paper."""
    found: list[Slot] = []
    claimed: set[str] = set()
    members = _by_attr(_descend(root, sp["member_types"], ()), sp["mem_attr"])
    for rec in _descend(root, _C_RECORDS, ()):
        name_node = _field(rec, "name")
        tag = _text(name_node) if name_node is not None else f"struct@{rec.start_point[0] + 1}"
        for fd in _descend(rec, ("field_declaration",), _C_RECORDS):
            for declarator in fd.children:
                name = _c_field_name(declarator)
                if not name or name in claimed:
                    continue
                claimed.add(name)
                refs = members.get(name, [])
                if refs:
                    found.append({"state": f"{tag}.{name}", "refs": refs,
                                  "writers_enumerable": False})
    return found


# --------------------------------------------------------------------------
# The names one field-declaration node declares. Not a finder: `_enum_instance_state` reads
# this for every language whose fields ARE reachable from a reference, so it lives beside the
# record rules rather than inside the algorithm they feed.
#
# `property_declaration` is here because a C# auto-property holds state exactly as a field
# does, and `field_decl_types` named `field_declaration` alone. The same dictionary was read
# when it was written `Dictionary<string,int> cache;` and invisible when it was written
# `Dictionary<string,int> Cache { get; set; }`, which is the spelling the language's own
# style guide asks for on anything public. 678 of Newtonsoft.Json's 1,360 state declarations
# and 267 of RestSharp's 378 are spelled that way.
# --------------------------------------------------------------------------

# node type -> the field carrying the declared name, for declarations that name it directly.
_DIRECT_NAME_FIELD: dict[str, str] = {
    "public_field_definition": "name",       # TypeScript
    "field_definition": "property",          # JavaScript
    "property_declaration": "name",          # C#
}


def field_decl_names(fd: Node) -> list[str]:
    """The names declared by one field-declaration node. TypeScript, JavaScript and a C#
    property name the slot directly; a Java or C# field nests one or more
    variable_declarators, because `int a, b;` is one declaration of two slots."""
    direct = _DIRECT_NAME_FIELD.get(fd.type)
    if direct is not None:
        name = _field(fd, direct)
        return [_text(name)] if name is not None else []
    names: list[str] = []
    for vd in _descend(fd, ("variable_declarator",), ()):
        name = _field(vd, "name")
        if name is not None:
            names.append(_text(name))
    return names


def _no_records(root: Node, sp: LangSpec, already: Callable[[Node], list[str]]) -> list[Slot]:
    """A language whose record fields are already reachable from a reference, or that has no
    record type at all. Named and dispatched to explicitly rather than defaulted: a spec that
    forgot to say which rule it wants must be a KeyError below, not a silent nothing."""
    return []


NONE = "none"

RECORD_STATES: dict[str, Callable[[Node, LangSpec, Callable[[Node], list[str]]], list[Slot]]] = {
    NONE: _no_records,
    "python_class_body": _python_class_body,
    "c_struct_field": _c_struct_field,
}


def slots(root: Node, sp: LangSpec, already: Callable[[Node], list[str]]) -> list[Slot]:
    """The record-declared state of one file, with the references that denote it.

    `already` reports the state keys another enumerator has claimed for a given record, so a
    finder can stand down rather than double-count. Subscripted, never `.get`: a LANG_SPEC
    entry with no `record_enum` is a spec nobody finished, and it must fail loudly instead of
    quietly reading no record fields for that language."""
    return RECORD_STATES[sp["record_enum"]](root, sp, already)
