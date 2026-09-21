//! The state census: a second, independent count of state-bearing declarations. Ported
//! from l1_analyzer.state_census.
//!
//! Every self-disclosure number the classifier publishes is computed over the state the
//! classifier RECOGNIZED, and that denominator cannot see non-enumeration. A struct field
//! the C enumerator does not know about, a file the bucketer set aside, a construct no
//! language row mentions: none of them produce silence, because silence is measured over
//! what was noticed. Zero of zero undecided is nought per cent, so the silence floor
//! structurally cannot fire on a repository the classifier never read, and the card reads
//! maximum confidence off an empty denominator.
//!
//! This module supplies the denominator the classifier cannot supply for itself. It counts
//! DECLARATION SITES straight from the parse tree, and it does so without calling anything
//! on the classifier's recognition path. That independence is the whole design: a shared
//! enumerator would make the two counts agree by construction and the gap would never
//! open.
//!
//! The defect that motivated it, exactly: an unbounded C cache reaches the worst grade
//! when it is written `static int cache[256]` at file scope, and reaches an affirmative
//! "none of the data this code keeps can grow without limit" when the identical array is
//! written `struct Store { int cache[256]; }`, because the C enumerator read file-scope
//! declarations and nothing else. One syntactic level of hiding, five letter grades.
//!
//! What the census is NOT. It is not a better classifier and it issues no verdict about
//! any piece of state. It answers one question, did the analysis look at this code at all,
//! and the only thing it can do to a report is withhold a grade. The count is deliberately
//! crude: it never follows a reference, never resolves a type, and never decides whether
//! the state is bounded.

use crate::nodes::{children, descendants, field, first_named, local_descendants, text};
use crate::state::sites::{
    decl_kind, enclosing_owner, owner_name, Site, CLASS_BODY_BINDING, INSTANCE_VARIABLE,
    MODULE_BINDING, RECEIVER_ATTRIBUTE,
};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use tree_sitter::Node;

/// The declarator wrappers a field declaration can put between itself and the name it
/// binds. `int cache[256]`, `char *name` and `void (*cb)(int)` each declare one slot
/// behind one to three of them.
///
/// Listed rather than unwrapped by "take the first named child", which would walk into an
/// anonymous member's struct body and return another record's field.
///
/// Re-derived here rather than shared with the classifier's side, which unwraps the same
/// wrappers: the census is the second reading, and a shared extractor is a shared blind
/// spot. What the two DO have to agree on is the name they arrive at, because the coverage
/// number is measured by matching those names. That agreement was once missing, and it is
/// what this list fixes: the census named a C field `cache[256]` where the classifier
/// named it `cache`, so every array, pointer and function-pointer field in C read as a
/// declaration nothing had visited. libuv reported 0.582 visited on that defect and
/// reports 0.928 without it.
const DECLARATOR_WRAPPERS: &[&str] = &[
    "array_declarator", "pointer_declarator", "function_declarator",
    "parenthesized_declarator", "attributed_declarator", "init_declarator",
];

/// The name-carrying field of a field declaration, tried in order.
const FIELD_NAME_FIELDS: &[&str] = &["name", "property", "declarator"];

/// Every node of one of `types` under `root`, `root` included.
fn of_type<'t>(root: Node<'t>, types: &[&str]) -> Vec<Node<'t>> {
    descendants(root).into_iter().filter(|n| types.contains(&n.kind())).collect()
}

/// Nodes of `types` belonging to `scope` itself, never to a record or declaration nested
/// inside it. A nested one is reached on its own turn and counted against its own owner.
fn own<'t>(scope: Node<'t>, types: &[&str], stop: &[&str]) -> Vec<Node<'t>> {
    local_descendants(scope, stop).into_iter().filter(|n| types.contains(&n.kind())).collect()
}

/// The identifier a name-ish declaration node binds, past any declarator wrappers.
///
/// A loop rather than a call to itself: one wrapper per star, and nothing bounds how many
/// a generated header writes.
fn bound_name(node: Option<Node>, src: &[u8]) -> String {
    let mut current = node;
    while let Some(n) = current {
        if !DECLARATOR_WRAPPERS.contains(&n.kind()) {
            return text(Some(n), src);
        }
        current = field(Some(n), "declarator").or_else(|| first_named(Some(n)));
    }
    String::new()
}

/// The name the first present name-ish field of a declaration node binds.
fn named_field(node: Node, names: &[&str], src: &[u8]) -> String {
    for name in names {
        if let Some(found) = field(Some(node), name) {
            return bound_name(Some(found), src);
        }
    }
    String::new()
}

/// One language's field-declaration vocabulary: the declaration node types, the name node
/// types, the declarator node types, and the record node types that can own one.
struct Fields {
    decl: &'static [&'static str],
    names: &'static [&'static str],
    declarators: &'static [&'static str],
    records: &'static [&'static str],
}

/// Every language in the table spells "a slot declared inside a record type" with its own
/// node. Rust and Go fields are enumerated from usage by the classifier and counted here,
/// which is exactly the gap the census exists to show.
fn fields_of(lang: &str) -> Option<Fields> {
    let row = match lang {
        // C: the case the census exists for. A struct or union field was invisible to the
        // classifier until it learned record fields, and it is still invisible when the
        // struct is declared in a header and used elsewhere, which the census counts and
        // the classifier cannot reach.
        "c" => Fields { decl: &["field_declaration"], names: &["field_identifier"],
                        declarators: &[],
                        records: &["struct_specifier", "union_specifier"] },
        "rust" => Fields { decl: &["field_declaration"], names: &["field_identifier"],
                           declarators: &[], records: &["struct_item", "union_item"] },
        // The owner is the `type_spec` the struct sits under, not the anonymous
        // `struct_type` itself: the classifier reaches a Go field from a method receiver
        // and can name only the type. An inline struct bound to no named type has no
        // type_spec and is unmatchable.
        "go" => Fields { decl: &["field_declaration"], names: &["field_identifier"],
                         declarators: &[], records: &["type_spec"] },
        // Every body a field can be declared in, not just a class: an interface constant
        // and an enum field are declaration sites too, and with only class_declaration
        // listed they got no owner at all. A site with no owner cannot be matched against
        // a walk that names one, so it read as unvisited whether or not anything had
        // looked at it.
        "java" => Fields { decl: &["field_declaration"], names: &[],
                           declarators: &["variable_declarator"],
                           records: &["class_declaration", "interface_declaration",
                                      "enum_declaration", "record_declaration",
                                      "annotation_type_declaration"] },
        // C# properties hold state as surely as fields do, and the classifier's field
        // vocabulary named only field_declaration, so an auto-property was state nobody
        // counted until it was added.
        "csharp" => Fields { decl: &["field_declaration", "property_declaration"],
                             names: &["identifier"], declarators: &["variable_declarator"],
                             records: &["class_declaration", "record_declaration",
                                        "struct_declaration", "interface_declaration",
                                        "enum_declaration"] },
        "typescript" => Fields { decl: &["public_field_definition"], names: &[],
                                 declarators: &[], records: &["class_declaration"] },
        "javascript" => Fields { decl: &["field_definition"], names: &[],
                                 declarators: &[], records: &["class_declaration"] },
        "python" => Fields { decl: &[], names: &[], declarators: &[],
                             records: &["class_definition"] },
        "ruby" => Fields { decl: &[], names: &[], declarators: &[],
                           records: &["class", "module"] },
        _ => return None,
    };
    Some(row)
}

fn field_sites(root: Node, lang: &str, src: &[u8]) -> Vec<Site> {
    let Some(row) = fields_of(lang) else { return Vec::new() };
    if row.decl.is_empty() {
        return Vec::new();
    }
    let mut sites = Vec::new();
    for fd in of_type(root, row.decl) {
        let owner = enclosing_owner(fd, row.records, src);
        // Bounded at the next record or the next declaration, so a declaration only ever
        // names its OWN slots. An anonymous member forced this: C spells
        // `union { int b; int c; };` as a field declaration wrapping a union whose members
        // are field declarations of their own, and an unbounded name walk read b and c off
        // the wrapper as well as off themselves. libuv counted 1,345 field declarations
        // that way, and the wrapper duplicates were sites nothing could ever visit,
        // because they were attributed to the outer struct while the fields belong to the
        // union. The double count inflated the denominator and read as a hole in the
        // reader.
        let mut inner: Vec<&str> = row.records.to_vec();
        inner.extend_from_slice(row.decl);
        let mut declared: Vec<String> = if row.declarators.is_empty() {
            Vec::new()
        } else {
            own(fd, row.declarators, &inner)
                .into_iter()
                .map(|d| named_field(d, &["name"], src))
                .collect()
        };
        if declared.is_empty() {
            let direct = named_field(fd, FIELD_NAME_FIELDS, src);
            declared = if direct.is_empty() {
                own(fd, row.names, &inner).into_iter().map(|n| text(Some(n), src)).collect()
            } else {
                vec![direct]
            };
        }
        // A field declaration with no record around it is not a field declaration. Every
        // grammar here produces the node only inside a record body, so an ownerless one is
        // the parser recovering from something it could not read: in libuv, 255
        // macro-prefixed function prototypes parsed as top-level field declarations and
        // were counted as places the code keeps data. They inflated the denominator by a
        // fifth, and every one read as a declaration nothing had visited, which is a
        // reading failure the reader never committed.
        if !owner.is_empty() {
            let kind = decl_kind(fd.kind());
            if let Some(kind) = kind {
                for name in declared.into_iter().filter(|n| !n.is_empty()) {
                    sites.push(Site::new(kind, owner.clone(), name));
                }
            }
        }
    }
    sites
}

/// One language's receiver-assignment vocabulary: state that is never declared, only
/// assigned, which is how Python and untyped JavaScript spell it.
struct Receiver {
    assigns: &'static [&'static str],
    lvalue: &'static str,
    members: &'static [&'static str],
    object: &'static str,
    attribute: &'static str,
    receivers: &'static [&'static str],
    records: &'static [&'static str],
}

fn receiver_of(lang: &str) -> Option<Receiver> {
    match lang {
        "python" => Some(Receiver {
            assigns: &["assignment"], lvalue: "left", members: &["attribute"],
            object: "object", attribute: "attribute", receivers: &["self", "cls"],
            records: &["class_definition"] }),
        "javascript" | "typescript" => Some(Receiver {
            assigns: &["assignment_expression"], lvalue: "left",
            members: &["member_expression"], object: "object", attribute: "property",
            receivers: &["this"], records: &["class_declaration"] }),
        // Ruby names instance state with a node type of its own and no receiver, so the
        // member-access shape does not apply and it is counted by `ruby_ivar_sites`.
        // The other five declare no receiver assignment at all.
        _ => None,
    }
}

fn receiver_sites(root: Node, lang: &str, src: &[u8]) -> Vec<Site> {
    let Some(row) = receiver_of(lang) else { return Vec::new() };
    let mut sites = Vec::new();
    for assign in of_type(root, row.assigns) {
        let Some(left) = field(Some(assign), row.lvalue) else { continue };
        if !row.members.contains(&left.kind()) {
            continue;
        }
        let Some(obj) = field(Some(left), row.object) else { continue };
        if !row.receivers.contains(&text(Some(obj), src).as_str()) {
            continue;
        }
        if let Some(attr) = field(Some(left), row.attribute) {
            sites.push(Site::new(RECEIVER_ATTRIBUTE,
                                 enclosing_owner(assign, row.records, src),
                                 text(Some(attr), src)));
        }
    }
    sites
}

/// Ruby instance variables, counted where they are ASSIGNED. A read of an ivar never
/// written in this file is state declared elsewhere, and counting it here would charge one
/// file for another file's slot.
fn ruby_ivar_sites(root: Node, src: &[u8]) -> Vec<Site> {
    let mut sites = Vec::new();
    for assign in of_type(root, &["assignment", "operator_assignment"]) {
        if let Some(left) = field(Some(assign), "left") {
            if left.kind() == "instance_variable" {
                sites.push(Site::new(INSTANCE_VARIABLE,
                                     enclosing_owner(assign, &["class", "module"], src),
                                     text(Some(left), src)));
            }
        }
    }
    sites
}

/// Python module-level bindings, plus class-body attributes. Both are state whose lifetime
/// is the process, and neither is a local.
fn py_toplevel(root: Node, src: &[u8]) -> Vec<Site> {
    let mut sites = Vec::new();
    for stmt in &children(root) {
        if stmt.kind() != "expression_statement" {
            continue;
        }
        for assign in of_type(*stmt, &["assignment"]) {
            if let Some(left) = field(Some(assign), "left") {
                if left.kind() == "identifier" {
                    sites.push(Site::new(MODULE_BINDING, "", text(Some(left), src)));
                }
            }
        }
    }
    for cls in of_type(root, &["class_definition"]) {
        let owner = owner_name(Some(cls), src);
        let Some(body) = field(Some(cls), "body") else { continue };
        for stmt in children(body) {
            if stmt.kind() != "expression_statement" {
                continue;
            }
            for assign in of_type(stmt, &["assignment"]) {
                if let Some(left) = field(Some(assign), "left") {
                    if left.kind() == "identifier" {
                        sites.push(Site::new(CLASS_BODY_BINDING, owner.clone(),
                                             text(Some(left), src)));
                    }
                }
            }
        }
    }
    sites
}

const JS_DECLARATIONS: &[&str] = &["lexical_declaration", "variable_declaration"];

/// Every declaration at a module's top level, whether or not it is handed out.
///
/// An exported declaration is an export statement with the declaration inside it, so a
/// reader walking the file's own children never meets it. Almost all module state in these
/// two languages is exported; a module that keeps something and never exports it keeps it
/// for itself, which is the rarer case and the only one this reader could once see. The
/// census's own fixture for this site had no export in front of it, so nothing here ever
/// exercised the gap: a fixture that supplies the property under test proves nothing.
///
/// `export default CACHE` is not reached and must not be. It hands out a binding declared
/// somewhere else and declares nothing itself, so following it would count that binding
/// twice.
pub fn js_declarations<'t>(root: Node<'t>) -> Vec<Node<'t>> {
    let mut out = Vec::new();
    for child in children(root) {
        if JS_DECLARATIONS.contains(&child.kind()) {
            out.push(child);
        } else if child.kind() == "export_statement" {
            out.extend(children(child).into_iter()
                       .filter(|c| JS_DECLARATIONS.contains(&c.kind())));
        }
    }
    out
}

/// Top-level `let` / `var` / `const` declarators, exported or not. `const` is included
/// where the classifier excludes it: a const binding to a mutable object is state, and the
/// census asks what was declared, not what can be reassigned.
fn js_toplevel(root: Node, src: &[u8]) -> Vec<Site> {
    let mut sites = Vec::new();
    for decl in js_declarations(root) {
        for vd in of_type(decl, &["variable_declarator"]) {
            if let Some(name) = field(Some(vd), "name") {
                if name.kind() == "identifier" {
                    sites.push(Site::new(MODULE_BINDING, "", text(Some(name), src)));
                }
            }
        }
    }
    sites
}

/// Rust `static` items, all of them. Whether the program can change what one holds is a
/// verdict about the state, which the classifier issues and the census does not.
///
/// The classifier declined every static without the `mut` keyword until 2026-09-06, and
/// this count is what said so: it reported the declarations while the classifier visited
/// them and returned nothing, which is how the blindness was measurable rather than
/// invisible.
fn rust_toplevel(root: Node, src: &[u8]) -> Vec<Site> {
    let mut sites = Vec::new();
    for st in children(root) {
        if st.kind() != "static_item" {
            continue;
        }
        let name = named_field(st, &["name"], src);
        if !name.is_empty() {
            sites.push(Site::new(MODULE_BINDING, "", name));
        }
    }
    sites
}

fn go_toplevel(root: Node, src: &[u8]) -> Vec<Site> {
    let mut sites = Vec::new();
    for decl in children(root) {
        if decl.kind() != "var_declaration" {
            continue;
        }
        for spec in of_type(decl, &["var_spec"]) {
            if let Some(name) = field(Some(spec), "name") {
                sites.push(Site::new(MODULE_BINDING, "", text(Some(name), src)));
            }
        }
    }
    sites
}

fn c_toplevel(root: Node, src: &[u8]) -> Vec<Site> {
    let mut sites = Vec::new();
    for decl in children(root) {
        if decl.kind() != "declaration" {
            continue;
        }
        let parts = children(decl);
        // A typedef declares a type, not a slot.
        if parts.iter().any(|c| c.kind() == "type_definition") {
            continue;
        }
        for child in parts {
            let name = c_declarator_name(Some(child), src);
            if !name.is_empty() {
                sites.push(Site::new(MODULE_BINDING, "", name));
            }
        }
    }
    sites
}

/// The identifier a C declarator binds, unwrapping init, array and pointer declarators.
/// Nothing for a FUNCTION declarator, which declares a function and not a variable, and
/// nothing for any other node.
///
/// The function refusal is what keeps a prototype out of the count. `UV_EXTERN void
/// uv_mutex_unlock(uv_mutex_t*);` is a top-level declaration whose declarator is a
/// function declarator, and reading a name off it would report 255 of libuv's prototypes
/// as places the code keeps data.
///
/// Note this is NOT the wrapper list above. That list unwraps a field declaration's name
/// and includes function_declarator, because `void (*cb)(int)` IS a slot; this one refuses
/// it, because at file scope the same node is a function. Two rules, two lists, and
/// collapsing them into one was the first thing this port got wrong.
pub fn c_declarator_name(node: Option<Node>, src: &[u8]) -> String {
    let Some(n) = node else { return String::new() };
    match n.kind() {
        "identifier" => text(Some(n), src),
        "function_declarator" => String::new(),
        "init_declarator" | "array_declarator" | "pointer_declarator" => {
            c_declarator_name(field(Some(n), "declarator"), src)
        }
        _ => String::new(),
    }
}

/// Every declaration site one parsed file spells, as a set. A site named twice in one file
/// is one place state is kept.
///
/// Java, C# and Ruby have no module scope worth counting: their state is fields and
/// instance variables, both counted above.
pub fn file_sites(root: Node, lang: &str, src: &[u8]) -> BTreeSet<Site> {
    let mut sites = field_sites(root, lang, src);
    sites.extend(receiver_sites(root, lang, src));
    sites.extend(match lang {
        "python" => py_toplevel(root, src),
        "javascript" | "typescript" => js_toplevel(root, src),
        "rust" => rust_toplevel(root, src),
        "go" => go_toplevel(root, src),
        "c" => c_toplevel(root, src),
        "java" | "csharp" | "ruby" => Vec::new(),
        _ => Vec::new(),
    });
    if lang == "ruby" {
        sites.extend(ruby_ivar_sites(root, src));
    }
    sites.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser_for;

    fn census(source: &str, lang: &str) -> BTreeSet<Site> {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        let tree = parser.parse(&bytes, None).expect("a parse");
        file_sites(tree.root_node(), lang, &bytes)
    }

    fn names(sites: &BTreeSet<Site>) -> Vec<String> {
        let mut out: Vec<String> = sites.iter().map(|s| s.name.clone()).collect();
        out.sort();
        out
    }

    #[test]
    fn the_case_the_census_exists_for_is_counted_in_both_spellings() {
        // The same array, one syntactic level of hiding apart. The classifier reads one
        // and not the other; the census must read both, or the hiding works.
        let at_file_scope = census("static int cache[256];\n", "c");
        let in_a_record = census("struct Store { int cache[256]; };\n", "c");
        assert_eq!(names(&at_file_scope), vec!["cache"]);
        assert_eq!(names(&in_a_record), vec!["cache"]);
    }

    #[test]
    fn a_c_field_is_named_the_way_the_classifier_names_it() {
        // Past every declarator wrapper. The census once said `cache[256]` where the
        // classifier said `cache`, so every array, pointer and function-pointer field in C
        // read as a declaration nothing had visited: libuv reported 0.582 visited on that
        // defect and 0.928 without it.
        let sites = census(
            "struct S { int cache[256]; char *name; void (*cb)(int); };\n", "c");
        assert_eq!(names(&sites), vec!["cache", "cb", "name"]);
    }

    #[test]
    fn an_anonymous_member_is_not_counted_twice() {
        // C spells this as a field declaration wrapping a union whose members are field
        // declarations of their own. An unbounded name walk read b and c off the wrapper
        // as well as off themselves, and the wrapper copies were sites nothing could ever
        // visit, because they were charged to the outer struct.
        let sites = census("struct S { int a; union { int b; int c; }; };\n", "c");
        assert_eq!(names(&sites), vec!["a", "b", "c"]);
    }

    #[test]
    fn a_field_declaration_with_no_record_around_it_is_not_a_field_declaration() {
        // A macro-prefixed prototype parses as a top-level field declaration. In libuv 255
        // of them inflated the denominator by a fifth, and every one read as a declaration
        // nothing had visited: a reading failure the reader never committed.
        let sites = census("UV_EXTERN void uv_mutex_unlock(uv_mutex_t*);\n", "c");
        assert!(sites.is_empty(), "{sites:?}");
    }

    #[test]
    fn an_exported_declaration_is_reached() {
        // Almost all module state in these languages is exported, and the census's own
        // fixture had no export in front of it, so nothing ever exercised the gap.
        let sites = census("export const CACHE = new Map();\n", "javascript");
        assert_eq!(names(&sites), vec!["CACHE"]);
    }

    #[test]
    fn a_default_export_of_an_existing_binding_declares_nothing() {
        // It hands out a binding declared elsewhere. Following it would count that binding
        // twice.
        let sites = census("const CACHE = new Map();\nexport default CACHE;\n", "javascript");
        assert_eq!(names(&sites), vec!["CACHE"]);
    }

    #[test]
    fn a_rust_static_is_counted_whether_or_not_it_is_mutable() {
        // Whether the program can change what one holds is a verdict, and the census
        // issues none. The classifier declined every non-mut static until 2026-09-06, and
        // this count is what made the blindness measurable.
        let sites = census("static mut CACHE: i32 = 0;\nstatic LIMIT: i32 = 5;\n", "rust");
        assert_eq!(names(&sites), vec!["CACHE", "LIMIT"]);
    }

    #[test]
    fn a_python_class_body_binding_is_not_a_module_binding() {
        let sites = census("LIMIT = 5\n\nclass Store:\n    cache = {}\n", "python");
        let mut kinds: Vec<(&str, String)> =
            sites.iter().map(|s| (s.kind, s.name.clone())).collect();
        kinds.sort();
        assert_eq!(kinds, vec![(CLASS_BODY_BINDING, "cache".to_string()),
                               (MODULE_BINDING, "LIMIT".to_string())]);
    }

    #[test]
    fn a_receiver_assignment_is_state_nobody_declared() {
        let sites = census(
            "class Store:\n    def __init__(self):\n        self.cache = {}\n", "python");
        let site = sites.iter().find(|s| s.kind == RECEIVER_ATTRIBUTE).expect("the attribute");
        assert_eq!((site.owner.as_str(), site.name.as_str()), ("Store", "cache"));
    }

    #[test]
    fn a_ruby_ivar_is_counted_where_it_is_written_and_not_where_it_is_read() {
        // Counting a read would charge this file for a slot another file declares.
        let written = census("class Store\n  def put(v)\n    @cache = v\n  end\nend\n", "ruby");
        let read = census("class Store\n  def get\n    @cache\n  end\nend\n", "ruby");
        assert_eq!(names(&written), vec!["@cache"]);
        assert!(read.is_empty(), "{read:?}");
    }

    #[test]
    fn a_csharp_auto_property_holds_state_as_surely_as_a_field() {
        // The classifier's field vocabulary named only field_declaration, so this was
        // state nobody counted.
        let sites = census(
            "class Store { public System.Collections.Generic.Dictionary<string, int> Cache { get; set; } }\n",
            "csharp");
        assert!(names(&sites).contains(&"Cache".to_string()), "{sites:?}");
    }

    #[test]
    fn a_java_field_is_named_through_its_declarator() {
        let sites = census("class Store { int cache = 0; }\n", "java");
        let site = sites.iter().next().expect("the field");
        assert_eq!((site.owner.as_str(), site.name.as_str()), ("Store", "cache"));
    }

    #[test]
    fn a_java_interface_constant_is_counted_by_neither_side_and_this_is_the_reference() {
        // The Java grammar spells it `constant_declaration`, which is not in the field
        // vocabulary, so the census does not count it. The reference agrees, and parity is
        // what this port owes first, so the behaviour is matched rather than improved.
        //
        // It is still a gap. An interface constant holding a mutable collection is state,
        // and neither walk sees it, which means the census cannot report the classifier's
        // blindness to it either. Filed as slop-audit-18a.
        let sites = census("interface Limits { int MAX = 5; }\n", "java");
        assert!(sites.is_empty(), "the reference counts none of these: {sites:?}");
    }

    #[test]
    fn a_name_bound_inside_a_function_is_a_local_and_never_reaches_the_census() {
        let sites = census("def f():\n    cache = {}\n    return cache\n", "python");
        assert!(sites.is_empty(), "{sites:?}");
    }

    #[test]
    fn a_site_spelled_twice_in_one_file_is_one_place_state_is_kept() {
        let sites = census(
            "class Store:\n    def a(self):\n        self.cache = {}\n    def b(self):\n        self.cache = {}\n",
            "python");
        assert_eq!(sites.len(), 1, "{sites:?}");
    }
}

/// The declaration sites of every file in scope, keyed by the path the classifier reports
/// its findings against.
///
/// Keyed per file, not merged, because the site names are only unique within one file: two
/// files can each declare `Store.cache`, and merging them would count one site where two
/// exist and would let a visit to either one cover both.
///
/// The scope is production without conformance, the same one the reference walks: test
/// trees and conformance tables are excluded, and no scope may decline a vendored tree or
/// machine output, because neither is anybody's code here whatever the question.
pub fn walk(repo: &Path, lang: &str) -> BTreeMap<String, BTreeSet<Site>> {
    parsed_files(repo, lang)
        .into_iter()
        .map(|(rel, tree, src)| (rel, file_sites(tree.root_node(), lang, &src)))
        .collect()
}

/// Every file in scope, parsed, with the path the classifier reports findings against.
///
/// Shared by both walks. They must read the same FILES or their counts are not comparable,
/// and a port that scoped them separately would make a scoping difference look like a
/// reading difference, which is the one confusion the census exists to prevent.
///
/// The scope is production without conformance, the same the reference walks: test trees
/// and conformance tables are excluded, and no scope may decline a vendored tree or
/// machine output, because neither is anybody's code here whatever the question.
pub fn parsed_files(repo: &Path, lang: &str) -> Vec<(String, tree_sitter::Tree, Vec<u8>)> {
    let Some(cfg) = crate::lang::cfg(lang) else { return Vec::new() };
    let has_packages = crate::repo_has_packages(repo);
    // What the project itself says is not part of it. Without this the port read two
    // generated bindings in a gitignored build file as state this repository keeps, and a
    // 262 MB disowned tree elsewhere once carried the only unbounded state in a whole
    // measurement.
    let disowned = crate::ignored_paths(repo);
    let mut parser = crate::parser_for(lang);
    let mut out = Vec::new();
    for entry in crate::walk_repo(repo) {
        let path = entry.path();
        if !crate::is_file_entry(&entry) {
            continue;
        }
        let Some(ext) = path.extension().and_then(|e| e.to_str()) else { continue };
        if !cfg.extensions.contains(&format!(".{}", ext.to_lowercase()).as_str()) {
            continue;
        }
        if crate::bucket_reason(path, repo, has_packages, CENSUS_IGNORE).is_some() {
            continue;
        }
        if path.canonicalize().map(|p| disowned.contains(&p)).unwrap_or(false) {
            continue;
        }
        let Ok(src) = std::fs::read(path) else { continue };
        let Some(tree) = parser.parse(&src, None) else { continue };
        let rel = path.strip_prefix(repo).unwrap_or(path).to_string_lossy().into_owned();
        out.push((rel, tree, src));
    }
    out
}

/// The directory names the census scope removes beyond the vendored ones, matching the
/// reference's production-without-conformance. A conformance table is append-only
/// scaffolding and test doubles, so it is production for neither the state meters nor the
/// god-file count: nobody hand-piles logic into one.
const CENSUS_IGNORE: &[&'static str] = &["tests", "test", "conformance"];
