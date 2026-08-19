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

WHICH DECLARATIONS COUNT TOWARDS THE DENOMINATOR, and why a raw count could not decide it.
"No rule existed" and "every rule said no" both leave the classifier with nothing admitted,
and comparing two totals cannot separate them. A Rust or Go struct field is the first: the
classifier enumerates those from usage and from nothing else, so a field no method touches
could not have been admitted and a refusal is right. This repository's own analyzer package
is the second: every state it declares is a TypedDict body or an all-caps module constant,
the enumerator has a rule for the module bindings, it ran that rule over each one and
declined them on the merits, and a planted `self.cache = {}` beside them is admitted. Same
zero, opposite facts, and the first version of this module refused both.

`struct Store { int cache[256]; }` in C was the first case too, until `record_state` taught
the classifier struct fields. Three of these entries have flipped from unreadable to
readable that way, which is what the table is for: it is measured, so it moved on its own
when the rule landed.

So the denominator is the declaration sites THE CLASSIFIER'S OWN WALK REACHED, published as
`visited`, and the refusal is that it reached none of them. `declared` stays beside it,
because the wider count is the more conservative disclosure of how thin a reading was.

THE DENOMINATOR IS MEASURED PER SITE, ON THE REPOSITORY IN FRONT OF IT. It used to be
measured per (language, declaration KIND), against a fixture, by the `CAPABILITY` table
below, and that granularity is the defect this module carried from 2026-08-15 to
2026-08-16. A kind was recorded readable when ONE fixture of that kind could be read, the
three record rules made every one of the nineteen pairs readable, `reachable` therefore
equalled `declared` on every repository, and the refusal could not fire at all. Everything
hanging off it went with it: `report.census_unread`, `card._census_note`, the "Insufficient
basis" wording and the cli line that reads it were all unreachable in production, and seven
tests were skipped with the reason written on them.

What makes the site-level denominator right is that a kind is not a property of a
repository. `struct Store { int cache[256]; }` used in the same file is read; the same
declaration in a header, used in another translation unit, is not; both are one kind. A Rust
or Go struct field is starker still - those two languages enumerate fields from usage and
from nothing else, so a field no method touches was never looked at, while the kind's fixture
says the kind is readable. Measured on sixteen real trees (the six pinned corpus
repositories and ten local ones) `visited` runs from 323/373 to 1,002/1,002 and reaches zero
on none of them, so this is a one-way tightening that refuses nothing that used to grade,
and it fires on the case the docstring above has named since the module was written.

`CAPABILITY` survives, and its job is now the one it can do. It no longer decides any
denominator. It is the regression test that a rule the classifier HAS is not silently lost:
each entry carries a fixture and `tests/test_state_census.py` runs every one through the real
classifier, so removing a rule turns a test red instead of quietly shrinking what gets read.
It also fixes the kind vocabulary, so a construct the extractors emit with no capability entry
is a KeyError rather than a site missing from the count.

Per-language limits are recorded against each extractor below, and the limits are real:
a language whose state hides somewhere the census does not look will report a small
denominator and let a thin analysis pass. The census narrows the blind spot; it does not
close it. The largest one left is that a single visited site is enough to grade a repository
whose other declarations nothing reached; `unread_kinds` names those kinds on the card so the
gap is disclosed rather than closed on paper.

WHAT DISCLOSES THAT GAP NOW, and what used to pretend to. `admitted_fraction` divided
`len(findings)` by `declared`: conclusions over declarations, two counts of different things.
A file holding one TypedDict of five fields and one module-level `cache = {}` published 0.167
with nothing missed at all - the reader walked every one of the six declarations and was right
about five of them - so a codebase using more typed records scored worse for being no less well
read. That number reached every report card, every adopter's JSON and the public web card, and
it was quoted as coverage. It is deleted, not repaired.

In its place `compare` publishes two fractions over ONE unit, the declaration site.
`visited_fraction` is sites the classifier's enumerator reached over sites declared: how much
of what this code spells did the reader look at. `judged_fraction` is sites that reached a
verdict over sites reached: of what it looked at, how much held state there was anything to
conclude about. The visits come from the enumerators' own walk and never from a second
traversal guessing where the first one went; `state_sites` holds the vocabulary the two walks
name a site in, and the full list of the places that naming cannot be made to match.

libuv now reads 1.0 visited and 0.366 judged, and both are the truth: the C rule reaches every
field declaration in every file, and joins barely more than a third of them to a use, because
the rest are used in a translation unit a file-at-a-time reading never opens. The old 0.277 was
wrong in direction as well as in size - it read as a reader that had seen a quarter of the code.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.indicators import LANG_CFG, _get_parser, _read_source_bytes
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.state_sites import (
    CLASS_BODY_BINDING,
    FIELD_DECLARATION,
    INSTANCE_VARIABLE,
    MODULE_BINDING,
    PROPERTY_DECLARATION,
    RECEIVER_ATTRIBUTE,
    Site,
)
from l1_analyzer.state_sites import (
    DECL_KIND as _DECL_KIND,
)
from l1_analyzer.state_sites import (
    enclosing_owner as _owner,
)
from l1_analyzer.state_sites import (
    owner_name as _owner_name,
)
from l1_analyzer.ts_nodes import c_declarator_name as _c_declarator_name
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import local_refs as _local_refs
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import text as _text

# The declaration kinds and the shape of a site both live in `state_sites`, because the
# classifier's enumerators now name the declarations THEY reach in the same vocabulary and the
# two walks are compared site by site. Sharing the names is not sharing the count: nothing
# below calls the classifier, and the sites here come from this file's own walk.
#
# One site is (kind, owning record, declared name), keyed so the same slot spelled twice in one
# file counts once: `self.x = 0` in __init__ and `self.x = 1` in reset() are one piece of state,
# and a denominator that counted them twice would open a gap the code never had.


def _of_type(root: Node, types: tuple[str, ...]) -> list[Node]:
    return _refs(root, lambda n: n.type in types)


def _own(scope: Node, types: tuple[str, ...], stop: tuple[str, ...]) -> list[Node]:
    """Nodes of `types` belonging to `scope` itself, never to a record or declaration nested
    inside it. A nested one is reached on its own turn and counted against its own owner."""
    return _local_refs(scope, lambda n: n.type in types, stop)


# The declarator wrappers a field declaration can put between itself and the name it binds.
# `int cache[256]`, `char *name` and `void (*cb)(int)` each declare one slot behind one to
# three of them. Whitelisted rather than unwrapped by "take the first named child", which
# would walk into an anonymous member's struct body and return another record's field.
#
# Re-derived here rather than imported from `record_state`, which unwraps the same wrappers on
# the classifier's side: the census is the second reading, and a shared extractor is a shared
# blind spot. What the two DO have to agree on is the name they arrive at, because the coverage
# number is measured by matching those names. That agreement was missing and is what this
# helper fixes: the census named a C field `cache[256]` where the classifier named it `cache`,
# so every array, pointer and function-pointer field in C read as a declaration nothing had
# visited. libuv reported 0.582 visited on that defect and reports 0.928 without it.
_DECLARATOR_WRAPPERS = ("array_declarator", "pointer_declarator", "function_declarator",
                        "parenthesized_declarator", "attributed_declarator", "init_declarator")


def _bound_name(node: Node | None) -> str:
    """The identifier a name-ish declaration node binds, past any declarator wrappers."""
    if node is None:
        return ""
    if node.type not in _DECLARATOR_WRAPPERS:
        return _text(node)
    inner = _field(node, "declarator")
    if inner is None:
        inner = next((c for c in node.children if c.is_named), None)
    return _bound_name(inner)


def _named_field(node: Node, names: tuple[str, ...]) -> str:
    """The name the first present name-ish field of a declaration node binds."""
    for name in names:
        found = _field(node, name)
        if found is not None:
            return _bound_name(found)
    return ""


# --------------------------------------------------------------------------
# Record fields. Every language in the table spells "a slot declared inside a
# record type" with its own node, and the classifier reads them by two different
# routes: LANG_SPEC's field_decl_types for the languages whose fields are named
# the same way at their uses, and record_state for C, whose fields are not.
# Rust and Go go through neither, and are enumerated from usage instead.
# --------------------------------------------------------------------------

# (field-declaration node types, name node types, declarator node types, record node types)
_FIELDS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    # C: the case the census exists for. A struct or union field was invisible to the
    # classifier until record_state, whose C enumerator read file-scope declarations only.
    # It is still invisible when the struct is declared in a header and used elsewhere,
    # which the census counts and the classifier cannot reach.
    "c": (("field_declaration",), ("field_identifier",), (),
          ("struct_specifier", "union_specifier")),
    "rust": (("field_declaration",), ("field_identifier",), (), ("struct_item", "union_item")),
    # The owner is the `type_spec` the struct sits under, not the anonymous `struct_type`
    # itself: the classifier reaches a Go field from a method receiver and can name only the
    # type. An inline struct bound to no named type has no type_spec and is unmatchable.
    "go": (("field_declaration",), ("field_identifier",), (), ("type_spec",)),
    # Every body a field can be declared in, not just a class: an interface constant and
    # an enum field are declaration sites too, and with only class_declaration listed they
    # got no owner at all. A site with no owner cannot be matched against a walk that
    # names one, so it read as unvisited whether or not anything had looked at it.
    "java": (("field_declaration",), (), ("variable_declarator",),
             ("class_declaration", "interface_declaration", "enum_declaration",
              "record_declaration", "annotation_type_declaration")),
    # C# properties hold state as surely as fields do, and field_decl_types named only
    # field_declaration, so an auto-property was state nobody counted until it was added.
    "csharp": (("field_declaration", "property_declaration"), ("identifier",),
               ("variable_declarator",), ("class_declaration", "record_declaration", "struct_declaration",
                                          "interface_declaration", "enum_declaration")),
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
        owner = _owner(fd, record_types)
        # Bounded at the next record or the next declaration, so a declaration only ever
        # names its OWN slots. An anonymous member is the case that forced this: C spells
        # `union { int b; int c; };` as a field declaration wrapping a union whose members
        # are field declarations of their own, and an unbounded name walk read b and c off
        # the wrapper as well as off themselves. libuv counted 1,345 field declarations that
        # way, of which the wrapper duplicates were sites nothing could ever visit, because
        # they were attributed to the outer struct while the fields themselves belong to the
        # union. The double count inflated the denominator and read as a hole in the reader.
        inner = record_types + decl_types
        declared = [_named_field(d, ("name",)) for d in _own(fd, declarator_types, inner)] if declarator_types else []
        if not declared:
            direct = _named_field(fd, _FIELD_NAME_FIELDS)
            declared = [direct] if direct else [_text(n) for n in _own(fd, name_types, inner)]
        # A field declaration with no record around it is not a field declaration. Every
        # grammar here produces the node only inside a record body, so an ownerless one is the
        # parser recovering from something it could not read - in libuv, 255 macro-prefixed
        # function prototypes (`UV_EXTERN void uv_mutex_unlock(uv_mutex_t*);`) parsed as
        # top-level field declarations and were counted as places the code keeps data. They
        # inflated the denominator by a fifth and every one of them read as a declaration
        # nothing had visited, which is a reading failure the reader never committed.
        if owner:
            sites += [(_DECL_KIND[fd.type], owner, name) for name in declared if name]
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
            sites.append((RECEIVER_ATTRIBUTE, _owner(assign, record_types), _text(attr)))
    return sites


def _ruby_ivar_sites(root: Node) -> list[Site]:
    """Ruby instance variables, counted where they are ASSIGNED. A read of an ivar that is
    never written in this file is state declared elsewhere, and counting it here would
    charge one file for another file's slot."""
    sites: list[Site] = []
    for assign in _of_type(root, ("assignment", "operator_assignment")):
        left = _field(assign, "left")
        if left is not None and left.type == "instance_variable":
            sites.append((INSTANCE_VARIABLE, _owner(assign, ("class", "module")), _text(left)))
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
                sites.append((MODULE_BINDING, "", _text(left)))
    for cls in _of_type(root, ("class_definition",)):
        owner = _owner_name(cls)
        body = _field(cls, "body")
        for stmt in (body.children if body is not None else []):
            if stmt.type != "expression_statement":
                continue
            for assign in _of_type(stmt, ("assignment",)):
                left = _field(assign, "left")
                if left is not None and left.type == "identifier":
                    sites.append((CLASS_BODY_BINDING, owner, _text(left)))
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
                sites.append((MODULE_BINDING, "", _text(name)))
    return sites


def _rust_toplevel(root: Node) -> list[Site]:
    """`static` items. A plain `static` is immutable and the classifier skips it; the
    census counts it, because immutability is a verdict about the state and the census
    issues none."""
    return [(MODULE_BINDING, "", _named_field(st, ("name",)))
            for st in root.children if st.type == "static_item" and _named_field(st, ("name",))]


def _go_toplevel(root: Node) -> list[Site]:
    sites: list[Site] = []
    for decl in root.children:
        if decl.type != "var_declaration":
            continue
        for spec in _of_type(decl, ("var_spec",)):
            name = _field(spec, "name")
            if name is not None:
                sites.append((MODULE_BINDING, "", _text(name)))
    return sites




def _c_toplevel(root: Node) -> list[Site]:
    sites: list[Site] = []
    for decl in root.children:
        if decl.type != "declaration" or any(c.type == "type_definition" for c in decl.children):
            continue
        for child in decl.children:
            name = _c_declarator_name(child)
            if name:
                sites.append((MODULE_BINDING, "", name))
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


# --------------------------------------------------------------------------
# The capability matrix: for each (language, declaration kind) the census can count, can
# the CLASSIFIER'S enumerator match one at all?
#
# WHAT THIS TABLE DOES AND NO LONGER DOES. It is a regression test on the classifier's rules
# and it fixes the kind vocabulary. It does NOT decide `visited`, and until 2026-08-16 it
# decided the denominator the refusal was taken on, under the name `reachable`. That was the
# wrong unit: a kind is readable here when ONE fixture of it can be read, while readability
# varies site by site within a kind, and once the three record rules landed every pair
# measured readable and the refusal could not fire on any repository. The denominator is now
# the classifier's own per-site visit record, measured on the repository being audited.
#
# Every `source` below declares exactly one site of its kind, holds an obviously mutable
# value, and references that value somewhere, because the classifier drops a state with no
# references and an unreferenced fixture would measure that rule instead of this one. The
# question each fixture asks is capability, not judgement: `admitted: False` means no rule
# in LANG_SPEC could ever reach this construct, and it is why a `static CACHE` (immutable,
# declined on the merits) is not the fixture for a Rust module binding while `static mut`
# is.
#
# `admitted` is the MEASURED answer, checked against the real classifier by
# test_the_recorded_capability_is_what_the_classifier_actually_does. Editing a value here
# without changing the classifier turns that test red, which is the property a table
# maintained by hand does not have. All nineteen read True on 2026-08-16, at site
# granularity: for each one the classifier's judged-site record contains the very site the
# census counted, not merely some finding elsewhere in the fixture. A False here would mean a
# rule was removed.
# --------------------------------------------------------------------------

class Probe(TypedDict):
    file: str        # the fixture's filename; its extension picks the grammar
    source: str      # one declaration of this kind, mutable and referenced
    admitted: bool   # measured: did the classifier produce a finding for it


CAPABILITY: dict[tuple[str, str], Probe] = {
    ("python", MODULE_BINDING): {
        "file": "m.py", "admitted": True,
        "source": "cache = {}\n\n\ndef put(k, v):\n    cache[k] = v\n",
    },
    # The Python spelling of the C struct field. It read as nothing until `record_state`
    # taught the classifier the class body: field_decl_types is empty for Python and the
    # module scan reaches root children and one level below, so this binding sat between the
    # two enumerators and neither one touched it.
    ("python", CLASS_BODY_BINDING): {
        "file": "m.py", "admitted": True,
        "source": "class Store:\n    cache = {}\n\n    def put(self, k, v):\n        Store.cache[k] = v\n",
    },
    ("python", RECEIVER_ATTRIBUTE): {
        "file": "m.py", "admitted": True,
        "source": "class Store:\n    def __init__(self):\n        self.cache = {}\n\n    def put(self, k, v):\n        self.cache[k] = v\n",
    },
    ("javascript", MODULE_BINDING): {
        "file": "m.js", "admitted": True,
        "source": "let cache = {};\n\nexport function put(k, v) { cache[k] = v; }\n",
    },
    ("javascript", FIELD_DECLARATION): {
        "file": "m.js", "admitted": True,
        "source": "export class Store {\n  cache = {};\n  put(k, v) { this.cache[k] = v; }\n}\n",
    },
    ("javascript", RECEIVER_ATTRIBUTE): {
        "file": "m.js", "admitted": True,
        "source": "export class Store {\n  constructor() { this.cache = {}; }\n  put(k, v) { this.cache[k] = v; }\n}\n",
    },
    ("typescript", MODULE_BINDING): {
        "file": "m.ts", "admitted": True,
        "source": "let cache: Record<string, number> = {};\n\nexport function put(k: string, v: number) { cache[k] = v; }\n",
    },
    ("typescript", FIELD_DECLARATION): {
        "file": "m.ts", "admitted": True,
        "source": "export class Store {\n  cache: Record<string, number> = {};\n  put(k: string, v: number) { this.cache[k] = v; }\n}\n",
    },
    ("typescript", RECEIVER_ATTRIBUTE): {
        "file": "m.ts", "admitted": True,
        "source": "export class Store {\n  constructor() { this.cache = {}; }\n  put(k: string, v: number) { this.cache[k] = v; }\n}\n",
    },
    ("java", FIELD_DECLARATION): {
        "file": "M.java", "admitted": True,
        "source": "class Store {\n    java.util.Map<String, Integer> cache = new java.util.HashMap<>();\n    void put(String k, Integer v) { cache.put(k, v); }\n}\n",
    },
    ("csharp", FIELD_DECLARATION): {
        "file": "M.cs", "admitted": True,
        "source": "class Store {\n    System.Collections.Generic.Dictionary<string, int> cache = new();\n    void Put(string k, int v) { cache[k] = v; }\n}\n",
    },
    # The C# blind spot the census was already commenting on. field_decl_types named
    # field_declaration only, so an auto-property held state nobody enumerated until
    # property_declaration was added beside it.
    ("csharp", PROPERTY_DECLARATION): {
        "file": "M.cs", "admitted": True,
        "source": "class Store {\n    public System.Collections.Generic.Dictionary<string, int> Cache { get; set; }\n    void Put(string k, int v) { Cache[k] = v; }\n}\n",
    },
    ("rust", MODULE_BINDING): {
        "file": "m.rs", "admitted": True,
        "source": "static mut CACHE: i32 = 0;\n\npub fn bump() { unsafe { CACHE += 1; } }\n",
    },
    ("rust", FIELD_DECLARATION): {
        "file": "m.rs", "admitted": True,
        "source": "pub struct Store { pub cache: Vec<i32> }\n\nimpl Store {\n    pub fn put(&mut self, v: i32) { self.cache.push(v); }\n}\n",
    },
    ("go", MODULE_BINDING): {
        "file": "m.go", "admitted": True,
        "source": "package p\n\nvar cache = map[string]int{}\n\nfunc Put(k string, v int) { cache[k] = v }\n",
    },
    ("go", FIELD_DECLARATION): {
        "file": "m.go", "admitted": True,
        "source": "package p\n\ntype Store struct {\n\tcache map[string]int\n}\n\nfunc (s *Store) Put(k string, v int) { s.cache[k] = v }\n",
    },
    ("c", MODULE_BINDING): {
        "file": "m.c", "admitted": True,
        "source": "static int cache[256];\n\nvoid put(int k, int v) { cache[k] = v; }\n",
    },
    # The case the whole census exists for. `record_state` reaches it now, within one file:
    # the fixture declares the struct and uses it in the same translation unit, which is what
    # the rule can see. A struct declared in a header and used elsewhere still reads as
    # nothing, and this probe cannot measure that - see `_c_struct_field` for the limit.
    ("c", FIELD_DECLARATION): {
        "file": "m.c", "admitted": True,
        "source": "struct Store { int cache[256]; };\n\nvoid put(struct Store *s, int k, int v) { s->cache[k] = v; }\n",
    },
    ("ruby", INSTANCE_VARIABLE): {
        "file": "m.rb", "admitted": True,
        "source": "class Store\n  def initialize\n    @cache = {}\n  end\n\n  def put(k, v)\n    @cache[k] = v\n  end\nend\n",
    },
}


# What each kind is called in a refusal a reader has to act on. A refusal that quotes a
# count alone tells nobody which construct went unread, and the whole value of the census is
# that it can name one.
# Singular, because the sentences that use it read "every one of them is spelled as ...",
# which has to work for one declaration and for a thousand.
KIND_LABEL: dict[str, str] = {
    MODULE_BINDING: "a file-scope or package-level binding",
    CLASS_BODY_BINDING: "a name bound in a class body",
    RECEIVER_ATTRIBUTE: "a receiver-assigned attribute",
    INSTANCE_VARIABLE: "an instance variable",
    FIELD_DECLARATION: "a field declared inside a record type",
    PROPERTY_DECLARATION: "a property",
}


def kind_phrase(kinds: object) -> str:
    """The kinds named in prose, for a refusal message. Nothing to name is the honest "we
    did not record which", never an empty string that would leave the sentence dangling.
    A kind with no label is a KeyError, for the same reason `_DECL_KIND` is subscripted:
    a construct nobody named must not reach a reader as silence."""
    labels = [KIND_LABEL[k] for k in kinds] if isinstance(kinds, list) else []
    if not labels:
        return "a construct we did not record"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def _kinds(lang: str) -> list[str]:
    """The declaration kinds the census can count for this language, in table order."""
    return [kind for (spoken, kind) in CAPABILITY if spoken == lang]


def _walk(repo: Path, lang: str) -> dict[str, set[Site]]:
    """The declaration sites of every file in scope, keyed by the path the classifier reports
    its findings against.

    Keyed per file, not merged, because the site names are only unique within one file: two
    files can each declare `Store.cache`, and merging them into one set would count one site
    where two exist and would let a visit to either one cover both."""
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION_WITHOUT_CONFORMANCE)
    by_file: dict[str, set[Site]] = {}
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        by_file[rel] = _file_sites(parser.parse(src).root_node, lang)
    return by_file


def uncounted(admitted: int) -> dict[str, object]:
    """The census of a language it has no spec for. Every count is None rather than 0.

    A confident zero is exactly the failure this module exists to stop: it would let an
    unread repository report a full denominator and pass. None says "not counted here",
    which withholds the gap check rather than faking it."""
    return {"declared": None, "by_kind": {}, "files": 0, "unread_kinds": None,
            "admitted": admitted, "visited": None, "visited_fraction": None,
            "judged": None, "judged_fraction": None}


def _tally(by_file: dict[str, set[Site]], lang: str) -> dict[str, object]:
    """The counts one walk of the parse trees can produce on its own, rolled up per file.

    Declarations only. Nothing here says whether anything READ them, because this walk has no
    access to the classifier's; `compare` joins the two and publishes `visited`, which is the
    denominator the refusal is decided on. A `reachable` count used to be computed here from
    the capability table, and it could not be: capability is recorded per kind while
    readability varies per site, so it reported `declared` on every repository and the refusal
    it fed never fired."""
    # Seeded from the capability matrix, so every kind this language can spell appears with
    # its count even at zero, and a kind the extractors emit without a capability entry is a
    # KeyError below rather than a site quietly missing from the denominator.
    by_kind: dict[str, int] = {kind: 0 for kind in _kinds(lang)}
    declared = 0
    for sites in by_file.values():
        for kind, _owner_of, _name in sites:
            by_kind[kind] += 1
            declared += 1
    return {"declared": declared, "by_kind": by_kind, "files": len(by_file)}


def count(repo: Path, lang: str) -> dict[str, object]:
    """The declaration count over a repository, in the same scope the classifier uses.

    `visited` and `unread_kinds` are None here rather than zero and empty, because this
    function never runs the classifier and cannot know where it went. Zero would assert "the
    reader reached none of this", which is the exact claim the refusal is taken on and nobody
    has measured at this point. Only `compare`, which is handed the classifier's own visit
    record, may answer it."""
    if lang not in _FIELDS or lang not in LANG_CFG:
        return {"declared": None, "by_kind": {}, "files": 0, "visited": None, "unread_kinds": None}
    return {**_tally(_walk(repo, lang), lang), "visited": None, "unread_kinds": None}


def _hit_by_kind(by_file: dict[str, set[Site]], reached: dict[str, set[Site]]) -> dict[str, int]:
    """Declared sites that the classifier's walk also named, counted per declaration kind.

    Per kind rather than as one total, because a refusal owes a reader the name of what went
    unread and a bare number cannot give it. The totals are sums of this, so the count that
    withholds a grade and the kinds the card prints beside it come from one pass and cannot
    disagree about the same repository.

    Matched file by file, since a site name is unique only within a file. A file the classifier
    never opened contributes nothing rather than raising: the two walks read the same directory
    with the same scope and should agree on the file list, and if they ever do not, the honest
    reading of the difference is that those declarations went unread. The error direction is
    the safe one - a file missing here lowers coverage, never raises it."""
    out: dict[str, int] = {}
    for rel, sites in by_file.items():
        for kind, _owner_of, _name in sites & reached.get(rel, set()):
            out[kind] = out.get(kind, 0) + 1
    return out


def compare(repo: Path, lang: str, admitted: int,
            visited: dict[str, set[Site]], judged: dict[str, set[Site]]) -> dict[str, object]:
    """The census beside what the classifier's own walk reached, which is the only comparison
    that can see non-enumeration.

    TWO FRACTIONS, BECAUSE THERE WERE ALWAYS TWO QUESTIONS. `visited_fraction` is declared
    sites the enumerator reached over declared sites: how much of what this code spells did
    the reader look at. `judged_fraction` is sites that yielded a verdict over sites reached:
    of what it looked at, how much held state there was anything to conclude about. A site the
    reader reached and declined is not a gap; a site it never reached is, and only the first
    fraction can see one.

    WHAT WAS DELETED AND WHY IT IS NOT COMING BACK. `admitted_fraction` was `len(findings)`
    over `declared`: conclusions over declarations, two counts of different things. One
    TypedDict of five fields beside one module-level dict published 0.167 with nothing missed,
    and a codebase that used more typed records scored worse for being no less well read. That
    figure reached every report card, every adopter's JSON and the public web card, and it was
    quoted as coverage. `admitted` stays, as the raw count of findings it always was, divided
    by nothing.

    HOW THE TWO WALKS ARE MATCHED, and where the match cannot be made: `state_sites` holds the
    site vocabulary and the full list of the places the correspondence fails. In short, a site
    is (kind, owning record's name, declared name) within one file, and the classifier can name
    the owner only where a name exists to name - never for an anonymous Go struct type, and for
    Rust only through an `impl` block in the same file.

    `visited` and `judged` come from the enumerators' own walk, handed down through
    `_analyze_file`. Nothing here re-derives where the classifier went: a second traversal
    written to work out where the first one probably looked is a guess with a measurement's
    name, which is the class of defect this number replaced.

    `visited` IS ALSO THE REFUSAL'S DENOMINATOR, and it is the only count in this module
    entitled to be. The refusal - no grade, because the reading never started - is
    `report.census_unread`, and it asks for declarations here, none of them reached, and no
    finding produced. A separate `reachable` count answered the middle clause from the
    capability table until 2026-08-16, one answer per (language, kind) taken off a fixture,
    which reported `declared` on every repository and left the refusal dead. There is one
    number now, measured on the repository in front of it, and `unread_kinds` names the kinds
    it found nothing reached so a card can say which construct went unread."""
    if lang not in _FIELDS or lang not in LANG_CFG:
        return uncounted(admitted)
    by_file = _walk(repo, lang)
    census = _tally(by_file, lang)
    declared, by_kind = census["declared"], census["by_kind"]
    seen_by_kind, decided_by_kind = _hit_by_kind(by_file, visited), _hit_by_kind(by_file, judged)
    seen, decided = sum(seen_by_kind.values()), sum(decided_by_kind.values())
    return {**census, "admitted": admitted, "visited": seen, "judged": decided,
            "unread_kinds": [kind for kind, n in by_kind.items() if n and not seen_by_kind.get(kind)],
            # None, not 0.0, when there is no denominator. Nothing declared is not "we read
            # none of it", and nothing reached is not "we judged none of what we reached".
            "visited_fraction": round(seen / declared, 3) if isinstance(declared, int) and declared else None,
            "judged_fraction": round(decided / seen, 3) if seen else None}
