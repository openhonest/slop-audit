"""State enumeration: which declarations the classifier's reader walks, and what it makes of them.

This is the classifier's own walk, moved out of state_bounds so that file stays under the
god-file line the meter enforces on itself, and restructured so it reports TWO things instead
of one. It used to hand back a list of state keys: the names it decided were state. Everything
it looked at and declined - a `const` binding, a plain `static`, a TypedDict field nothing
references - vanished, and with it the only evidence that the reader had been there at all.

That absence is what made the published coverage number wrong. `state_census` counts
declaration sites; the classifier counted conclusions; and the ratio of the two called a
correctly declined declaration a missed one. A file holding one TypedDict of five fields and
one module-level `cache = {}` reported six declared, one admitted, and 0.167 "coverage" with
nothing missed at all.

So every enumerator here returns `Cands`: an ordered map from DECLARATION SITE to the state key
that site yields, with the empty string for a site the walk reached and declined. The sites are
named in `state_sites`' vocabulary, which is the vocabulary the census names its own sites in,
and that shared naming is the whole of the correspondence between the two walks. The counting
stays independent; only the names are shared.

The ordering is why `Cands` is a dict and not a set. `_analyze_file` iterates it to build
findings, and the final sort keys on verdict, drives_decision, file and line, so two states
declared on the SAME line tie on every key. Python's sort is stable, so a tie preserves whatever
order the enumerator handed over, and set iteration order over strings varies between processes:
six module dicts on one line once serialized in six different orders across six runs of
unchanged code. Insertion order here IS source order, because every walk below is pre-order.
"""

from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from l1_analyzer import record_state, state_sites
from l1_analyzer.indicators import LangCfg, _find_module_mutable_names
from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.mutable_state import shallow_candidates
from l1_analyzer.state_sites import Site
from l1_analyzer.ts_nodes import c_declarator_name as _c_declarator_name
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import local_refs as _local_refs
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import text as _text

# declaration site -> the state key it yields, "" for a site the walk reached and declined.
Cands = dict[Site, str]


def _put(cands: Cands, site: Site, key: str) -> None:
    """Record one site the walk reached, keeping the first position and the strongest answer.

    The same site can be reached twice - `x = 0` and `x = 1` at module scope are one binding
    written twice - and a repeat must not create a second finding. When one visit declines and
    another admits, the admitting answer wins: the walk did produce a key for that declaration,
    and reporting it as declined would lose a finding the classifier used to make. Overwriting
    an existing dict entry keeps its original insertion position, so source order survives."""
    if site not in cands or key:
        cands[site] = key


def keys_of(cands: Cands) -> list[str]:
    """The state keys the walk admitted, in source order, each one once. Two declarations can
    yield the same key - a TypeScript field `x` and an assignment `this.x` are one slot spelled
    twice - and the classifier judges the slot once."""
    out: dict[str, None] = {}
    for key in cands.values():
        if key:
            out[key] = None
    return list(out)


def sites_of(cands: Cands, key: str) -> set[Site]:
    """Every declaration site that yielded `key`. Plural on purpose: when one verdict covers
    two spellings of one slot, both declarations were judged, and crediting only one of them
    would report the other as unread."""
    return {site for site, k in cands.items() if k == key}


# --------------------------------------------------------------------------
# Module and package scope. Read from the root's own children, so a name bound inside a
# function is a local and never reaches here.
# --------------------------------------------------------------------------



def _py_module(root: Node, cfg: LangCfg) -> Cands:
    """Python module bindings. The mutability rule lives in `mutable_state` and L1.18 reads it
    too, so it is asked rather than re-implemented; what is taken from the walk here is the
    CANDIDATE list, which is the set of bindings the rule was run over. A name the rule declined
    - a type alias, an uppercase constant, a dunder - was read, and this is the only place that
    can still say so."""
    admitted = _find_module_mutable_names(root, cfg)
    cands: Cands = {}
    for node in shallow_candidates(root, cfg["module_level_assign"]):
        left = _field(node, "left")
        if left is None or left.type != "identifier":   # subscripts, tuples, attributes
            continue
        name = _text(left)
        _put(cands, (state_sites.MODULE_BINDING, "", name), name if name in admitted else "")
    return cands


def _js_module(root: Node, cfg: LangCfg) -> Cands:
    """Top-level `let` / `var` / `const` declarators. A `const` binding is declined, not
    skipped: the walk read the declaration and ruled it out because the binding cannot be
    reassigned. (It can still hold a mutable object, which is why the census counts it.)"""
    cands: Cands = {}
    for decl in root.children:
        if decl.type == "lexical_declaration":
            immutable = bool(decl.children) and _text(decl.children[0]) == "const"
        elif decl.type == "variable_declaration":
            immutable = False
        else:
            continue
        for vd in _refs(decl, lambda n: n.type == "variable_declarator"):
            name = _field(vd, "name")
            if name is not None and name.type == "identifier":
                _put(cands, (state_sites.MODULE_BINDING, "", _text(name)),
                     "" if immutable else _text(name))
    return cands


def _rust_module(root: Node, cfg: LangCfg) -> Cands:
    """`static` items. Only `static mut` is state; a plain static is immutable and declined on
    the merits, which is a reading of it, not a gap in the reader."""
    cands: Cands = {}
    for st in root.children:
        if st.type != "static_item":
            continue
        name = _field(st, "name")
        if name is None:
            continue
        mutable = any(c.type == "mutable_specifier" for c in st.children)
        _put(cands, (state_sites.MODULE_BINDING, "", _text(name)), _text(name) if mutable else "")
    return cands


def _go_module(root: Node, cfg: LangCfg) -> Cands:
    """Package-level `var` declarations. `const` is immutable and is not a var_declaration, so
    it never enters the candidate list and the census does not count it either."""
    cands: Cands = {}
    for decl in root.children:
        if decl.type != "var_declaration":
            continue
        for vs in _refs(decl, lambda n: n.type == "var_spec"):
            nm = _field(vs, "name")
            if nm is not None and nm.type == "identifier":
                _put(cands, (state_sites.MODULE_BINDING, "", _text(nm)), _text(nm))
    return cands


def _c_module(root: Node, cfg: LangCfg) -> Cands:
    """C has no classes: file-scope variable declarations are the only state this walk reads.
    Function declarations and typedefs declare no slot and never become a candidate."""
    cands: Cands = {}
    for decl in root.children:
        if decl.type != "declaration" or any(c.type == "type_definition" for c in decl.children):
            continue
        for dcl in decl.children:
            nm = _c_declarator_name(dcl)
            if nm:
                _put(cands, (state_sites.MODULE_BINDING, "", nm), nm)
    return cands


def _no_module(root: Node, cfg: LangCfg) -> Cands:
    """Java, C# and Ruby keep module and static state out of this prototype and rely on class
    scope. Named and dispatched to explicitly rather than defaulted: a spec that forgot to say
    which rule it wants must be a KeyError, not a silent nothing."""
    return {}


_MODULE_CANDS: dict[str, Callable[[Node, LangCfg], Cands]] = {
    "none": _no_module, "python": _py_module, "js": _js_module,
    "rust": _rust_module, "go": _go_module, "c": _c_module,
}


def module_cands(root: Node, sp: LangSpec, cfg: LangCfg) -> Cands:
    """Every top-level binding this language's reader walks, with the key each one yields.
    Subscripted, never `.get`: a spec with no `module_enum` is a spec nobody finished."""
    return _MODULE_CANDS[sp["module_enum"]](root, cfg)


# --------------------------------------------------------------------------
# Class scope. Member-style languages name state through a receiver (self.x / this.x) and may
# also declare fields; identifier-style languages (Java, C#) reference fields by bare name, so
# the key is the field name itself.
# --------------------------------------------------------------------------

def _field_decl_cands(cls: Node, sp: LangSpec) -> Cands:
    cands: Cands = {}
    owner = state_sites.owner_name(cls)
    for fd in _local_refs(cls, lambda n: n.type in sp["field_decl_types"], sp["class_types"]):
        for name in record_state.field_decl_names(fd):
            _put(cands, (state_sites.DECL_KIND[fd.type], owner, name), sp["key_prefix"] + name)
    return cands


def _member_cands(cls: Node, sp: LangSpec) -> Cands:
    """Receiver-assigned attributes, plus whatever fields the language also declares."""
    cands: Cands = {}
    owner = state_sites.owner_name(cls)
    for n in _local_refs(cls, lambda n: n.type in sp["assign_types"], sp["class_types"]):
        left = _field(n, sp["assign_left"])
        if left is None or left.type not in sp["member_types"]:
            continue
        obj = _field(left, sp["mem_object"])
        attr = _field(left, sp["mem_attr"])
        if obj is None or attr is None or _text(obj) not in sp["this_idents"]:
            continue
        _put(cands, (state_sites.RECEIVER_ATTRIBUTE, owner, _text(attr)), _text(left))
    cands.update(_field_decl_cands(cls, sp))
    return cands


def _self_usage_cands(cls: Node, sp: LangSpec) -> Cands:
    """Rust: the field list is on the struct, but state is used as `self.<field>` in the impl
    (reads and writes), so it is enumerated from that usage and not from the declaration.

    The owner is therefore the impl's type name, and the census names the same site from the
    struct's own name. They agree when the struct and its impl are in one file, which is the
    normal Rust shape, and a struct whose impl is elsewhere is honestly unvisited from here."""
    cands: Cands = {}
    owner = state_sites.rust_impl_owner(cls)
    for m in _local_refs(cls, lambda n: n.type in sp["member_types"], sp["class_types"]):
        obj = _field(m, sp["mem_object"])
        attr = _field(m, sp["mem_attr"])
        if obj is None or attr is None or _text(obj) not in sp["this_idents"]:
            continue
        _put(cands, (state_sites.FIELD_DECLARATION, owner, _text(attr)), _text(m))
    return cands


def _ivar_cands(cls: Node, sp: LangSpec) -> Cands:
    """Ruby: state is `@instance_variables`, a node type of their own with no receiver. Every
    mention counts as a visit, including a read; the census counts only the ones this file
    ASSIGNS, so a read of an ivar written elsewhere drops out of the comparison rather than
    charging this file for another file's slot."""
    cands: Cands = {}
    owner = state_sites.owner_name(cls)
    for iv in _local_refs(cls, lambda n: n.type == "instance_variable", sp["class_types"]):
        _put(cands, (state_sites.INSTANCE_VARIABLE, owner, _text(iv)), _text(iv))
    return cands


def _no_instance(cls: Node, sp: LangSpec) -> Cands:
    """C and Go declare no class this walk enters: C's state is file-scope and struct fields,
    Go's is grouped by receiver type. Both are read elsewhere in this module."""
    return {}


_INSTANCE_CANDS: dict[str, Callable[[Node, LangSpec], Cands]] = {
    "none": _no_instance, "member": _member_cands, "identifier": _field_decl_cands,
    "self_usage": _self_usage_cands, "ruby_ivar": _ivar_cands,
}


def instance_cands(cls: Node, sp: LangSpec) -> Cands:
    """Every declaration inside one class that this language's reader walks."""
    return _INSTANCE_CANDS[sp["instance_enum"]](cls, sp)


def instance_keys(cls: Node, sp: LangSpec) -> list[str]:
    """The state keys one class yields, for the callers that need only the names: reference
    collection, and the record rules asking what another enumerator has already claimed."""
    return keys_of(instance_cands(cls, sp))


# --------------------------------------------------------------------------
# Go, whose state spans methods rather than a class body.
# --------------------------------------------------------------------------

def _go_type_name(typ: Node | None) -> str:
    """The struct type a Go receiver binds to, unwrapping `*T` to `T`."""
    if typ is None:
        return ""
    if typ.type == "pointer_type":
        return _go_type_name(next((c for c in typ.children if c.is_named), None))
    if typ.type == "type_identifier":
        return _text(typ)
    return ""


def _go_receiver(method: Node) -> tuple[str, str]:
    """(receiver type, receiver variable name) for a Go method_declaration."""
    recv = _field(method, "receiver")               # parameter_list `(c *Cache)`
    pd = next((c for c in recv.children if c.is_named), None) if recv is not None else None
    if pd is None:
        return "", ""
    name = _field(pd, "name")
    return _go_type_name(_field(pd, "type")), _text(name)


def go_slots(root: Node) -> list[record_state.Slot]:
    """Go state, grouped by receiver TYPE across all its methods (spec section 4: analyse state
    across the whole type, not one method). A field is `<recv>.<field>` inside a method; the key
    is `<Type>.<field>` so it is stable across methods whose receivers are named differently.

    Every slot here is reached from a USE, so the site's owner is the receiver's type name and
    the census names the same site from the `type_spec` the struct sits under. A field the type
    never touches in any method is not enumerated at all and reads as unvisited, which is the
    truth: nothing in this reading looked at it."""
    by_type: dict[str, list[tuple[Node, str]]] = {}
    for m in _refs(root, lambda n: n.type == "method_declaration"):
        tname, rname = _go_receiver(m)
        if tname and rname:
            by_type.setdefault(tname, []).append((m, rname))

    slots: list[record_state.Slot] = []
    for tname, methods in by_type.items():
        field_refs: dict[str, list[Node]] = {}
        for method, rname in methods:
            for sel in _refs(method, lambda n: n.type == "selector_expression"):
                operand = _field(sel, "operand")
                if operand is not None and operand.type == "identifier" and _text(operand) == rname:
                    field_refs.setdefault(_text(_field(sel, "field")), []).append(sel)
        for field, refs in field_refs.items():
            slots.append({"state": f"{tname}.{field}", "refs": refs, "writers_enumerable": True,
                          "site": (state_sites.FIELD_DECLARATION, tname, field)})
    return slots
