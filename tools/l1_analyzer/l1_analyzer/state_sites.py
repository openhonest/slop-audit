"""How one declaration site is NAMED, so two independent walks can be compared site by site.

The census counts declaration sites from the parse tree. The classifier enumerates state from
references. Both read the same files with the same grammar, and until now neither could say
anything about the other's units: `declared` counted places state is spelled and `admitted`
counted pieces of state that reached a verdict, so their ratio compared a count of declarations
against a count of conclusions. One TypedDict of five fields beside one module-level dict
reported six declared, one admitted, and a published "coverage" of 0.167 with nothing missed.

A shared NAME for a site is what the comparison needs, and it is the only thing shared here.
The counting stays independent - that independence is the whole reason the census exists, and
a shared enumerator would make the two walks agree by construction. This module holds no walk
and no rule about what state is. It answers one question: given a node one of the two walks is
looking at, what do we call the declaration site it sits on, so that the other walk names the
same site the same way.

THE SITE IS (kind, owner, name). The kind is the construct, from the list below. The name is
the declared identifier. The owner is the RECORD THAT DECLARES IT, named by its own name - not
by its byte offset, which is the change that made the two walks comparable.

Why the owner is a name and not an offset. The census reaches a field declaration by walking
down from the record, so it always has the record node and could use anything stable about it.
The classifier mostly reaches state from a USE - `self.cache` inside an impl block, `s.cache`
inside a Go method - and from a use there is no path back to the declaring record's node
without resolving a type, which is inference this analyzer does not do. What both walks can see
is a name: `struct Store` and `impl Store` agree on "Store" without either one resolving
anything. So the owner is the name, and the correspondence holds exactly as far as names do.

WHERE THE CORRESPONDENCE FAILS, in full, because a silent failure here reads as a coverage gap
that is really a naming gap:

  - An ANONYMOUS record has no name to agree on. Its owner is `@<byte offset>`, which both
    walks can compute only when both are holding the record node. The census always is; the
    classifier is for a C struct and never for a Go anonymous struct type, so a field of an
    anonymous Go struct can never be matched and reads as unvisited.
  - TWO RECORDS OF THE SAME NAME in one file collapse to one owner, so their same-named fields
    become one site. The census counts them once and the classifier can visit them once. The
    count is lower than the truth on both sides, in the same direction.
  - RUST names the owner from the `impl` block, and a struct with no impl in the same file has
    no path from any use back to its fields. Those sites read as unvisited, which is correct:
    nothing in this file's reading looked at them.
  - GO names the owner from the `type_spec` the struct type sits under, and the classifier
    names it from the method receiver's type. A struct type that is not bound to a named type
    (an inline struct in a var declaration or a field) has no type_spec and is unmatched.

Nothing here reads a file or decides a verdict. It reads a node and returns a string.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import first_named as _first_named
from l1_analyzer.ts_nodes import text as _text

# The declaration kinds, one per construct a language spells state with. They are finer than
# the three the census started with (field / attribute / module), and the extra cuts are where
# capability was measured to differ INSIDE one of the old buckets: a C# auto-property and a C#
# field were both "field", and the enumerator reads one and not the other. A kind that hides a
# capability difference is a kind that hides a blind spot.
MODULE_BINDING = "module_binding"            # file-scope or package-level binding
CLASS_BODY_BINDING = "class_body_binding"    # a name bound in a class body, not through self
RECEIVER_ATTRIBUTE = "receiver_attribute"    # self.x / this.x, assigned in a method
INSTANCE_VARIABLE = "instance_variable"      # Ruby @ivar, which has no receiver
FIELD_DECLARATION = "field_declaration"      # a slot declared inside a record type
PROPERTY_DECLARATION = "property_declaration"  # C# property: a slot with accessors

# One declaration site: the construct, the record that declares it, and the declared name.
# `owner` is the empty string at module scope, which is the one owner both walks can name
# without looking at anything.
Site = tuple[str, str, str]

# The kind each field-declaration node type belongs to, read from the node the parser produced
# rather than from the language. Subscripted by both walks, never `.get`: a node type nobody
# assigned a kind must be a KeyError on the next run, because the alternative - a default kind -
# files a new construct under an existing capability answer and hides it there.
DECL_KIND: dict[str, str] = {
    "field_declaration": FIELD_DECLARATION,
    "public_field_definition": FIELD_DECLARATION,    # TypeScript
    "field_definition": FIELD_DECLARATION,           # JavaScript
    "property_declaration": PROPERTY_DECLARATION,    # C#
}

# Rust type expressions that wrap the name of a type. `impl Store` names the owner directly;
# `impl<T> Store<T>` and `impl a::Store` reach the same struct through a wrapper, and the
# census sees only `struct Store`, so the wrappers are peeled to the bare name.
_RUST_TYPE_WRAPPERS: dict[str, str] = {
    "generic_type": "type",
    "scoped_type_identifier": "name",
    "reference_type": "type",
}


def owner_name(record: Node | None) -> str:
    """What to call the record a declaration sits in.

    None is module scope, spelled as the empty string. A record with a `name` field is called
    by its name, which is the only handle a walk arriving from a USE can produce. A record with
    no name gets its byte offset, which only a walk holding the record node can produce, and
    that is the honest answer: an anonymous record cannot be named from a distance."""
    if record is None:
        return ""
    named = _field(record, "name")
    return _text(named) if named is not None else f"@{record.start_byte}"


def enclosing_owner(node: Node, record_types: tuple[str, ...]) -> str:
    """The owner of the nearest ancestor record of one of `record_types`, or module scope.

    Nearest, not outermost: a class nested in a class owns its own body, and charging the outer
    one with the inner one's fields would make two records into one site."""
    parent = node.parent
    while parent is not None:
        if parent.type in record_types:
            return owner_name(parent)
        parent = parent.parent
    return ""


def rust_impl_owner(impl_item: Node) -> str:
    """The struct an `impl` block belongs to, by the name the struct declares itself with.

    Rust is the one language whose classifier scope is not the record: state is enumerated from
    `self.<field>` inside an impl, and the fields are declared on a struct somewhere else. The
    impl names its type and the struct names itself, and those two names are the whole of the
    correspondence: a struct whose impl is in another file is never visited from here."""
    typ = _field(impl_item, "type")
    while typ is not None and typ.type in _RUST_TYPE_WRAPPERS:
        inner = _field(typ, _RUST_TYPE_WRAPPERS[typ.type])
        typ = inner if inner is not None else _first_named(typ)
    return _text(typ)
