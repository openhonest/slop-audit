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

So the denominator is declaration sites of a KIND THE ENUMERATOR HAS A RULE CAPABLE OF
MATCHING, published as `reachable`, and the refusal is that nothing declared here is of
such a kind. `declared` stays beside it, because the wider count is the more conservative
disclosure of how thin a reading was.

Capability is MEASURED, in `CAPABILITY` below, never asserted. A hand-maintained table of
which language handles which declaration kind rots into exactly the blind spot this module
exists to detect: it would keep claiming a rule after the rule was removed, and stay silent
about a kind nobody taught it. Each entry carries a fixture - one declaration of that kind,
holding obviously mutable state, referenced so the classifier has something to read - and
`tests/test_state_census.py` runs every one of them through the real classifier and fails
when the recorded answer and the measured answer disagree. That is why the table is asserted
at test time rather than computed on every audit: the measurement needs a temporary tree per
fixture, and an audit should not write files to learn what its own reader can do.

Per-language limits are recorded against each extractor below, and the limits are real:
a language whose state hides somewhere the census does not look will report a small
denominator and let a thin analysis pass. The census narrows the blind spot; it does not
close it.

AND AS OF THE THREE RECORD RULES, NO PAIR IN `CAPABILITY` IS UNREADABLE. That is the good
news and the bad news in one sentence. `reachable` now equals `declared` for every language
in the table, so the refusal this module exists to issue - no grade, because nothing declared
here is of a kind the reader has a rule for - can no longer fire on any of them. The check is
not wrong, it is unexercised, and an unexercised check is one nobody will notice rotting.

The blind spot did not go away with it; it moved somewhere this table's granularity cannot
see. A kind is recorded readable when ONE fixture of that kind can be read, and a C struct
field declared in a header and used in another translation unit is a field declaration the
classifier still cannot reach. libuv declares 1,345 of them, all counted `reachable`, and
373 reach a finding. What discloses that is `admitted_fraction`, which divides by `declared`
and reports 0.277 rather than the 1.0 `reachable` would flatter it to. Splitting the kind -
a field declared and used in one translation unit against one that is not - would put the
gap back where the refusal can act on it, and it is not done here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.indicators import LANG_CFG, _get_parser, _read_source_bytes
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import text as _text

# The declaration kinds, one per construct a language spells state with. They are finer than
# the three the census started with (field / attribute / module), and the extra cuts are
# where capability was measured to differ INSIDE one of the old buckets: a C# auto-property
# and a C# field were both "field", and the enumerator reads one and not the other. A kind
# that hides a capability difference is a kind that hides a blind spot.
MODULE_BINDING = "module_binding"            # file-scope or package-level binding
CLASS_BODY_BINDING = "class_body_binding"    # a name bound in a class body, not through self
RECEIVER_ATTRIBUTE = "receiver_attribute"    # self.x / this.x, assigned in a method
INSTANCE_VARIABLE = "instance_variable"      # Ruby @ivar, which has no receiver
FIELD_DECLARATION = "field_declaration"      # a slot declared inside a record type
PROPERTY_DECLARATION = "property_declaration"  # C# property: a slot with accessors

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
    "go": (("field_declaration",), ("field_identifier",), (), ("struct_type",)),
    "java": (("field_declaration",), (), ("variable_declarator",), ("class_declaration",)),
    # C# properties hold state as surely as fields do, and field_decl_types named only
    # field_declaration, so an auto-property was state nobody counted until it was added.
    "csharp": (("field_declaration", "property_declaration"), ("identifier",),
               ("variable_declarator",), ("class_declaration", "record_declaration", "struct_declaration")),
    "typescript": (("public_field_definition",), (), (), ("class_declaration",)),
    "javascript": (("field_definition",), (), (), ("class_declaration",)),
    "python": ((), (), (), ("class_definition",)),
    "ruby": ((), (), (), ("class", "module")),
}
# The name-carrying field of a field declaration, tried in order.
_FIELD_NAME_FIELDS = ("name", "property", "declarator")

# The kind each field-declaration node type belongs to, read from the node the parser
# produced rather than from the language. Subscripted, never `.get`: adding a node type to
# _FIELDS without deciding its kind is a KeyError on the next run, and the alternative - a
# default kind - would quietly file a new construct under an existing capability answer.
_DECL_KIND: dict[str, str] = {
    "field_declaration": FIELD_DECLARATION,
    "public_field_definition": FIELD_DECLARATION,    # TypeScript
    "field_definition": FIELD_DECLARATION,           # JavaScript
    "property_declaration": PROPERTY_DECLARATION,    # C#
}


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
        sites += [(_DECL_KIND[fd.type], f"{scope}.{name}") for name in declared if name]
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
            sites.append((RECEIVER_ATTRIBUTE, f"{_scope_key(assign, record_types)}.{_text(attr)}"))
    return sites


def _ruby_ivar_sites(root: Node) -> list[Site]:
    """Ruby instance variables, counted where they are ASSIGNED. A read of an ivar that is
    never written in this file is state declared elsewhere, and counting it here would
    charge one file for another file's slot."""
    sites: list[Site] = []
    for assign in _of_type(root, ("assignment", "operator_assignment")):
        left = _field(assign, "left")
        if left is not None and left.type == "instance_variable":
            sites.append((INSTANCE_VARIABLE, f"{_scope_key(assign, ('class', 'module'))}.{_text(left)}"))
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
                sites.append((MODULE_BINDING, _text(left)))
    for cls in _of_type(root, ("class_definition",)):
        body = _field(cls, "body")
        for stmt in (body.children if body is not None else []):
            if stmt.type != "expression_statement":
                continue
            for assign in _of_type(stmt, ("assignment",)):
                left = _field(assign, "left")
                if left is not None and left.type == "identifier":
                    sites.append((CLASS_BODY_BINDING, f"{cls.start_byte}.{_text(left)}"))
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
                sites.append((MODULE_BINDING, _text(name)))
    return sites


def _rust_toplevel(root: Node) -> list[Site]:
    """`static` items. A plain `static` is immutable and the classifier skips it; the
    census counts it, because immutability is a verdict about the state and the census
    issues none."""
    return [(MODULE_BINDING, _named_field(st, ("name",)))
            for st in root.children if st.type == "static_item" and _named_field(st, ("name",))]


def _go_toplevel(root: Node) -> list[Site]:
    sites: list[Site] = []
    for decl in root.children:
        if decl.type != "var_declaration":
            continue
        for spec in _of_type(decl, ("var_spec",)):
            name = _field(spec, "name")
            if name is not None:
                sites.append((MODULE_BINDING, _text(name)))
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
                sites.append((MODULE_BINDING, name))
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
# maintained by hand does not have.
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


def count(repo: Path, lang: str) -> dict[str, object]:
    """The census over a repository, in the same scope the classifier uses.

    `declared` is None, never 0, for a language with no census spec. A confident zero is
    exactly the failure this module exists to stop: it would let an unread repository
    report a full denominator and pass. None says "not counted here", which withholds the
    gap check rather than faking it.

    `reachable` is the subset of `declared` whose kind the classifier's enumerator has a
    rule capable of matching, and it is the denominator the refusal is decided on.
    `unread_kinds` names the kinds that were declared here and have no such rule, so a
    refusal can say what it could not read instead of quoting a bare count."""
    if lang not in _FIELDS or lang not in LANG_CFG:
        return {"declared": None, "by_kind": {}, "files": 0, "reachable": None, "unread_kinds": []}
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION_WITHOUT_CONFORMANCE)
    # Seeded from the capability matrix, so every kind this language can spell appears with
    # its count even at zero, and a kind the extractors emit without a capability entry is a
    # KeyError below rather than a site quietly missing from the denominator.
    by_kind: dict[str, int] = {kind: 0 for kind in _kinds(lang)}
    declared = 0
    for _path, src in files:
        for kind, _name in _file_sites(parser.parse(src).root_node, lang):
            by_kind[kind] += 1
            declared += 1
    reachable = sum(n for kind, n in by_kind.items() if CAPABILITY[(lang, kind)]["admitted"])
    unread_kinds = [kind for kind, n in by_kind.items() if n and not CAPABILITY[(lang, kind)]["admitted"]]
    return {"declared": declared, "by_kind": by_kind, "files": len(files),
            "reachable": reachable, "unread_kinds": unread_kinds}


def compare(repo: Path, lang: str, admitted: int) -> dict[str, object]:
    """The census beside what the classifier admitted, which is the only comparison that
    can see non-enumeration.

    `admitted_fraction` is None when nothing was declared or the language has no census.
    Those two are not a ratio of zero; they are the absence of a ratio, and a caller that
    reads them as 0.0 would refuse a grade to every repository the census cannot count.

    The published fraction keeps `declared` as its denominator while the refusal uses
    `reachable`, and the two answer different questions. The refusal asks whether the reader
    had a rule at all, so it must not charge a repository for kinds nobody can reach. The
    fraction is a disclosure of how thin the reading was, and dividing by the narrower count
    would flatter it: a C repository whose state is mostly struct fields would report a high
    fraction over the file-scope globals alone."""
    census = count(repo, lang)
    declared = census["declared"]
    fraction = None
    if isinstance(declared, int) and declared > 0:
        fraction = round(min(admitted / declared, 1.0), 3)
    return {**census, "admitted": admitted, "admitted_fraction": fraction}
