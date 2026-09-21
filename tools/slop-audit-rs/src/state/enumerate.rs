//! State enumeration: which declarations the classifier's reader walks, and what it makes
//! of them. Ported from l1_analyzer.state_enum.
//!
//! This is the classifier's OWN walk, and it is not the census. The census counts
//! declaration sites; this one reaches a conclusion about each. They are kept apart on
//! purpose: a shared enumerator would make the two agree by construction and the gap
//! between them would never open.
//!
//! It used to hand back a list of state keys, the names it decided were state. Everything
//! it looked at and DECLINED, a `const` binding, a plain `static`, a record field nothing
//! references, vanished, and with it the only evidence that the reader had been there at
//! all. That absence is what made the published coverage number wrong: the census counted
//! declaration sites, the classifier counted conclusions, and the ratio of the two called
//! a correctly declined declaration a missed one. A file holding one record of five fields
//! and one module-level `cache = {}` reported six declared, one admitted, and 0.167
//! coverage with nothing missed at all.
//!
//! So every enumerator here returns `Cands`: an ORDERED map from declaration site to the
//! state key that site yields, with the empty string for a site the walk reached and
//! declined. The sites are named in the shared site vocabulary, and that naming is the
//! whole of the correspondence between the two walks.
//!
//! The ordering is why this is a map with insertion order and not a set. The classifier
//! sorts findings on verdict, then whether they decide anything, then file and line, so
//! two states declared on the SAME line tie on every key. A stable sort then preserves
//! whatever order the enumerator handed over, and set iteration order varies between runs:
//! six module maps on one line once serialised in six different orders across six runs of
//! unchanged code. Insertion order here IS source order, because every walk below is
//! pre-order.

use crate::lang_spec::LangSpec;
use crate::nodes::{children, descendants, field, text};
use crate::state::sites::{owner_name, rust_impl_owner, Site, FIELD_DECLARATION, MODULE_BINDING};
use tree_sitter::Node;

/// Declaration site to the state key it yields, empty for a site the walk reached and
/// DECLINED. Ordered: the order is source order, and the classifier's sort depends on it.
///
/// A list of pairs and free functions over it, not a record with methods. The reference
/// holds a plain mapping and reads it with free functions, and a method that reaches its
/// receiver only for data it could have been handed is the shape this instrument counts
/// against the code it audits.
pub type Cands = Vec<(Site, String)>;

/// Record one site the walk reached, keeping the FIRST position and the STRONGEST answer.
///
/// The same site can be reached twice: `x = 0` and `x = 1` at module scope are one binding
/// written twice, and a repeat must not create a second finding. When one visit declines
/// and another admits, the admitting answer wins, because the walk did produce a key for
/// that declaration and reporting it as declined would lose a finding the classifier used
/// to make. Overwriting in place keeps the original position, so source order survives.
pub fn put(cands: &mut Cands, site: Site, key: &str) {
    match cands.iter_mut().find(|(existing, _)| *existing == site) {
        Some((_, held)) if !key.is_empty() => *held = key.to_string(),
        Some(_) => {}
        None => cands.push((site, key.to_string())),
    }
}

/// The state keys the walk admitted, in source order, each one once.
///
/// Two declarations can yield the same key: a TypeScript field `x` and an assignment
/// `this.x` are one slot spelled twice, and the classifier judges the slot once.
pub fn keys_of(cands: &Cands) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for (_, key) in cands {
        if !key.is_empty() && !out.iter().any(|held| held == key) {
            out.push(key.clone());
        }
    }
    out
}

/// Every declaration site that yielded `key`.
///
/// Plural on purpose: when one verdict covers two spellings of one slot, both declarations
/// were judged, and crediting only one would report the other as unread.
pub fn sites_of(cands: &Cands, key: &str) -> Vec<Site> {
    cands.iter().filter(|(_, held)| held == key).map(|(site, _)| site.clone()).collect()
}

/// Every site the walk reached, admitted or declined. This is what the classifier reports
/// as VISITED, and the declined ones are the whole reason it can report anything.
pub fn visited(cands: &Cands) -> Vec<Site> {
    cands.iter().map(|(site, _)| site.clone()).collect()
}

// --------------------------------------------------------------------------
// Module and package scope. Read from the root's own children, so a name bound inside a
// function is a local and never reaches here.
// --------------------------------------------------------------------------

/// The container literal types JavaScript and TypeScript bind writable values with. Taken
/// from the generated language table rather than retyped, so the two cannot drift.
///
/// `container_literal_types`, not `literal_types`. The second is the SCALAR list, strings
/// and numbers and booleans, and reading it here inverted the whole rule: `const LIMIT = 5`
/// read as state and `const CACHE = {}` read as nothing, which is the exact defect this
/// function exists to fix, running backwards.
fn js_containers(sp: &LangSpec) -> &'static [&'static str] {
    sp.container_literal_types
}

/// The one call that makes a value genuinely immutable, and the idiomatic way to write a
/// constant table in these languages. Everything else `new` produces is a fresh object
/// nobody has frozen.
const JS_FREEZE: &str = "Object.freeze";

/// Whether a declarator binds a value that can be written even though the name cannot.
///
/// `const` says the NAME cannot be rebound. It says nothing about the object, and an
/// object literal bound to a const and then written through is exactly unbounded state.
/// This walk declined every const until 2026-09-06, so two files that behave identically
/// at run time got opposite readings off a keyword:
///
/// ```text
/// export let   CACHE = {};  export function put(k, v) { CACHE[k] = v; }   promiscuous
/// export const CACHE = {};  export function put(k, v) { CACHE[k] = v; }   nothing
/// ```
///
/// The second is the one people write. `const` is the default in these languages and `let`
/// is the exception, so the decline took nearly all the real module state out of every
/// JavaScript and TypeScript reading, and took it out as a clean pass rather than as
/// silence. The census had it right in its own words the whole time.
///
/// An over-approximation, deliberately, and in the safe direction. `new Date()` is rarely
/// state anybody cares about and is counted anyway, because the direction that under-counts
/// is the direction that reports clean.
fn js_binds_something_writable(declarator: Node, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(value) = field(Some(declarator), "value") else { return false };
    if js_containers(sp).contains(&value.kind()) {
        return true;
    }
    match value.kind() {
        "new_expression" => true,
        "call_expression" => text(field(Some(value), "function"), src) != JS_FREEZE,
        _ => false,
    }
}

/// Top-level `let` / `var` / `const` declarators, exported or not.
///
/// A const bound to a scalar is DECLINED, not skipped: the walk read the declaration and
/// ruled it out, because a name bound once to a number holds nothing that can be written.
///
/// Through the export statement, for the reason the census gives: an exported declaration
/// sits inside an export statement, almost all module state in these two languages is
/// exported, and a reader walking the file's own children met none of it. The census
/// reported those declarations and this walk visited none of them, which is the honest
/// half of the same defect: it said the state was there and unread rather than absent.
fn js_module(root: Node, sp: &LangSpec, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    for decl in crate::state::census::js_declarations(root) {
        let rebindable = match decl.kind() {
            // The keyword is the first child, named or not, so this reads all of them.
            "lexical_declaration" => children(decl)
                .first()
                .map(|first| text(Some(*first), src) != "const")
                .unwrap_or(true),
            "variable_declaration" => true,
            _ => continue,
        };
        for vd in descendants(decl).into_iter().filter(|n| n.kind() == "variable_declarator") {
            let Some(name) = field(Some(vd), "name") else { continue };
            if name.kind() != "identifier" {
                continue;
            }
            let spelled = text(Some(name), src);
            let is_state = rebindable || js_binds_something_writable(vd, sp, src);
            put(&mut cands, Site::new(MODULE_BINDING, "", spelled.clone()),
                      if is_state { &spelled } else { "" });
        }
    }
    cands
}

/// The types Rust hands out to be written through a shared reference. A static of one of
/// these is mutable state by construction: that is what they are for, and there is nothing
/// to infer from the rest of the declaration.
///
/// Named as bare identifiers and matched anywhere in the type, because the wrapping varies
/// and the wrapper does not change the answer: `Mutex<HashMap<..>>`, `Arc<RwLock<T>>` and
/// `OnceLock<String>` are all reached through the same door.
const RUST_INTERIOR_MUTABILITY: &[&str] = &[
    "AtomicBool", "AtomicI8", "AtomicI16", "AtomicI32", "AtomicI64", "AtomicIsize",
    "AtomicPtr", "AtomicU8", "AtomicU16", "AtomicU32", "AtomicU64", "AtomicUsize",
    "Cell", "LazyCell", "LazyLock", "Mutex", "OnceCell", "OnceLock", "RefCell", "RwLock",
    "UnsafeCell",
];

/// Whether this static holds something the program can change.
///
/// `static mut` was the only shape this reader admitted, and `static mut` is nearly
/// extinct: it requires `unsafe` at every access, so modern Rust holds global state
/// through interior mutability instead. The two shapes that are how it is actually done
/// both read as nothing until 2026-09-06:
///
/// ```text
/// pub static COUNTER: AtomicUsize = AtomicUsize::new(0);
/// pub static CACHE: Mutex<Option<HashMap<String, u64>>> = Mutex::new(None);
/// ```
///
/// The same defect as JavaScript's declined `const`, found the same day, and worse here.
/// There the keyword described the binding rather than the object and the object had to be
/// read. Here the type is not a hint at all: an atomic and a lock exist to be mutated
/// through a shared reference, so a static of that type is mutable state by construction.
///
/// A static that carries none of them is still declined, and that is a reading. A
/// `static NAMES: [&str; 3]` cannot be written through and nothing can change it.
fn rust_static_is_writable(item: Node, src: &[u8]) -> bool {
    if children(item).iter().any(|c| c.kind() == "mutable_specifier") {
        return true;
    }
    let Some(declared) = field(Some(item), "type") else { return false };
    descendants(declared)
        .into_iter()
        .filter(|n| n.is_named())
        .any(|n| RUST_INTERIOR_MUTABILITY.contains(&text(Some(n), src).as_str()))
}

/// Rust `static` items. A static is state when the program can change what it holds;
/// anything else is declined on the merits, which is a reading of it and not a gap in the
/// reader.
fn rust_module(root: Node, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    for st in children(root) {
        if st.kind() != "static_item" {
            continue;
        }
        let Some(name) = field(Some(st), "name") else { continue };
        let spelled = text(Some(name), src);
        let writable = rust_static_is_writable(st, src);
        put(&mut cands, Site::new(MODULE_BINDING, "", spelled.clone()),
                  if writable { &spelled } else { "" });
    }
    cands
}

/// Package-level `var` declarations. `const` is immutable and is not a var declaration, so
/// it never enters the candidate list and the census does not count it either.
fn go_module(root: Node, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    for decl in children(root) {
        if decl.kind() != "var_declaration" {
            continue;
        }
        for vs in descendants(decl).into_iter().filter(|n| n.kind() == "var_spec") {
            let Some(nm) = field(Some(vs), "name") else { continue };
            if nm.kind() == "identifier" {
                let spelled = text(Some(nm), src);
                put(&mut cands, Site::new(MODULE_BINDING, "", spelled.clone()), &spelled);
            }
        }
    }
    cands
}

/// C has no classes: file-scope variable declarations are the only state this walk reads.
/// Function declarations and typedefs declare no slot and never become a candidate.
fn c_module(root: Node, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    for decl in children(root) {
        if decl.kind() != "declaration" {
            continue;
        }
        let parts = children(decl);
        if parts.iter().any(|c| c.kind() == "type_definition") {
            continue;
        }
        for dcl in parts {
            let name = crate::state::census::c_declarator_name(Some(dcl), src);
            if !name.is_empty() {
                put(&mut cands, Site::new(MODULE_BINDING, "", name.clone()), &name);
            }
        }
    }
    cands
}

/// Every top-level binding this language's reader walks, with the key each one yields.
///
/// Dispatched on the language's own declared enumerator name, and refused for a name no
/// arm covers: a row with an enumerator nobody wrote is a row nobody finished, and
/// returning an empty candidate list for it would report a repository the reader never
/// understood as one holding no state.
pub fn module_cands(root: Node, sp: &LangSpec, src: &[u8]) -> Option<Cands> {
    match sp.module_enum {
        // Java, C# and Ruby keep module and static state out of this reader and rely on
        // class scope. An arm of its own rather than a default, because a language whose
        // rule nobody wrote must reach the refusal below and not this empty list.
        "none" => Some(Vec::new()),
        "js" => Some(js_module(root, sp, src)),
        "rust" => Some(rust_module(root, src)),
        "go" => Some(go_module(root, src)),
        "c" => Some(c_module(root, src)),
        // Python's module rule reads the mutability machinery L1.18 also reads, and that
        // is not ported yet. Refused rather than emptied, so the gap is a refusal at the
        // call site and never a clean reading.
        _ => None,
    }
}

// --------------------------------------------------------------------------
// Class scope. Member-style languages name state through a receiver (self.x / this.x) and
// may also declare fields; identifier-style languages reference fields by bare name, so
// the key is the field name itself.
// --------------------------------------------------------------------------

/// Rust: the field list is on the struct, but state is used as `self.<field>` in the impl
/// (reads and writes), so it is enumerated from that usage and not from the declaration.
///
/// The owner is therefore the impl's type name, and the census names the same site from
/// the struct's own name. They agree when the struct and its impl are in one file, which
/// is the normal Rust shape, and a struct whose impl is elsewhere is honestly unvisited
/// from here.
pub fn rust_self_usage_cands(cls: Node, sp: &LangSpec, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    let owner = rust_impl_owner(cls, src);
    for m in local_of_types(cls, sp.member_types, sp.class_types) {
        let (Some(obj), Some(attr)) = (field(Some(m), sp.mem_object), field(Some(m), sp.mem_attr))
        else { continue };
        if !sp.this_idents.contains(&text(Some(obj), src).as_str()) {
            continue;
        }
        put(&mut cands, Site::new(FIELD_DECLARATION, owner.clone(), text(Some(attr), src)),
                  &text(Some(m), src));
    }
    cands
}

/// Nodes of `types` inside `scope`, never inside a record nested within it. A nested
/// record is reached on its own turn and counted against its own owner.
fn local_of_types<'t>(scope: Node<'t>, types: &[&str], stop: &[&str]) -> Vec<Node<'t>> {
    crate::nodes::local_descendants(scope, stop)
        .into_iter()
        .filter(|n| types.contains(&n.kind()))
        .collect()
}

/// The owner name for a record, in the vocabulary both walks share.
pub fn record_owner(record: Node, src: &[u8]) -> String {
    owner_name(Some(record), src)
}

// --------------------------------------------------------------------------
// Class scope. Member-style languages name state through a receiver (self.x / this.x) and
// may also declare fields; identifier-style languages reference fields by bare name, so
// the key is the field name itself.
// --------------------------------------------------------------------------

/// Fields a record DECLARES, for the languages whose fields are named the same way at
/// their uses. The key carries the language's own prefix, so a field referenced by bare
/// name and one referenced through a receiver are not two slots.
fn field_decl_cands(cls: Node, sp: &LangSpec, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    let owner = owner_name(Some(cls), src);
    for fd in local_of_types(cls, sp.field_decl_types, sp.class_types) {
        let Some(kind) = crate::state::sites::decl_kind(fd.kind()) else { continue };
        for name in crate::state::records::field_decl_names(fd, src) {
            let key = format!("{}{name}", sp.key_prefix);
            put(&mut cands, Site::new(kind, owner.clone(), name), &key);
        }
    }
    cands
}

/// Receiver-assigned attributes, plus whatever fields the language also declares.
///
/// Both, because they are two spellings of one slot in these languages: a TypeScript class
/// can declare `x` and assign `this.x`, and counting only one would report the other as a
/// declaration nothing visited.
fn member_cands(cls: Node, sp: &LangSpec, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    let owner = owner_name(Some(cls), src);
    for n in local_of_types(cls, sp.assign_types, sp.class_types) {
        let Some(left) = field(Some(n), sp.assign_left) else { continue };
        if !sp.member_types.contains(&left.kind()) {
            continue;
        }
        let (Some(obj), Some(attr)) =
            (field(Some(left), sp.mem_object), field(Some(left), sp.mem_attr)) else { continue };
        if !sp.this_idents.contains(&text(Some(obj), src).as_str()) {
            continue;
        }
        put(&mut cands,
            Site::new(crate::state::sites::RECEIVER_ATTRIBUTE, owner.clone(),
                      text(Some(attr), src)),
            &text(Some(left), src));
    }
    for (site, key) in field_decl_cands(cls, sp, src) {
        put(&mut cands, site, &key);
    }
    cands
}

/// Ruby: state is `@instance_variables`, a node type of their own with no receiver.
///
/// Every mention counts as a visit, including a READ. The census counts only the ones a
/// file assigns, so a read of an ivar written elsewhere drops out of the comparison rather
/// than charging this file for another file's slot.
fn ivar_cands(cls: Node, sp: &LangSpec, src: &[u8]) -> Cands {
    let mut cands: Cands = Vec::new();
    let owner = owner_name(Some(cls), src);
    for iv in local_of_types(cls, &["instance_variable"], sp.class_types) {
        let spelled = text(Some(iv), src);
        put(&mut cands,
            Site::new(crate::state::sites::INSTANCE_VARIABLE, owner.clone(), spelled.clone()),
            &spelled);
    }
    cands
}

/// Every declaration inside one class that this language's reader walks.
///
/// Dispatched on the language's declared style and refused for a style no arm covers, for
/// the reason the module enumerator gives: an empty candidate list reads as a class
/// holding no state.
pub fn instance_cands(cls: Node, sp: &LangSpec, src: &[u8]) -> Option<Cands> {
    match sp.instance_enum {
        // C and Go declare no class this walk enters: C's state is file scope and struct
        // fields, Go's is grouped by receiver type, and both are read elsewhere here.
        "none" => Some(Vec::new()),
        "member" => Some(member_cands(cls, sp, src)),
        "identifier" => Some(field_decl_cands(cls, sp, src)),
        "self_usage" => Some(rust_self_usage_cands(cls, sp, src)),
        "ruby_ivar" => Some(ivar_cands(cls, sp, src)),
        _ => None,
    }
}

// --------------------------------------------------------------------------
// Go, whose state spans methods rather than a class body.
// --------------------------------------------------------------------------

/// The struct type a Go receiver binds to, unwrapping `*T` to `T`.
///
/// A loop rather than a call to itself: `**T` is one wrapper per star, and the depth is
/// the audited file's business rather than anyone's choice here.
fn go_type_name(typ: Option<Node>, src: &[u8]) -> String {
    let mut current = typ;
    while let Some(t) = current {
        match t.kind() {
            "pointer_type" => current = crate::nodes::first_named(Some(t)),
            "type_identifier" => return text(Some(t), src),
            _ => return String::new(),
        }
    }
    String::new()
}

/// (receiver type, receiver variable name) for a Go method declaration.
fn go_receiver(method: Node, src: &[u8]) -> (String, String) {
    let Some(recv) = field(Some(method), "receiver") else { return (String::new(), String::new()) };
    let Some(pd) = crate::nodes::first_named(Some(recv)) else {
        return (String::new(), String::new());
    };
    (go_type_name(field(Some(pd), "type"), src), text(field(Some(pd), "name"), src))
}

/// One piece of state reached from its uses, with the site both walks name it by.
#[derive(Debug, Clone)]
pub struct Slot {
    pub state: String,
    pub refs: Vec<usize>,
    pub writers_enumerable: bool,
    pub site: Site,
}

/// Go state, grouped by receiver TYPE across all its methods, because the analysis scope
/// is the type and not one method.
///
/// A field is `<recv>.<field>` inside a method, and the key is `<Type>.<field>` so it is
/// stable across methods whose receivers are named differently.
///
/// Every slot here is reached from a USE, so the site's owner is the receiver's type name
/// and the census names the same site from the type declaration the struct sits under. A
/// field the type never touches in any method is not enumerated at all and reads as
/// unvisited, which is the truth: nothing in this reading looked at it.
pub fn go_slots(root: Node, src: &[u8]) -> Vec<Slot> {
    // Insertion-ordered, because the classifier's sort ties for two slots on one line and
    // a stable sort then keeps whatever order arrived here.
    let mut by_type: Vec<(String, Vec<(Node, String)>)> = Vec::new();
    for m in descendants(root).into_iter().filter(|n| n.kind() == "method_declaration") {
        let (tname, rname) = go_receiver(m, src);
        if tname.is_empty() || rname.is_empty() {
            continue;
        }
        match by_type.iter_mut().find(|(held, _)| *held == tname) {
            Some((_, methods)) => methods.push((m, rname)),
            None => by_type.push((tname, vec![(m, rname)])),
        }
    }

    let mut slots = Vec::new();
    for (tname, methods) in by_type {
        let mut field_refs: Vec<(String, Vec<usize>)> = Vec::new();
        for (method, rname) in methods {
            for sel in descendants(method).into_iter()
                .filter(|n| n.kind() == "selector_expression") {
                let Some(operand) = field(Some(sel), "operand") else { continue };
                if operand.kind() != "identifier" || text(Some(operand), src) != rname {
                    continue;
                }
                let name = text(field(Some(sel), "field"), src);
                match field_refs.iter_mut().find(|(held, _)| *held == name) {
                    Some((_, refs)) => refs.push(sel.id()),
                    None => field_refs.push((name, vec![sel.id()])),
                }
            }
        }
        for (name, refs) in field_refs {
            slots.push(Slot {
                state: format!("{tname}.{name}"),
                refs,
                writers_enumerable: true,
                site: Site::new(FIELD_DECLARATION, tname.clone(), name),
            });
        }
    }
    slots
}

/// The candidate sites of every file in scope, keyed by path.
///
/// Scoped exactly as the census is, through the same helper, because the two counts are
/// only comparable over the same set of files. A port that read a different set of FILES
/// and the same sites in each is a different defect from one that read the same files
/// differently, and sharing the scope keeps those two questions apart.
pub fn walk(repo: &std::path::Path, lang: &str)
    -> std::collections::BTreeMap<String, Cands> {
    let mut out = std::collections::BTreeMap::new();
    let Some(sp) = crate::lang_spec::spec_for(lang) else { return out };
    for (rel, tree, src) in crate::state::census::parsed_files(repo, lang) {
        let root = tree.root_node();
        // Both scopes, in the order the classifier reads them: module first, then every
        // class in the file. A file whose module enumerator is not ported contributes
        // nothing at all rather than its classes alone, because a partial reading of a
        // file is the shape that reads as a clean one.
        let Some(mut cands) = module_cands(root, sp, &src) else { continue };
        for cls in descendants(root).into_iter().filter(|n| sp.class_types.contains(&n.kind())) {
            let Some(inner) = instance_cands(cls, sp, &src) else { continue };
            for (site, key) in inner {
                put(&mut cands, site, &key);
            }
        }
        // Go's state spans methods rather than a class body, so its slots are reached
        // here and nowhere else.
        if sp.scope_by_receiver {
            for slot in go_slots(root, &src) {
                put(&mut cands, slot.site, &slot.state);
            }
        }
        out.insert(rel, cands);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lang_spec::spec_for;
    use crate::parser_for;

    fn enumerate(source: &str, lang: &str) -> Cands {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        let tree = parser.parse(&bytes, None).expect("a parse");
        let sp = spec_for(lang).expect("a language row");
        module_cands(tree.root_node(), sp, &bytes).expect("an enumerator for this language")
    }

    fn admitted(source: &str, lang: &str) -> Vec<String> {
        keys_of(&enumerate(source, lang))
    }

    fn reached(source: &str, lang: &str) -> usize {
        visited(&enumerate(source, lang)).len()
    }

    #[test]
    fn a_const_bound_to_a_container_is_state_because_const_binds_the_name_not_the_object() {
        // Two files that behave identically at run time got opposite readings off a
        // keyword until 2026-09-06, and `const` is the DEFAULT in these languages, so the
        // decline took nearly all the real module state out of every reading.
        let source = "export const CACHE = {};\nexport function put(k, v) { CACHE[k] = v; }\n";
        assert_eq!(admitted(source, "javascript"), vec!["CACHE"]);
    }

    #[test]
    fn a_const_bound_to_a_scalar_is_declined_and_the_decline_is_recorded() {
        // Declined, not skipped. The walk read the declaration and ruled it out, and that
        // reading is the only thing that stops the census counting it as a site nobody
        // looked at.
        let cands = enumerate("const LIMIT = 5;\n", "javascript");
        assert!(keys_of(&cands).is_empty(), "{cands:?}");
        assert_eq!(visited(&cands).len(), 1, "the decline must still be a visit");
    }

    #[test]
    fn a_frozen_object_is_not_writable_state() {
        assert!(admitted("const T = Object.freeze({a: 1});\n", "javascript").is_empty());
    }

    #[test]
    fn a_let_binding_is_state_whatever_it_holds_because_the_name_can_be_rebound() {
        assert_eq!(admitted("export let CACHE = 0;\n", "javascript"), vec!["CACHE"]);
    }

    #[test]
    fn a_rust_static_of_an_atomic_is_state_without_the_mut_keyword() {
        // `static mut` is nearly extinct: it needs `unsafe` at every access, so modern
        // Rust holds global state through interior mutability. Both shapes below read as
        // nothing until 2026-09-06.
        let atomic = "pub static COUNTER: AtomicUsize = AtomicUsize::new(0);\n";
        let locked = "pub static CACHE: Mutex<Option<HashMap<String, u64>>> = Mutex::new(None);\n";
        assert_eq!(admitted(atomic, "rust"), vec!["COUNTER"]);
        assert_eq!(admitted(locked, "rust"), vec!["CACHE"]);
    }

    #[test]
    fn the_wrapper_round_an_interior_mutable_type_does_not_change_the_answer() {
        // Matched anywhere in the type, because the wrapping varies and the door is the
        // same: Arc<RwLock<T>> is reached exactly as RwLock<T> is.
        let source = "pub static S: Arc<RwLock<Vec<u8>>> = f();\n";
        assert_eq!(admitted(source, "rust"), vec!["S"]);
    }

    #[test]
    fn a_rust_static_that_cannot_be_written_through_is_declined_and_read() {
        let cands = enumerate("static NAMES: [&str; 3] = [\"a\", \"b\", \"c\"];\n", "rust");
        assert!(keys_of(&cands).is_empty());
        assert_eq!(visited(&cands).len(), 1);
    }

    #[test]
    fn a_rust_static_mut_is_still_state() {
        assert_eq!(admitted("static mut CACHE: i32 = 0;\n", "rust"), vec!["CACHE"]);
    }

    #[test]
    fn a_go_const_never_enters_the_candidate_list() {
        // It is not a var declaration, and the census does not count it either, so the two
        // walks agree about it by reading the same grammar rather than by agreeing to skip.
        let source = "package p\n\nconst LIMIT = 5\n\nvar cache = map[string]int{}\n";
        assert_eq!(admitted(source, "go"), vec!["cache"]);
        assert_eq!(reached(source, "go"), 1);
    }

    #[test]
    fn a_c_function_declaration_declares_no_slot() {
        let source = "static int cache[256];\nvoid put(int k, int v);\n";
        assert_eq!(admitted(source, "c"), vec!["cache"]);
    }

    #[test]
    fn a_site_reached_twice_keeps_its_position_and_the_stronger_answer() {
        // `x = 0` then `x = 1` is one binding written twice. A repeat must not create a
        // second finding, and when one visit declines and another admits, the admitting
        // answer wins: the walk DID produce a key for that declaration.
        let mut cands: Cands = Vec::new();
        put(&mut cands, Site::new(MODULE_BINDING, "", "a"), "");
        put(&mut cands, Site::new(MODULE_BINDING, "", "b"), "b");
        put(&mut cands, Site::new(MODULE_BINDING, "", "a"), "a");
        // `a` keeps the position its FIRST visit gave it, even though that visit declined
        // and the later one admitted. The classifier sorts findings on keys that tie for
        // two states declared on one line, and a stable sort then preserves this order.
        assert_eq!(keys_of(&cands), vec!["a", "b"], "the first visit fixes the position");
        assert_eq!(visited(&cands).len(), 2);
    }

    #[test]
    fn a_declining_visit_never_overwrites_an_admitting_one() {
        let mut cands: Cands = Vec::new();
        put(&mut cands, Site::new(MODULE_BINDING, "", "a"), "a");
        put(&mut cands, Site::new(MODULE_BINDING, "", "a"), "");
        assert_eq!(keys_of(&cands), vec!["a"]);
    }

    #[test]
    fn one_slot_spelled_twice_is_judged_once_and_credits_both_declarations() {
        // Crediting only one would report the other as unread.
        let mut cands: Cands = Vec::new();
        put(&mut cands, Site::new(FIELD_DECLARATION, "Store", "x"), "this.x");
        put(&mut cands, Site::new(super::super::sites::RECEIVER_ATTRIBUTE, "Store", "x"), "this.x");
        assert_eq!(keys_of(&cands), vec!["this.x"]);
        assert_eq!(sites_of(&cands, "this.x").len(), 2);
    }

    #[test]
    fn a_language_whose_enumerator_is_not_ported_is_refused_rather_than_emptied() {
        // An empty candidate list would read as a file holding no state. Python's module
        // rule needs the mutability machinery L1.18 carries, which is not ported yet.
        let mut parser = parser_for("python");
        let bytes = b"cache = {}\n".to_vec();
        let tree = parser.parse(&bytes, None).expect("a parse");
        let sp = spec_for("python").expect("python");
        assert!(module_cands(tree.root_node(), sp, &bytes).is_none());
    }
}
