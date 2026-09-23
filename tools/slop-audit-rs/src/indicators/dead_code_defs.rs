//! What each language calls a definition, and which of them a syntactic scan may judge.
//! Ported from l1_analyzer.dead_code_defs.
//!
//! Nine collectors. Each walks one grammar's top level and hands back every named definition
//! with a status: a CANDIDATE the reference scan may call dead if nothing names it, an
//! UNDECIDABLE the scan must not judge because something outside its reach can name it, or an
//! EXCLUDED the language or a runner binds by convention.
//!
//! The undecidable status is the load-bearing one. Every definition a language or a framework
//! can reach by a route this reader cannot follow is listed with the reason and left OUT of
//! the numerator, so the published ratio is a lower bound and the undecidable share is
//! disclosed beside it. A dead-code pass that guesses in this region reports its own blind
//! spot as a defect in somebody's code.

use crate::nodes::{children, field, text};
use tree_sitter::Node;

/// The scan may call this dead if nothing in the repository names it.
pub const CANDIDATE: &str = "candidate";
/// Something outside this reader's reach can name it, so the scan must not judge it.
pub const UNDECIDABLE: &str = "undecidable";
/// The language or a runner binds it by convention, so it is not a finding either way.
pub const EXCLUDED: &str = "excluded";

/// One named definition and everything the classifier needs to judge it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Definition {
    pub name: String,
    pub kind: &'static str,
    pub line: usize,
    pub end_line: usize,
    pub start_byte: usize,
    pub end_byte: usize,
    pub status: &'static str,
    pub reason: String,
}

/// Repository-level facts a single file cannot answer for itself.
#[derive(Debug, Clone, Default)]
pub struct RepoFacts {
    pub rust_is_library: bool,
    pub js_entry_files: std::collections::BTreeSet<String>,
    pub ruby_metaprogramming: String,
}

fn named_child_of_type<'t>(node: Node<'t>, types: &[&str]) -> Option<Node<'t>> {
    children(node).into_iter().find(|c| c.is_named() && types.contains(&c.kind()))
}

fn named_children<'t>(node: Node<'t>) -> Vec<Node<'t>> {
    children(node).into_iter().filter(|c| c.is_named()).collect()
}

fn mk(name_node: Node, item: Node, kind: &'static str, status: &'static str, reason: &str,
      src: &[u8]) -> Definition {
    Definition {
        name: text(Some(name_node), src),
        kind,
        line: item.start_position().row + 1,
        end_line: item.end_position().row + 1,
        start_byte: item.start_byte(),
        end_byte: item.end_byte(),
        status,
        reason: reason.to_string(),
    }
}

/// A name of the form `__x__`, which the interpreter binds.
fn is_dunder(name: &str) -> bool {
    name.len() > 4 && name.starts_with("__") && name.ends_with("__")
        && name[2..name.len() - 2].chars().all(|c| c.is_alphanumeric() || c == '_')
        && !name[2..name.len() - 2].is_empty()
}

/// Names a Python runner calls by convention, never by an import.
///
/// `test_x` and `TestX` are collected by the test runners; `pytest_x` is a plugin hook looked
/// up by name; the setup and teardown pair is the older fixture protocol. Found on a
/// repository where two plugin hooks are the whole point of a shipped module and this pass
/// called them dead.
fn is_python_runner_name(name: &str) -> bool {
    if name.starts_with("test_") || name.starts_with("pytest_") {
        return true;
    }
    if let Some(rest) = name.strip_prefix("Test") {
        if rest.starts_with(|c: char| c.is_ascii_uppercase() || c == '_') {
            return true;
        }
    }
    matches!(name, "setup_module" | "setup_function" | "teardown_module" | "teardown_function")
}

/// The names a module-level `__all__` lists, which are its declared public surface.
fn python_all_exports(root: Node, src: &[u8]) -> std::collections::BTreeSet<String> {
    for stmt in named_children(root) {
        let assign = if stmt.kind() == "assignment" {
            Some(stmt)
        } else {
            named_child_of_type(stmt, &["assignment"])
        };
        let Some(assign) = assign else { continue };
        if text(field(Some(assign), "left"), src) != "__all__" {
            continue;
        }
        let Some(right) = field(Some(assign), "right") else { continue };
        return named_children(right).into_iter()
            .filter(|s| s.kind().contains("string"))
            .map(|s| text(Some(s), src).trim_matches(['"', '\'']).to_string())
            .collect();
    }
    std::collections::BTreeSet::new()
}

fn python(root: Node, src: &[u8], _relpath: &str, _facts: &RepoFacts) -> Vec<Definition> {
    let exports = python_all_exports(root, src);
    let mut out = Vec::new();
    let mut add = |name_node: Option<Node>, item: Node, kind: &'static str, decorated: bool| {
        let Some(name_node) = name_node else { return };
        let name = text(Some(name_node), src);
        let d = if is_dunder(&name) {
            mk(name_node, item, kind, EXCLUDED, "dunder name bound by the interpreter", src)
        } else if is_python_runner_name(&name) {
            mk(name_node, item, kind, EXCLUDED, "test-runner or pytest plugin hook name", src)
        } else if decorated {
            mk(name_node, item, kind, UNDECIDABLE,
               "decorated (a decorator can register the name with a framework)", src)
        } else if exports.contains(&name) {
            mk(name_node, item, kind, UNDECIDABLE, "exported via __all__", src)
        } else {
            mk(name_node, item, kind, CANDIDATE, "", src)
        };
        out.push(d);
    };

    for stmt in named_children(root) {
        let (node, decorated) = if stmt.kind() == "decorated_definition" {
            match field(Some(stmt), "definition") {
                Some(inner) => (inner, true),
                None => continue,
            }
        } else {
            (stmt, false)
        };
        match node.kind() {
            "function_definition" => add(field(Some(node), "name"), node, "function", decorated),
            "class_definition" => add(field(Some(node), "name"), node, "class", decorated),
            "expression_statement" => {
                if let Some(assign) = named_child_of_type(node, &["assignment"]) {
                    if let Some(left) = field(Some(assign), "left") {
                        if left.kind() == "identifier" {
                            add(Some(left), node, "constant", false);
                        }
                    }
                }
            }
            _ => {}
        }
    }
    out
}

/// The item kinds Rust's top level declares.
const RUST_ITEMS: &[(&str, &str)] = &[
    ("function_item", "function"), ("struct_item", "type"), ("enum_item", "type"),
    ("union_item", "type"), ("trait_item", "trait"), ("type_item", "type"),
    ("const_item", "constant"), ("static_item", "constant"),
];
const RUST_NAME_TYPES: &[&str] = &["identifier", "type_identifier"];

/// The attribute attached to an item, read from the preceding sibling.
///
/// A Rust attribute is a sibling of the item it decorates, not a parent, so a derive, a
/// linkage attribute and a procedural macro attribute are only visible by looking back.
fn rust_attribute_before(item: Node, src: &[u8]) -> String {
    let mut prev = item.prev_named_sibling();
    while let Some(p) = prev {
        if !matches!(p.kind(), "line_comment" | "block_comment") {
            break;
        }
        prev = p.prev_named_sibling();
    }
    match prev {
        Some(p) if p.kind() == "attribute_item" => text(Some(p), src),
        _ => String::new(),
    }
}

fn rust(root: Node, src: &[u8], _relpath: &str, facts: &RepoFacts) -> Vec<Definition> {
    let mut out = Vec::new();
    // A worklist rather than a call to itself. A module holds a module, and how deep a crate
    // nests them is the audited file's business. A module's items are spliced in WHERE THE
    // MODULE STOOD, not appended after its siblings, so the definitions come back in the
    // order they were written.
    let mut work: std::collections::VecDeque<Node> = named_children(root).into();
    while let Some(item) = work.pop_front() {
        if item.kind() == "mod_item" {
            if let Some(body) = field(Some(item), "body") {
                if !rust_attribute_before(item, src).replace(' ', "").contains("cfg(test)") {
                    for (i, child) in named_children(body).into_iter().enumerate() {
                        work.insert(i, child);
                    }
                }
            }
            continue;
        }
        let Some(kind) = crate::lang_spec::lookup(RUST_ITEMS, item.kind()) else { continue };
        let Some(name_node) = named_child_of_type(item, RUST_NAME_TYPES) else { continue };
        let name = text(Some(name_node), src);
        let attribute = rust_attribute_before(item, src);
        let is_pub = named_child_of_type(item, &["visibility_modifier"]).is_some();
        out.push(if name == "main" {
            mk(name_node, item, kind, EXCLUDED, "crate entry point", src)
        } else if !attribute.is_empty() {
            let first = attribute.lines().next().unwrap_or("").to_string();
            mk(name_node, item, kind, UNDECIDABLE,
               &format!("carries the attribute {first}"), src)
        } else if is_pub && facts.rust_is_library {
            mk(name_node, item, kind, UNDECIDABLE,
               "public item of a library crate (may be used by a dependent crate)", src)
        } else {
            mk(name_node, item, kind, CANDIDATE, "", src)
        });
    }
    out
}

/// A Go name a test runner calls by convention.
fn is_go_entry(name: &str) -> bool {
    for prefix in ["Test", "Benchmark", "Example", "Fuzz"] {
        if let Some(rest) = name.strip_prefix(prefix) {
            if rest.starts_with(|c: char| c.is_ascii_uppercase() || c == '_') {
                return true;
            }
        }
    }
    false
}

fn go_package(root: Node, src: &[u8]) -> String {
    match named_child_of_type(root, &["package_clause"]) {
        Some(clause) => text(named_child_of_type(clause, &["package_identifier"]), src),
        None => String::new(),
    }
}

fn go(root: Node, src: &[u8], _relpath: &str, _facts: &RepoFacts) -> Vec<Definition> {
    let package = go_package(root, src);
    let mut out = Vec::new();
    let mut add = |name_node: Option<Node>, item: Node, kind: &'static str| {
        let Some(name_node) = name_node else { return };
        let name = text(Some(name_node), src);
        let exported = name.chars().next().is_some_and(|c| c.is_uppercase());
        out.push(if matches!(name.as_str(), "main" | "init" | "_") || is_go_entry(&name) {
            mk(name_node, item, kind, EXCLUDED, "runtime or test-runner entry point", src)
        } else if exported && package != "main" {
            mk(name_node, item, kind, UNDECIDABLE,
               "exported identifier of an importable package (may be used by another module)",
               src)
        } else {
            mk(name_node, item, kind, CANDIDATE, "", src)
        });
    };

    for item in named_children(root) {
        match item.kind() {
            "function_declaration" => add(field(Some(item), "name"), item, "function"),
            "type_declaration" => {
                for spec in named_children(item) {
                    add(named_child_of_type(spec, &["type_identifier"]), item, "type");
                }
            }
            "var_declaration" | "const_declaration" => {
                for spec in named_children(item) {
                    add(named_child_of_type(spec, &["identifier"]), item, "constant");
                }
            }
            _ => {}
        }
    }
    out
}

// --- Java and C#: one shape, two spellings -----------------------------------------

/// What one JVM-family grammar calls a type, a member and a body.
struct MemberCfg {
    types: &'static [&'static str],
    members: &'static [(&'static str, &'static str)],
    annotation_types: &'static [&'static str],
}

const JAVA_CFG: MemberCfg = MemberCfg {
    types: &["class_declaration", "interface_declaration", "enum_declaration",
             "record_declaration"],
    members: &[("method_declaration", "method"), ("field_declaration", "field")],
    annotation_types: &["annotation", "marker_annotation"],
};

const CSHARP_CFG: MemberCfg = MemberCfg {
    types: &["class_declaration", "interface_declaration", "struct_declaration",
             "enum_declaration", "record_declaration"],
    members: &[("method_declaration", "method"), ("field_declaration", "field"),
               ("property_declaration", "property")],
    annotation_types: &["attribute_list"],
};

/// Members the serialisation runtime reads by name through reflection.
///
/// Nothing in the source references them, which is exactly why they read as dead.
const JVM_RUNTIME_MEMBERS: &[&str] = &["serialVersionUID", "serialPersistentFields",
                                       "readObject", "writeObject", "readObjectNoData",
                                       "readResolve", "writeReplace"];

/// Every modifier keyword on a declaration, in either grammar's spelling. Java groups them
/// under one node; C# emits one node each.
fn modifier_text(node: Node, src: &[u8]) -> String {
    named_children(node).into_iter()
        .filter(|c| matches!(c.kind(), "modifiers" | "modifier"))
        .map(|c| text(Some(c), src))
        .collect::<Vec<_>>()
        .join(" ")
}

/// True for a C# static class holding extension methods.
///
/// An extension method is called on its receiver, so the class that declares it is never
/// named at any call site and reads as unreferenced. All ten of one corpus repository's
/// unreferenced-type findings were extension containers, every one in daily use.
///
/// Both spellings count: the classic modified first parameter, and the newer member block,
/// which the grammar parses as a constructor named `extension`.
fn is_extension_container(node: Node, src: &[u8]) -> bool {
    if !modifier_text(node, src).contains("static") {
        return false;
    }
    let Some(body) = named_child_of_type(node, &["declaration_list"]) else { return false };
    for member in named_children(body) {
        if member.kind() == "constructor_declaration"
            && text(named_child_of_type(member, &["identifier"]), src) == "extension" {
            return true;
        }
        let Some(params) = field(Some(member), "parameters") else { continue };
        let Some(first) = named_children(params).into_iter().next() else { continue };
        if children(first).into_iter().any(|c| text(Some(c), src) == "this") {
            return true;
        }
    }
    false
}

/// The first annotation or attribute on a declaration.
///
/// An annotated member is reachable through a framework, an injection, a serialiser or a
/// test runner, that no syntactic scan can follow, so it is undecidable rather than dead.
fn annotation_on(node: Node, annotation_types: &[&str], src: &[u8]) -> String {
    for child in named_children(node) {
        if annotation_types.contains(&child.kind()) {
            return text(Some(child), src).lines().next().unwrap_or("").to_string();
        }
        if child.kind() == "modifiers" {
            for inner in named_children(child) {
                if annotation_types.contains(&inner.kind()) {
                    return text(Some(inner), src).lines().next().unwrap_or("").to_string();
                }
            }
        }
    }
    String::new()
}

fn member_name<'t>(node: Node<'t>) -> Option<Node<'t>> {
    if node.kind() == "field_declaration" {
        if let Some(declarator) = named_child_of_type(node, &["variable_declarator"]) {
            return named_child_of_type(declarator, &["identifier"])
                .or_else(|| field(Some(declarator), "name"));
        }
    }
    field(Some(node), "name").or_else(|| named_child_of_type(node, &["identifier"]))
}

/// A worklist rather than a call to itself. A type holds a type, and how deep a file nests
/// them is its own business. Each item carries whether it sits inside a type, which is the
/// one thing the recursion passed down, and a container's children are spliced in where the
/// container stood so the definitions come back in the order they were written.
fn member_language(cfg: &MemberCfg, root: Node, src: &[u8]) -> Vec<Definition> {
    let mut out = Vec::new();
    let mut work: std::collections::VecDeque<(Node, bool)> =
        named_children(root).into_iter().map(|c| (c, false)).collect();
    while let Some((child, inside_type)) = work.pop_front() {
        if cfg.types.contains(&child.kind()) {
            if let Some(name_node) = field(Some(child), "name") {
                let annotation = annotation_on(child, cfg.annotation_types, src);
                out.push(if !annotation.is_empty() {
                    mk(name_node, child, "type", UNDECIDABLE,
                       &format!("annotated {annotation} (framework-reachable)"), src)
                } else if is_extension_container(child, src) {
                    mk(name_node, child, "type", UNDECIDABLE,
                       "extension-method container (dispatched on the receiver's type, so the \
                        class name never appears at a call site)", src)
                } else if modifier_text(child, src).contains("public") {
                    mk(name_node, child, "type", UNDECIDABLE,
                       "public type (may be consumed outside the repository)", src)
                } else {
                    mk(name_node, child, "type", CANDIDATE, "", src)
                });
            }
            for (i, c) in named_children(child).into_iter().enumerate() {
                work.insert(i, (c, true));
            }
        } else if inside_type && crate::lang_spec::lookup(cfg.members, child.kind()).is_some() {
            let kind = crate::lang_spec::lookup(cfg.members, child.kind())
                .expect("the row that just matched");
            let Some(name_node) = member_name(child) else { continue };
            let name = text(Some(name_node), src);
            let annotation = annotation_on(child, cfg.annotation_types, src);
            let modifiers = modifier_text(child, src);
            out.push(if name == "main" || name == "Main" {
                mk(name_node, child, kind, EXCLUDED, "program entry point", src)
            } else if JVM_RUNTIME_MEMBERS.contains(&name.as_str()) {
                mk(name_node, child, kind, EXCLUDED,
                   "read by the serialization runtime through reflection", src)
            } else if !annotation.is_empty() {
                mk(name_node, child, kind, UNDECIDABLE,
                   &format!("annotated {annotation} (framework-reachable)"), src)
            } else if modifiers.contains("private") {
                mk(name_node, child, kind, CANDIDATE, "", src)
            } else {
                mk(name_node, child, kind, UNDECIDABLE,
                   "non-private member (may be overridden or dispatched through an interface)",
                   src)
            });
        } else {
            for (i, c) in named_children(child).into_iter().enumerate() {
                work.insert(i, (c, inside_type));
            }
        }
    }
    out
}

// --- TypeScript and JavaScript -----------------------------------------------------

const JS_DECLS: &[(&str, &str)] = &[
    ("function_declaration", "function"), ("generator_function_declaration", "function"),
    ("class_declaration", "class"), ("interface_declaration", "interface"),
    ("type_alias_declaration", "type"), ("enum_declaration", "enum"),
    ("abstract_class_declaration", "class"),
];
const JS_NAME_TYPES: &[&str] = &["identifier", "type_identifier"];

fn js(root: Node, src: &[u8], relpath: &str, facts: &RepoFacts) -> Vec<Definition> {
    let is_entry = facts.js_entry_files.contains(relpath);
    let mut out = Vec::new();

    let add = |name_node: Option<Node>, item: Node, kind: &'static str, exported: bool,
                   default: bool, out: &mut Vec<Definition>| {
        let Some(name_node) = name_node else { return };
        out.push(if default {
            mk(name_node, item, kind, UNDECIDABLE,
               "default export (an importer binds it under any name)", src)
        } else if exported && is_entry {
            mk(name_node, item, kind, UNDECIDABLE,
               "named in package.json as a package entry point", src)
        } else {
            mk(name_node, item, kind, CANDIDATE, "", src)
        });
    };

    let declaration = |node: Node, exported: bool, default: bool, item: Node,
                           out: &mut Vec<Definition>| {
        if let Some(kind) = crate::lang_spec::lookup(JS_DECLS, node.kind()) {
            let name = field(Some(node), "name")
                .or_else(|| named_child_of_type(node, JS_NAME_TYPES));
            add(name, item, kind, exported, default, out);
        } else if matches!(node.kind(), "lexical_declaration" | "variable_declaration") {
            for declarator in named_children(node) {
                if declarator.kind() != "variable_declarator" {
                    continue;
                }
                if let Some(name_node) = field(Some(declarator), "name") {
                    if name_node.kind() == "identifier" {
                        add(Some(name_node), item, "variable", exported, default, out);
                    }
                }
            }
        }
    };

    for stmt in named_children(root) {
        if stmt.kind() == "export_statement" {
            let default = children(stmt).into_iter().any(|c| text(Some(c), src) == "default");
            if let Some(inner) = field(Some(stmt), "declaration") {
                declaration(inner, true, default, stmt, &mut out);
            }
        } else {
            declaration(stmt, false, false, stmt, &mut out);
        }
    }
    out
}

// --- C -----------------------------------------------------------------------------

/// Descend a C declarator to the identifier it names.
///
/// Takes the absence, because a declaration with no declarator is what a broken parse
/// produces. Named apart from the state analysis's declarator reader, which answers a
/// different question: this one descends THROUGH a function declarator to reach the
/// function's name, because a definition is what this is enumerating; that one refuses a
/// function declarator, because a function is not a state binding.
fn c_declared_identifier<'t>(node: Option<Node<'t>>) -> Option<Node<'t>> {
    let mut current = node;
    while let Some(n) = current {
        if n.kind() == "identifier" {
            return Some(n);
        }
        match field(Some(n), "declarator") {
            Some(next) => current = Some(next),
            None => return named_child_of_type(n, &["identifier"]),
        }
    }
    None
}

fn c(root: Node, src: &[u8], _relpath: &str, _facts: &RepoFacts) -> Vec<Definition> {
    let mut out = Vec::new();
    for item in named_children(root) {
        let (name_node, kind) = match item.kind() {
            "function_definition" =>
                (c_declared_identifier(field(Some(item), "declarator")), "function"),
            "declaration" => {
                let declarator = named_child_of_type(item, &["init_declarator"]);
                (declarator.and_then(|d| c_declared_identifier(Some(d))), "variable")
            }
            _ => continue,
        };
        let Some(name_node) = name_node else { continue };
        let is_static = named_children(item).into_iter()
            .any(|c| c.kind() == "storage_class_specifier" && text(Some(c), src) == "static");
        let name = text(Some(name_node), src);
        out.push(if name == "main" {
            mk(name_node, item, kind, EXCLUDED, "program entry point", src)
        } else if is_static {
            mk(name_node, item, kind, CANDIDATE, "", src)
        } else {
            mk(name_node, item, kind, UNDECIDABLE,
               "external linkage (may be called from a translation unit outside this \
                repository)", src)
        });
    }
    out
}

// --- Ruby --------------------------------------------------------------------------

const RUBY_HOOKS: &[&str] = &["initialize", "method_missing", "respond_to_missing?", "to_s",
                              "to_str", "inspect", "each", "call", "==", "<=>", "coerce",
                              "hash", "eql?", "included", "extended", "inherited"];

/// Top-level methods, classes, modules and constants only.
///
/// A method defined inside a class is deliberately not analysed: Ruby dispatches it on a
/// receiver whose type is not known statically, so an unreferenced name inside a class is not
/// evidence of anything. The repository-level metaprogramming gate decides whether even this
/// much is publishable.
fn ruby(root: Node, src: &[u8], _relpath: &str, _facts: &RepoFacts) -> Vec<Definition> {
    let mut out = Vec::new();
    for item in named_children(root) {
        match item.kind() {
            "method" | "singleton_method" => {
                let Some(name_node) = field(Some(item), "name") else { continue };
                let hook = RUBY_HOOKS.contains(&text(Some(name_node), src).as_str());
                out.push(mk(name_node, item, "method",
                            if hook { EXCLUDED } else { CANDIDATE },
                            if hook { "interpreter hook method" } else { "" }, src));
            }
            "class" | "module" => {
                if let Some(name_node) = field(Some(item), "name") {
                    let kind = if item.kind() == "class" { "class" } else { "module" };
                    out.push(mk(name_node, item, kind, CANDIDATE, "", src));
                }
            }
            "assignment" => {
                if let Some(left) = field(Some(item), "left") {
                    if left.kind() == "constant" {
                        out.push(mk(left, item, "constant", CANDIDATE, "", src));
                    }
                }
            }
            _ => {}
        }
    }
    out
}

/// The definitions one language's top level declares, or nothing where this reader has no
/// collector for it.
///
/// Refused rather than emptied: a language with no collector finds no definitions, which
/// reads exactly like a file that declares none.
pub fn collect(root: Node, lang: &str, relpath: &str, facts: &RepoFacts,
               src: &[u8]) -> Option<Vec<Definition>> {
    match lang {
        "python" => Some(python(root, src, relpath, facts)),
        "rust" => Some(rust(root, src, relpath, facts)),
        "go" => Some(go(root, src, relpath, facts)),
        "java" => Some(member_language(&JAVA_CFG, root, src)),
        "csharp" => Some(member_language(&CSHARP_CFG, root, src)),
        "typescript" | "javascript" => Some(js(root, src, relpath, facts)),
        "c" => Some(c(root, src, relpath, facts)),
        "ruby" => Some(ruby(root, src, relpath, facts)),
        _ => None,
    }
}

/// Every definition the collectors find in the production files of one repository, for the
/// parity dump.
///
/// The repository facts are handed in, because two of the three are answers a single file
/// cannot give and the third is a refusal about the whole tree.
pub fn walk(repo: &std::path::Path, lang: &str, facts: &RepoFacts)
    -> Vec<(String, Definition)> {
    let (parsed, _skipped) = crate::indicators::dead_code_grammars::parsed_files(repo, lang);
    let mut out = Vec::new();
    for (rel, tree, src) in parsed {
        if tree.root_node().has_error() {
            continue;
        }
        if let Some(found) = collect(tree.root_node(), lang, &rel, facts, &src) {
            out.extend(found.into_iter().map(|d| (rel.clone(), d)));
        }
    }
    out
}
