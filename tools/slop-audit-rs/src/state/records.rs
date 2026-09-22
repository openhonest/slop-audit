//! Reading a slot declared inside a record. Ported from l1_analyzer.record_state.
//!
//! The classifier reaches most state from a USE, and a slot declared once and thereafter
//! only used is spelled one way at its declaration and another at every use. This module
//! owns the declaration half.

use crate::nodes::{field, local_descendants, text};
use tree_sitter::Node;

/// The field carrying the declared name, for declarations that name it directly.
///
/// A C# auto-property is the reason this table exists. The classifier's field vocabulary
/// named `field_declaration` alone, so the same dictionary was read when it was written
/// `Dictionary<string,int> cache;` and invisible when it was written
/// `Dictionary<string,int> Cache { get; set; }`, which is the spelling the language's own
/// style guide asks for on anything public. 678 of Newtonsoft.Json's 1,360 state
/// declarations and 267 of RestSharp's 378 are spelled that way.
fn direct_name_field(node_type: &str) -> Option<&'static str> {
    match node_type {
        "public_field_definition" => Some("name"),    // TypeScript
        "field_definition" => Some("property"),       // JavaScript
        "property_declaration" => Some("name"),       // C#
        _ => None,
    }
}

/// The names declared by one field-declaration node.
///
/// TypeScript, JavaScript and a C# property name the slot directly; a Java or C# field
/// nests one or more declarators, because `int a, b;` is one declaration of two slots.
pub fn field_decl_names(fd: Node, src: &[u8]) -> Vec<String> {
    if let Some(direct) = direct_name_field(fd.kind()) {
        return match field(Some(fd), direct) {
            Some(name) => vec![text(Some(name), src)],
            None => Vec::new(),
        };
    }
    local_descendants(fd, &[])
        .into_iter()
        .filter(|n| n.kind() == "variable_declarator")
        .filter_map(|vd| field(Some(vd), "name").map(|name| text(Some(name), src)))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::nodes::descendants;
    use crate::parser_for;

    fn names(source: &str, lang: &str, node_type: &str) -> Vec<String> {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        let tree = parser.parse(&bytes, None).expect("a parse");
        let fd = descendants(tree.root_node())
            .into_iter()
            .find(|n| n.kind() == node_type)
            .unwrap_or_else(|| panic!("no {node_type} in the fixture"));
        field_decl_names(fd, &bytes)
    }

    #[test]
    fn one_declaration_of_two_slots_yields_two_names() {
        assert_eq!(names("class S { int a, b; }\n", "java", "field_declaration"),
                   vec!["a", "b"]);
    }

    #[test]
    fn a_csharp_auto_property_names_its_slot_directly() {
        // 678 of Newtonsoft.Json's 1,360 state declarations are spelled this way, and the
        // classifier read none of them until this node type was added.
        let source = "class S { public int Cache { get; set; } }\n";
        assert_eq!(names(source, "csharp", "property_declaration"), vec!["Cache"]);
    }

    #[test]
    fn a_typescript_field_names_its_slot_directly() {
        assert_eq!(names("class S { cache: number = 0; }\n", "typescript",
                         "public_field_definition"), vec!["cache"]);
    }

    #[test]
    fn a_javascript_field_names_its_slot_under_a_different_field() {
        // The grammar files it as `property` where TypeScript files it as `name`, which is
        // why the table is keyed by node type rather than shared across the two.
        assert_eq!(names("class S { cache = {}; }\n", "javascript", "field_definition"),
                   vec!["cache"]);
    }
}

// --- the two record rules ---------------------------------------------------------

use crate::lang_spec::LangSpec;
use crate::nodes::children;
use crate::state::sites::{self, Site};
use std::collections::{BTreeMap, BTreeSet};

/// One record-declared state, with everything the classifier needs to judge it.
///
/// `writers_enumerable` is the premise the compositional call-target rule rests on, and it
/// differs between the two record kinds, which is why it travels with the slot rather than
/// being decided once at the call site. A Python class attribute is written by the methods
/// of its own class, so an invoked slot can be proved to hold what was injected. A C struct
/// field has no such boundary: any translation unit that can see the struct can assign a
/// function pointer into it, so a called field is undecidable and must fail closed rather
/// than earn a neutral verdict from a premise that does not hold.
///
/// `site` names the declaration in the census's vocabulary, so the coverage number can say
/// which declared site this verdict is about. The finder is the only thing that knows which
/// record it read the slot out of, and a caller recomputing it from the finding's name would
/// be guessing.
pub struct Slot<'t> {
    pub state: String,
    pub refs: Vec<Node<'t>>,
    pub writers_enumerable: bool,
    pub site: Site,
}

/// What one file's record rules produced, and what they walked to produce it.
///
/// Two outputs rather than one, because a declaration the rule read and declined is not the
/// same fact as a declaration nobody looked at, and a list of slots alone cannot tell them
/// apart. Five typed-dictionary fields nothing references produce no slot at all; they were
/// still read, one by one, and the coverage number is wrong by five without `visited`.
pub struct RecordRead<'t> {
    pub slots: Vec<Slot<'t>>,
    pub visited: Vec<Site>,
}

/// Descendants of `node` whose type is in `types`, never entering a nested record.
///
/// A record nested inside another owns its own fields and is enumerated as its own scope,
/// so the outer walk must stop at it. Without the stop,
/// `struct A { struct B { int x; } b; }` charges A with B's field and the same slot is
/// counted twice.
fn descend<'t>(node: Node<'t>, types: &[&str], stop: &[&str]) -> Vec<Node<'t>> {
    local_descendants(node, stop).into_iter().filter(|n| types.contains(&n.kind())).collect()
}

/// Member accesses indexed by the name they reach for, built once per scope.
///
/// A C header can declare a thousand fields and mention as many members, and rescanning the
/// member list once per field name turns one file into a million string comparisons with a
/// fresh decode inside each one.
fn by_attr<'t>(nodes: Vec<Node<'t>>, attr_field: &str, src: &[u8])
    -> BTreeMap<String, Vec<Node<'t>>> {
    let mut out: BTreeMap<String, Vec<Node<'t>>> = BTreeMap::new();
    for n in nodes {
        out.entry(text(field(Some(n), attr_field), src)).or_default().push(n);
    }
    out
}

/// (name, binding identifier) for each name bound at the top level of a class body.
///
/// Only the body's own statements are read, so a name bound inside a method is a local and
/// never reaches here. A bare annotation (`name: str`) is kept alongside a value-bearing
/// binding: tree-sitter spells both as an assignment, and the two cannot be separated on the
/// merits anyway. `items: list[int]` in a dataclass IS a slot, filled by a generated
/// constructor, and dropping annotations to keep typed-dictionary fields out would drop it
/// too. What keeps a typed-dictionary field out of the findings is that nothing references
/// it.
fn py_class_body_bindings<'t>(cls: Node<'t>, src: &[u8]) -> Vec<(String, Node<'t>)> {
    let mut out = Vec::new();
    let Some(body) = field(Some(cls), "body") else { return out };
    for stmt in children(body).into_iter().filter(|s| s.kind() == "expression_statement") {
        for assign in children(stmt).into_iter().filter(|c| c.kind() == "assignment") {
            if let Some(left) = field(Some(assign), "left") {
                if left.kind() == "identifier" {
                    out.push((text(Some(left), src), left));
                }
            }
        }
    }
    out
}

/// The names a class attribute can be reached through inside its own class: the two
/// receivers, and the class's own name.
///
/// `Store.cache[k] = v` is the spelling that makes a class-body binding shared mutable state
/// rather than a per-instance default, so a rule that matched `self.` alone would enumerate
/// the slot and then find nothing using it.
fn py_receivers(cls: Node, src: &[u8]) -> BTreeSet<String> {
    let mut names: BTreeSet<String> = ["self", "cls"].iter().map(|s| s.to_string()).collect();
    if let Some(name) = field(Some(cls), "name") {
        names.insert(text(Some(name), src));
    }
    names
}

/// Class-body bindings, minus the ones the receiver rule already reports.
///
/// The subtraction is what keeps this additive. A default declared in the class body and
/// rebound per instance (`cache = {}` beside `self.cache = {}`) is ONE slot, and publishing a
/// second finding about it would inflate every count computed over findings without a single
/// new piece of state being read. The receiver rule keeps it, because it was there first and
/// its reference matching is narrower; this rule takes only what nothing else claims.
///
/// Both ways of taking nothing are still a reading, and both are recorded as visited. A
/// binding the receiver rule claimed was walked here and handed over; a binding nothing
/// references was walked here and found to hold no state anything reaches. Neither is a
/// declaration the reader missed.
fn python_class_body<'t, F>(root: Node<'t>, sp: &LangSpec, src: &[u8], already: &F)
    -> RecordRead<'t>
where
    F: Fn(Node<'t>) -> Vec<String>,
{
    let mut slots = Vec::new();
    let mut visited = Vec::new();
    for cls in descend(root, sp.class_types, &[]) {
        let enumerated: BTreeSet<String> = already(cls).into_iter().collect();
        let receivers = py_receivers(cls, src);
        let owner = sites::owner_name(Some(cls), src);
        let members = by_attr(descend(cls, sp.member_types, sp.class_types), sp.mem_attr, src);
        for (name, binding) in py_class_body_bindings(cls, src) {
            let site = Site { kind: sites::CLASS_BODY_BINDING.into(), owner: owner.clone(),
                              name: name.clone() };
            visited.push(site.clone());
            if sp.this_idents.iter().any(|ident| enumerated.contains(&format!("{ident}.{name}"))) {
                continue;
            }
            // The binding site leads the reference list so the binding line sends a reader
            // to the declaration rather than to the first place the name is used.
            let mut refs = vec![binding];
            if let Some(uses) = members.get(&name) {
                refs.extend(uses.iter().copied().filter(|m| {
                    receivers.contains(&text(field(Some(*m), sp.mem_object), src))
                }));
            }
            if refs.len() > 1 {
                slots.push(Slot { state: format!("{owner}.{name}"), refs,
                                  writers_enumerable: true, site });
            }
        }
    }
    RecordRead { slots, visited }
}

const C_RECORDS: &[&str] = &["struct_specifier", "union_specifier"];

/// Declarator wrappers between a field declaration and the name it binds.
///
/// Whitelisted rather than unwrapped by "take the first named child", which would walk into
/// an anonymous member's struct body and return a field of the wrong record as this record's
/// name.
const C_DECLARATORS: &[&str] = &["array_declarator", "pointer_declarator", "function_declarator",
                                 "parenthesized_declarator", "attributed_declarator",
                                 "init_declarator"];

/// The identifier a C field declarator binds. `int cache[256]`, `char *name` and
/// `void (*cb)(int)` each declare one slot, behind one to three wrappers.
///
/// A loop rather than a call to itself: `int ****x` is one wrapper per star and nothing
/// bounds how many a generated header writes.
fn c_field_name(node: Option<Node>, src: &[u8]) -> String {
    let mut current = node;
    while let Some(n) = current {
        if n.kind() == "field_identifier" {
            return text(Some(n), src);
        }
        if !C_DECLARATORS.contains(&n.kind()) {
            return String::new();
        }
        current = field(Some(n), "declarator")
            .or_else(|| children(n).into_iter().find(|c| c.is_named()));
    }
    String::new()
}

/// Struct and union fields, with every same-file member access that names them.
///
/// TWO LIMITS, both real, both consequences of what C does not give a reader. A field has no
/// owner at the point of use: `s->cache` says nothing about which struct `s` is, and
/// resolving it needs type inference this analyzer does not do, so references are matched on
/// the field NAME and a name declared by two records in one file is reported once, against
/// the record that declared it first. And references are collected per file, so a struct
/// declared in a header and used in another translation unit has no same-file reference and
/// nothing is reported for it.
///
/// BOTH LIMITS ARE VISITS, not misses. This walk reaches every field declaration in the file
/// and reads the name off it; what it then fails to do is join that name to a use. So the
/// distance between visited and judged is exactly the cross-unit gap, published rather than
/// folded into a ratio that made it look like a reading failure.
fn c_struct_field<'t>(root: Node<'t>, sp: &LangSpec, src: &[u8]) -> RecordRead<'t> {
    let mut slots = Vec::new();
    let mut visited = Vec::new();
    let mut claimed: BTreeSet<String> = BTreeSet::new();
    let members = by_attr(descend(root, sp.member_types, &[]), sp.mem_attr, src);
    for rec in descend(root, C_RECORDS, &[]) {
        let tag = match field(Some(rec), "name") {
            Some(name) => text(Some(name), src),
            None => format!("struct@{}", rec.start_position().row + 1),
        };
        let owner = sites::owner_name(Some(rec), src);
        for fd in descend(rec, &["field_declaration"], C_RECORDS) {
            for declarator in children(fd) {
                let name = c_field_name(Some(declarator), src);
                if name.is_empty() {
                    continue;
                }
                let site = Site { kind: sites::FIELD_DECLARATION.into(), owner: owner.clone(),
                                  name: name.clone() };
                visited.push(site.clone());
                if claimed.contains(&name) {
                    continue;
                }
                claimed.insert(name.clone());
                if let Some(refs) = members.get(&name) {
                    if !refs.is_empty() {
                        slots.push(Slot { state: format!("{tag}.{name}"), refs: refs.clone(),
                                          writers_enumerable: false, site });
                    }
                }
            }
        }
    }
    RecordRead { slots, visited }
}

/// The record-declared state of one file, with the references that denote it, beside every
/// record declaration the rule walked to find it.
///
/// `already` reports the state keys another enumerator has claimed for a given record, so a
/// finder can stand down rather than double-count.
///
/// Refused for a rule name no arm covers. A language whose record rule nobody wrote would
/// otherwise read no record fields and say nothing about it, which is the silence this
/// module exists to break.
// honest-code-allow: L1.21.13 - `slots` is a STRUCT FIELD, not module state. The reader counts a field written through Rust's init shorthand in one function and read as a local in another as one hidden name shared between them; the reproduction is in slop-audit-qb7. Nothing here is written outside a value the caller is handed back
pub fn slots<'t, F>(root: Node<'t>, sp: &LangSpec, src: &[u8], already: &F)
    -> Option<RecordRead<'t>>
where
    F: Fn(Node<'t>) -> Vec<String>,
{
    match sp.record_enum {
        // A language whose record fields are already reachable from a reference, or that has
        // no record type at all. An arm of its own rather than a default: a spec that forgot
        // to say which rule it wants must reach the refusal below.
        "none" => Some(RecordRead { slots: Vec::new(), visited: Vec::new() }),
        "python_class_body" => Some(python_class_body(root, sp, src, already)),
        "c_struct_field" => Some(c_struct_field(root, sp, src)),
        _ => None,
    }
}
