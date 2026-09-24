//! L1.18, the mutable-state ratio: the share of functions that reference unbounded external
//! mutable state. Ported from l1_analyzer.mutable_state.
//!
//! THERE IS NO I/O BOUNDARY EXCLUSION, and its absence is the point. The canon promised to
//! exclude route handlers, database adapters and CLI entry points. What was implemented was a
//! comment marker a function had to carry, which fired on no repository that had not adopted
//! this project's private marker. Doing it by analysis was investigated across seven local
//! trees and the pinned corpus and cannot be done: a route-handler decorator list reaches
//! 7.2% of production functions locally and 0% of the corpus, and "database adapter" has no
//! syntactic signature at all. So the claim is dropped rather than faked, and the consequence
//! is disclosed: L1.18 is inflated by the whole I/O layer of every codebase it measures, and
//! always was.
//!
//! THE RATIO IS BOUND-AWARE. State whose reaching set the finite-testability classifier could
//! bound does not count, because a literal-keyed read against a closed set is exhaustively
//! testable and an unbounded accumulator is not. Reusing the classifier rather than writing a
//! second boundedness rule is deliberate: two rules for one concept drift, and the ratio
//! would then contradict the classifier printed beside it on the same panel.

use crate::lang_cfg::LangCfg;
use crate::nodes::{children, descendants, field, text};
use crate::state::bounds;
use crate::state::partition::NEUTRAL;
use crate::{band, lang, Indicator};
use std::collections::BTreeSet;
use std::path::Path;
use tree_sitter::Node;

/// Body node types that hold a function's statements, across all grammars.
const BODY_NODE_TYPES: &[&str] = &["block", "compound_statement", "body", "function_body",
                                   "body_statement", "statement_block"];

/// Constructors of MUTABLE containers whose empty form seeds an accumulator.
///
/// frozenset, tuple and bytes are immutable and cannot accumulate, so they are excluded:
/// `X = frozenset()` is a constant, not mutable state.
const PY_CONTAINER_CTORS: &[&str] = &["dict", "list", "set", "defaultdict", "OrderedDict",
                                      "deque", "Counter", "bytearray"];

/// Java wraps its modifiers in one node and C# repeats one per word; splitting the text of
/// either on whitespace reads both without a per-grammar branch.
const MODIFIER_TYPES: &[&str] = &["modifiers", "modifier"];

/// The declarator forms a C file-scope declaration can carry. Written out rather than probed
/// at runtime, so a form nobody listed is a missing row here and not a silent omission.
const C_DECLARATORS: &[&str] = &["identifier", "init_declarator", "array_declarator",
                                 "pointer_declarator", "function_declarator"];

/// A pure type expression: a bare name, a dotted name, a subscript, or a `|` union of those.
/// No call, no container literal.
fn py_is_type_expression(n: Node, src: &[u8]) -> bool {
    if matches!(n.kind(), "identifier" | "attribute" | "subscript") {
        return true;
    }
    if n.kind() == "binary_operator" {
        let op = field(Some(n), "operator");
        if text(op, src) != "|" {
            return false;
        }
        return match (field(Some(n), "left"), field(Some(n), "right")) {
            (Some(left), Some(right)) => py_is_type_expression(left, src)
                && py_is_type_expression(right, src),
            _ => false,
        };
    }
    false
}

/// Whether this binding declares a type rather than holding a value.
///
/// The call form is here because the expression rule declines anything with a call in it, and
/// `TypedDict("Panel", {...})` is a call that returns a type. The class form of the same
/// declaration was never counted, so one declaration read two ways depending on which syntax
/// spelled it.
fn py_is_type_alias(node: Node, rhs: Option<Node>, type_ctors: &[&str], src: &[u8]) -> bool {
    if let Some(annot) = field(Some(node), "type") {
        let spelling = text(Some(annot), src);
        if spelling.split('[').next().unwrap_or("").trim() == "TypeAlias" {
            return true;
        }
    }
    if let Some(rhs) = rhs {
        if rhs.kind() == "call" {
            if let Some(func) = field(Some(rhs), "function") {
                if type_ctors.contains(&text(Some(func), src).as_str()) {
                    return true;
                }
            }
        }
        return py_is_type_expression(rhs, src);
    }
    false
}

/// An accumulator seed: `{}`, `[]`, or a mutable container constructor with no elements.
fn py_is_empty_container(rhs: Option<Node>, src: &[u8]) -> bool {
    let Some(rhs) = rhs else { return false };
    let named = |n: Node| children(n).into_iter().any(|c| c.is_named());
    match rhs.kind() {
        "dictionary" | "list" => !named(rhs),
        "call" => {
            let func = field(Some(rhs), "function");
            let args = field(Some(rhs), "arguments");
            match func {
                Some(f) if f.kind() == "identifier"
                    && PY_CONTAINER_CTORS.contains(&text(Some(f), src).as_str()) => {
                    match args {
                        None => true,
                        Some(a) => !named(a),
                    }
                }
                _ => false,
            }
        }
        _ => false,
    }
}

/// Top-level assignments, allowing one wrapper: Python nests `x = 0` inside an expression
/// statement, so the assignment node is a child of a root child.
///
/// It defines WHICH declarations the module scan considers. The scan reports only the names it
/// judges mutable, and the coverage number needs the ones it judged and declined as well: a
/// binding the reader walked and ruled out is read, not missed.
pub fn shallow_candidates<'t>(root: Node<'t>, assign_types: &[&str]) -> Vec<Node<'t>> {
    let mut out = Vec::new();
    for node in children(root) {
        if assign_types.contains(&node.kind()) {
            out.push(node);
        } else {
            out.extend(children(node).into_iter().filter(|c| assign_types.contains(&c.kind())));
        }
    }
    out
}

/// Field-based module-global detection for Python.
///
/// The binding name is read from the assignment's own target field, so string literals and
/// annotation tails are never scanned as source. Type aliases are skipped. An uppercase name
/// is a constant by convention, unless it is seeded with an empty container, which is an
/// accumulator (`CACHE = {}`), the pattern the indicator exists to catch.
fn module_mutables_python(root: Node, cfg: &LangCfg, src: &[u8]) -> BTreeSet<String> {
    let mut mutables = BTreeSet::new();
    for node in shallow_candidates(root, cfg.module_level_assign) {
        // Skip subscripts, tuples and attributes.
        let Some(left) = field(Some(node), "left") else { continue };
        if left.kind() != "identifier" {
            continue;
        }
        let name = text(Some(left), src);
        // Dunders are module metadata, not state.
        if cfg.this_ident.contains(&name.as_str())
            || (name.starts_with("__") && name.ends_with("__")) {
            continue;
        }
        let rhs = field(Some(node), "right");
        if py_is_type_alias(node, rhs, cfg.type_constructors, src) {
            continue;
        }
        let upper = !name.is_empty()
            && name.chars().any(|c| c.is_alphabetic())
            && name.chars().filter(|c| c.is_alphabetic()).all(|c| c.is_uppercase());
        if upper {
            if py_is_empty_container(rhs, src) {
                mutables.insert(name);
            }
        } else {
            mutables.insert(name);
        }
    }
    mutables
}

/// Rust-style: a top-level binding is mutable state only where its declaration carries a
/// `mut` specifier. The name is the declaration's identifier child, read structurally so the
/// type token is never mistaken for the name. `const` and plain `static` are excluded.
fn module_mutables_by_specifier(root: Node, cfg: &LangCfg, src: &[u8]) -> BTreeSet<String> {
    let mut mutables = BTreeSet::new();
    for node in shallow_candidates(root, cfg.module_level_assign) {
        if !children(node).into_iter().any(|c| c.kind() == "mutable_specifier") {
            continue;
        }
        if let Some(name) = children(node).into_iter().find(|c| c.kind() == "identifier") {
            let spelling = text(Some(name), src);
            if !spelling.is_empty() {
                mutables.insert(spelling);
            }
        }
    }
    mutables
}

/// Every node of these types at any depth. Used only for class fields, which is why it is not
/// the general candidate collector: a deep walk over a language's whole assignment vocabulary
/// would harvest function locals as module state.
fn deep_nodes<'t>(root: Node<'t>, node_types: &[&str]) -> Vec<Node<'t>> {
    descendants(root).into_iter().filter(|n| node_types.contains(&n.kind())).collect()
}

/// The modifier words on a field declaration.
fn declared_modifiers(decl: Node, src: &[u8]) -> BTreeSet<String> {
    let mut words = BTreeSet::new();
    for child in children(decl) {
        if MODIFIER_TYPES.contains(&child.kind()) {
            words.extend(text(Some(child), src).split_whitespace().map(|w| w.to_string()));
        }
    }
    words
}

/// Java and C#: mutable state is every field not declared final, readonly or const.
///
/// The old scan reached root children and one level below, and a field sits at root, class
/// declaration, class body, field declaration, so no field ever entered the candidate set; and
/// it required an `=` on the line, so `private int total;` was invisible even at the right
/// depth. This walks to any depth for field-declaration nodes ONLY, which is what keeps method
/// locals out: both languages list a local declaration type among their assignment types, and
/// a deep walk over that vocabulary would count every local as external state.
///
/// Mutability is read from the declared modifiers rather than guessed from the name's casing,
/// because both languages have a keyword for the property and it is already in the source.
fn module_mutables_class_fields(root: Node, cfg: &LangCfg, src: &[u8]) -> BTreeSet<String> {
    let mut mutables = BTreeSet::new();
    for decl in deep_nodes(root, cfg.field_decl_types) {
        if declared_modifiers(decl, src).iter()
            .any(|w| cfg.immutable_modifiers.contains(&w.as_str())) {
            continue;
        }
        // A PROPERTY WITH NO SETTER CANNOT BE REASSIGNED, which is what `readonly` says about
        // a field. C# spells the same fact two ways and the modifier check above reads one.
        if !is_settable(decl) {
            continue;
        }
        for spelling in declared_names(decl, src) {
            if !cfg.this_ident.contains(&spelling.as_str()) {
                mutables.insert(spelling);
            }
        }
    }
    mutables
}

/// Whether this declaration can be assigned after the object exists.
///
/// True for anything with no accessor list, which is every field in both languages and every
/// construct in every other language that reaches here. A C# property declares its accessors,
/// so it is the one shape that can answer no. `init` is not a setter: an init-only property
/// can be set while the object is being built and never again, which is what `readonly` means
/// for a field.
fn is_settable(decl: Node) -> bool {
    let lists: Vec<Node> = children(decl).into_iter()
        .filter(|c| c.kind() == "accessor_list").collect();
    if lists.is_empty() {
        return true;
    }
    lists.into_iter().any(|list| children(list).into_iter()
        .any(|accessor| children(accessor).into_iter().any(|c| c.kind() == "set")))
}

/// Every name one field or property declaration binds.
///
/// A field carries its names in `variable_declarator` children, one per name, because a single
/// declaration may bind several. A C# property has no declarator at all and carries its one
/// name in its own `name` field, which is why reading only declarators counted no
/// auto-property: `public int Count { get; set; }` is state by any definition and was state
/// nobody counted.
fn declared_names(decl: Node, src: &[u8]) -> Vec<String> {
    let mut declared: Vec<String> = Vec::new();
    for vd in deep_nodes(decl, &["variable_declarator"]) {
        let named = field(Some(vd), "name")
            .or_else(|| children(vd).into_iter().find(|c| c.kind() == "identifier"));
        if let Some(named) = named {
            declared.push(text(Some(named), src));
        }
    }
    if !declared.is_empty() {
        return declared;
    }
    field(Some(decl), "name").map(|named| vec![text(Some(named), src)]).unwrap_or_default()
}

/// The text heuristic, for the languages with no structural scan yet.
///
/// The immutability keywords are read per language, with no shared default. The default they
/// used to have was a union of five languages' keywords that no single language uses, and
/// only two overrode it, so TypeScript inherited `let ` and classified every module-level
/// `let` as immutable.
fn module_mutables_text(root: Node, cfg: &LangCfg, src: &[u8]) -> BTreeSet<String> {
    let mut mutables = BTreeSet::new();
    for node in shallow_candidates(root, cfg.module_level_assign) {
        for line in text(Some(node), src).lines() {
            if !line.contains('=') {
                continue;
            }
            let lowered = line.to_lowercase();
            if cfg.const_keywords.iter().any(|kw| lowered.contains(kw)) {
                continue;
            }
            let head = line.split('=').next().unwrap_or("").trim();
            let Some(last) = head.split_whitespace().next_back() else { continue };
            let name = last.trim_matches(|c| "()[]:,".contains(c));
            let upper = !name.is_empty()
                && name.chars().any(|c| c.is_alphabetic())
                && name.chars().filter(|c| c.is_alphabetic()).all(|c| c.is_uppercase());
            if !name.is_empty() && !cfg.this_ident.contains(&name) && !upper {
                mutables.insert(name.to_string());
            }
        }
    }
    mutables
}

/// The identifier a C declarator binds, or nothing when it binds no state.
///
/// A prototype binds none: `void proto(int)` is a function declarator whose own declarator is
/// a bare identifier. A function POINTER does bind state, and the grammar makes the two easy
/// to confuse, because it puts a function declarator on top of both. `void (*handler)(int)`
/// reaches its name through a parenthesised declarator holding a pointer declarator, and a
/// rebindable pointer is state whatever it points at.
fn c_declared_name(declarator: Node, src: &[u8]) -> Option<String> {
    let mut node = Some(declarator);
    while let Some(n) = node {
        if n.kind() == "identifier" {
            return Some(text(Some(n), src));
        }
        if !C_DECLARATORS.contains(&n.kind()) {
            return None;
        }
        if n.kind() == "function_declarator" {
            let inner = field(Some(n), "declarator");
            match inner {
                Some(inner) if inner.kind() == "parenthesized_declarator" => {
                    node = children(inner).into_iter().find(|c| c.kind() == "pointer_declarator");
                }
                // A prototype, not a variable.
                _ => return None,
            }
            continue;
        }
        node = field(Some(n), "declarator")
            .or_else(|| children(n).into_iter().find(|c| C_DECLARATORS.contains(&c.kind())));
    }
    None
}

/// File-scope declarations in C, read from the parse tree rather than from line text.
///
/// C used the text heuristic, which needs an `=` on the line, so `static int cache[256];`
/// declared no state as far as L1.18 was concerned. On one fixture the text scan found one
/// name and missed four, while the classifier enumerated all five. Two measures of one file
/// disagreeing about what is even a candidate is the defect; the array was the instance.
///
/// Known limit, kept deliberately: a declaration carrying a `const` qualifier is excluded
/// whole, which is right for `const int MAX = 10` and wrong for `const char *NAME`, where
/// const qualifies the pointee and the pointer is still rebindable. That is the same call the
/// text heuristic made.
fn module_mutables_c(root: Node, cfg: &LangCfg, src: &[u8]) -> BTreeSet<String> {
    let mut names = BTreeSet::new();
    for node in children(root) {
        if node.kind() != "declaration" {
            continue;
        }
        let qualified = children(node).into_iter().any(|c| c.kind() == "type_qualifier"
            && cfg.const_keywords.iter().any(|kw| kw.trim() == text(Some(c), src)));
        if qualified {
            continue;
        }
        for child in children(node) {
            if C_DECLARATORS.contains(&child.kind()) {
                if let Some(name) = c_declared_name(child, src) {
                    names.insert(name);
                }
                break;
            }
        }
    }
    names
}

/// The names in one file that L1.18 treats as external mutable state.
///
/// Dispatched on the scan the language DECLARES, and refused for a name no arm covers. A chain
/// of flag tests used to fall through to the text heuristic, which is how TypeScript and C
/// ended up on a scan nobody chose for them.
pub fn module_mutable_names(root: Node, cfg: &LangCfg, src: &[u8]) -> Option<BTreeSet<String>> {
    match cfg.module_scan {
        "python_fields" => Some(module_mutables_python(root, cfg, src)),
        "mutable_specifier" => Some(module_mutables_by_specifier(root, cfg, src)),
        "class_fields" => Some(module_mutables_class_fields(root, cfg, src)),
        "c_declarations" => Some(module_mutables_c(root, cfg, src)),
        "text" => Some(module_mutables_text(root, cfg, src)),
        _ => None,
    }
}

/// The function declarator of a C function definition.
///
/// C hangs the name and the parameter list off a declarator chain rather than off the
/// definition, and a function returning a pointer wraps that chain in one or more pointer
/// declarators.
fn c_function_declarator<'t>(func: Node<'t>) -> Option<Node<'t>> {
    let mut declarator = field(Some(func), "declarator");
    while let Some(d) = declarator {
        if d.kind() == "function_declarator" {
            return Some(d);
        }
        declarator = field(Some(d), "declarator");
    }
    None
}

/// The declared name of a function node, in any of the nine languages.
///
/// Eight of them put it on a name field. C does not, and reading that field alone returned
/// nothing for every C function: harmless while no C function was ever counted, and a silent
/// contract break the moment one was.
pub fn function_name(node: Node, src: &[u8]) -> String {
    if let Some(named) = field(Some(node), "name") {
        return text(Some(named), src);
    }
    let mut inner = c_function_declarator(node).and_then(|d| field(Some(d), "declarator"));
    while let Some(n) = inner {
        if n.kind() == "identifier" {
            return text(Some(n), src);
        }
        inner = field(Some(n), "declarator");
    }
    String::new()
}

/// Go names its receiver per method. The first parameter list is the receiver list, and a
/// plain function has none, so nothing inside one is read as instance access.
fn go_method_receivers(func: Node, src: &[u8]) -> BTreeSet<String> {
    let mut names = BTreeSet::new();
    if func.kind() != "method_declaration" {
        return names;
    }
    if let Some(list) = children(func).into_iter().find(|c| c.kind() == "parameter_list") {
        for decl in children(list).into_iter().filter(|d| d.kind() == "parameter_declaration") {
            names.extend(children(decl).into_iter().filter(|p| p.kind() == "identifier")
                         .map(|p| text(Some(p), src)));
        }
    }
    names
}

/// C's receivers: the pointer parameters of this function.
///
/// C has no receiver keyword and no receiver declaration, and that absence is why this arm was
/// dead. A C function reaches state it does not own by being handed a pointer to the record
/// that holds it, so the pointer parameters are the names through which a caller's state is
/// read and written, and `s->cache` inside `void put(struct Store *s, ...)` is the same fact
/// about testability as `self.cache` inside a Python method.
///
/// Parameters only, never a local pointer. A pointer a function allocates and fills is state
/// that function owns for its own lifetime, and counting it would read local work as external
/// state. The limit worth naming: this counts the reach, not what is on the other end of it,
/// so C reads high on this axis rather than clean.
fn c_pointer_receivers(func: Node, src: &[u8]) -> BTreeSet<String> {
    let mut names = BTreeSet::new();
    let Some(declarator) = c_function_declarator(func) else { return names };
    let Some(params) = children(declarator).into_iter().find(|c| c.kind() == "parameter_list")
        else { return names };
    for decl in children(params).into_iter().filter(|d| d.kind() == "parameter_declaration") {
        let mut inner = field(Some(decl), "declarator");
        if inner.map(|i| i.kind()) != Some("pointer_declarator") {
            continue;
        }
        while let Some(n) = inner {
            if n.kind() != "pointer_declarator" {
                break;
            }
            inner = field(Some(n), "declarator");
        }
        if let Some(n) = inner {
            if n.kind() == "identifier" {
                names.insert(text(Some(n), src));
            }
        }
    }
    names
}

/// Names that denote the state-holding record this function reaches into.
///
/// Dispatched on the receiver rule the language DECLARES. What stood here was a fixed-keyword
/// test followed by a Go-shaped one, whose fall-through was the empty set. C took that
/// fall-through, so a struct field mutated through a pointer counted as no external state on
/// any repository ever audited, and L1.18 reported 0.0 Healthy over it.
fn receiver_names(func: Node, cfg: &LangCfg, src: &[u8]) -> Option<BTreeSet<String>> {
    match cfg.receiver_scan {
        "fixed" => Some(cfg.this_ident.iter().map(|s| s.to_string()).collect()),
        "go_method_receiver" => Some(go_method_receivers(func, src)),
        "c_pointer_params" => Some(c_pointer_receivers(func, src)),
        _ => None,
    }
}

/// Count references inside a function body to UNBOUNDED external mutable state.
///
/// `bounded` is the set of state keys the classifier could bound in this file, and a reference
/// to one of them does not count. L1.18 used to count a reference to outside state whether or
/// not the state could take unboundedly many values, so a read keyed by a literal against a
/// closed set scored identically to an unbounded accumulator.
///
/// The operator joining receiver to member is read from the language's own table rather than
/// assumed. It used to be a hard-coded `.`, which is right in eight of the nine and wrong in C,
/// where a caller's record is reached as `s->cache`.
///
/// The classifier keys instance state by the same text this walk sees, so the two vocabularies
/// line up without translation. Go and C are the exceptions: Go keys by type and field and C
/// by struct tag and field, while this walk sees receiver and field, so no Go or C reference is
/// ever matched as bounded and both keep their uncorrected reading on this axis. A key the
/// classifier never enumerated is absent from `bounded` and therefore counts, so every gap
/// reads high, never falsely clean.
fn count_mutable_refs(body: Node, cfg: &LangCfg, module_mutables: &BTreeSet<String>,
                      receivers: &BTreeSet<String>, bounded: &BTreeSet<String>,
                      src: &[u8]) -> usize {
    let mut count = 0;
    let prefixes: Vec<String> =
        receivers.iter().map(|r| format!("{r}{}", cfg.member_op)).collect();
    for n in descendants(body) {
        // The node's text is read only where a rule below can use it. Reading it for every
        // node in the tree allocates a string per node, and on a large C repository that is
        // most of the run.
        let is_member = n.kind() == cfg.member_access && !prefixes.is_empty();
        let is_field = cfg.instance_field_types.contains(&n.kind());
        let is_ident = n.kind() == "identifier";
        let raw = !cfg.raw_mut_patterns.is_empty();
        if !(is_member || is_field || is_ident || raw) {
            continue;
        }
        let spelling = text(Some(n), src);
        if is_member && prefixes.iter().any(|p| spelling.starts_with(p))
            && !bounded.contains(&spelling) {
            count += 1;
        }
        if is_field && !bounded.contains(&spelling) {
            count += 1;
        }
        if is_ident && module_mutables.contains(&spelling) && !bounded.contains(&spelling) {
            count += 1;
        }
        // Raw-text mutable patterns are language-scoped (Rust only). Running them for every
        // language flagged any source that merely contained the strings.
        if raw && cfg.raw_mut_patterns.iter().any(|p| spelling.contains(p)) {
            count += 1;
        }
    }
    count
}

/// State keys in one file whose reaching set the classifier could bound.
///
/// Three conditions, all read from the classifier's own finding, and all three needed. Neutral
/// is its verdict for state whose partition it bounded; promiscuous and unresolved both leave
/// the partition unknown, so both keep counting.
///
/// Driving a decision and a counted partition are the other two, and dropping them is a trap
/// this walked into once. Neutral is also what the classifier returns for state that reaches no
/// decision at all, an accumulator that is written and returned but never branched on, and its
/// partition is then empty, meaning "nothing to cover" and not "finitely many classes".
/// Excluding that state cancelled the Java and C# field correction exactly where it was needed.
fn bounded_state_keys(root: Node, rel: &str, lang: &str, immutable_ctors: &[String],
                      src: &[u8]) -> BTreeSet<String> {
    let Some(sp) = crate::lang_spec::spec_for(lang) else { return BTreeSet::new() };
    let Some(read) = bounds::analyze_file(root, rel, sp, immutable_ctors, src)
        else { return BTreeSet::new() };
    read.findings.into_iter()
        .filter(|f| f.verdict == NEUTRAL && f.drives_decision && f.partition.counted)
        .map(|f| f.state)
        .collect()
}


/// One file's (total functions, functions touching unbounded external mutable state).
///
/// Refused whole where the language declares a receiver scan nobody wrote. Counting the
/// function into the denominator and then skipping the test would publish a ratio built on
/// functions nobody looked at, which reads clean for the same reason the C gap did.
fn count_file_functions(root: Node, cfg: &LangCfg, module_mutables: &BTreeSet<String>,
                        bounded: &BTreeSet<String>, src: &[u8]) -> Option<(usize, usize)> {
    let mut total = 0;
    let mut touching = 0;
    for n in descendants(root) {
        if !cfg.function_types.contains(&n.kind()) {
            continue;
        }
        total += 1;
        let Some(body) = children(n).into_iter().find(|c| BODY_NODE_TYPES.contains(&c.kind()))
            else { continue };
        let receivers = receiver_names(n, cfg, src)?;
        if count_mutable_refs(body, cfg, module_mutables, &receivers, bounded, src) > 0 {
            touching += 1;
        }
    }
    Some((total, touching))
}

/// `round(x, 1)` as the reference's JSON prints it.
fn py_round1(x: f64) -> String {
    let rounded = (x * 10.0).round() / 10.0;
    let mut s = format!("{rounded}");
    if !s.contains('.') && !s.contains('e') {
        s.push_str(".0");
    }
    s
}

/// L1.18: the percentage of functions that reference unbounded external mutable state.
pub fn analyze(repo: &Path, language: &str) -> Indicator {
    let row = |value: String, band: String, details: String| Indicator {
        code: "L1.18".into(), label: "mutable-state".into(), value, band, details,
    };
    let Some(cfg) = lang::cfg(language) else {
        return row("n/a".into(), "n/a".into(),
                   format!("no tree-sitter config for {language}"));
    };
    let (roots, skipped) = crate::production_files(repo, language);

    // The repository's immutable constructors, which the classifier needs before it can
    // resolve a constant built by one. Two passes, matching the classifier's own contract: a
    // constant built by a function defined in another file cannot be resolved until every
    // file has been seen.
    let mut immutable_ctors: Vec<String> = Vec::new();
    if language == "python" {
        for (_rel, tree, src) in &roots {
            immutable_ctors.extend(
                crate::state::constants::collect_immutable_ctors(tree.root_node(), src));
        }
    }

    let mut total_funcs = 0usize;
    let mut mutable_funcs = 0usize;
    for (rel, tree, src) in &roots {
        let root = tree.root_node();
        let Some(module_mutables) = module_mutable_names(root, cfg, src) else {
            // A language whose module scan nobody wrote. Refused whole rather than reported
            // as a repository whose functions touch no outside state.
            return row("n/a".into(), "n/a".into(),
                       format!("{language} declares the module scan {:?}, which nobody wrote",
                               cfg.module_scan));
        };
        let bounded = bounded_state_keys(root, rel, language, &immutable_ctors, src);
        let Some((file_total, file_mutable)) =
            count_file_functions(root, cfg, &module_mutables, &bounded, src) else {
            return row("n/a".into(), "n/a".into(),
                       format!("{language} declares the receiver scan {:?}, which nobody wrote",
                               cfg.receiver_scan));
        };
        total_funcs += file_total;
        mutable_funcs += file_mutable;
    }

    if total_funcs == 0 {
        // Nought over zero is not a percentage and it is not zero percent; it is the absence
        // of a measurement. The reference refuses here and so does this.
        return row("n/a".into(), "n/a".into(), format!(
            "INCOMPLETE CODE: L1.18 unbounded mutable state cannot answer: no function was \
             enumerated in {language}, so the share of them touching unbounded state is \
             absent, not zero"));
    }
    let ratio = mutable_funcs as f64 / total_funcs as f64 * 100.0;
    let mut details = format!(
        "{mutable_funcs}/{total_funcs} functions reference unbounded external mutable state \
         ({language})");
    if skipped != 0 {
        details = format!("{details}; {skipped} file(s) unreadable and excluded");
    }
    row(py_round1(ratio), band(ratio, 15.0, 40.0, false).into(), details)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser_for;

    fn parse(source: &str, lang: &str) -> (tree_sitter::Tree, Vec<u8>) {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        (parser.parse(&bytes, None).expect("a parse"), bytes)
    }

    fn mutables(source: &str, lang: &str) -> BTreeSet<String> {
        let (tree, src) = parse(source, lang);
        let cfg = lang::cfg(lang).expect("a language row");
        module_mutable_names(tree.root_node(), cfg, &src).expect("a declared scan")
    }

    #[test]
    fn an_uppercase_name_is_a_constant_until_it_is_seeded_with_an_empty_container() {
        // `CACHE = {}` is the accumulator this indicator exists to catch, and `MAX = 10`
        // beside it is a constant. Casing alone cannot tell them apart.
        let found = mutables("MAX = 10\nCACHE = {}\nNAMES = list()\ncounter = 0\n", "python");
        assert!(found.contains("CACHE"), "{found:?}");
        assert!(found.contains("NAMES"), "{found:?}");
        assert!(found.contains("counter"), "{found:?}");
        assert!(!found.contains("MAX"), "{found:?}");
    }

    #[test]
    fn a_type_alias_is_a_declaration_and_not_state() {
        let source = "Panel = dict[str, int]\nRow = TypedDict('Row', {'a': int})\nseen = {}\n";
        let found = mutables(source, "python");
        assert!(!found.contains("Panel"), "{found:?}");
        assert!(!found.contains("Row"), "{found:?}");
        assert!(found.contains("seen"), "{found:?}");
    }

    #[test]
    fn a_dunder_is_module_metadata() {
        let found = mutables("__all__ = ['a']\n__version__ = '1'\nstate = []\n", "python");
        assert_eq!(found, ["state"].iter().map(|s| s.to_string()).collect());
    }

    #[test]
    fn rust_counts_a_static_only_where_it_carries_the_mut_specifier() {
        let source = "static mut COUNTER: i32 = 0;\nstatic LIMIT: i32 = 5;\n\
                      const MAX: i32 = 9;\n";
        let found = mutables(source, "rust");
        assert!(found.contains("COUNTER"), "{found:?}");
        assert!(!found.contains("LIMIT"), "{found:?}");
        assert!(!found.contains("MAX"), "{found:?}");
    }

    #[test]
    fn a_java_field_is_state_unless_a_keyword_says_it_cannot_be_rebound() {
        // Read from the declared modifiers, not from the name's casing: both languages have
        // a keyword for the property and it is already in the source. And no `=` is needed,
        // which is what made `private int total;` invisible to the line-text scan.
        let source = "class Store {\n  private int total;\n  private final int max = 9;\n\
                      static Map<String,Integer> hits = new HashMap<>();\n}\n";
        let found = mutables(source, "java");
        assert!(found.contains("total"), "{found:?}");
        assert!(found.contains("hits"), "{found:?}");
        assert!(!found.contains("max"), "{found:?}");
    }

    #[test]
    fn a_c_array_at_file_scope_is_state_though_no_equals_sign_appears() {
        // The defect this scan replaced: the text heuristic needed an `=` on the line, so
        // the ordinary C global cache declared no state at all.
        let source = "static int cache[256];\nstatic char buf[64];\nint counter = 0;\n\
                      const int MAX = 10;\n";
        let found = mutables(source, "c");
        assert!(found.contains("cache"), "{found:?}");
        assert!(found.contains("buf"), "{found:?}");
        assert!(found.contains("counter"), "{found:?}");
        assert!(!found.contains("MAX"), "{found:?}");
    }

    #[test]
    fn a_c_prototype_binds_nothing_and_a_function_pointer_binds_state() {
        // The grammar puts a function declarator on top of both, which is the confusion the
        // declarator walk exists to resolve.
        let source = "void proto(int);\nvoid (*handler)(int);\n";
        let found = mutables(source, "c");
        assert!(found.contains("handler"), "{found:?}");
        assert!(!found.contains("proto"), "{found:?}");
    }

    #[test]
    fn typescript_reads_its_own_immutability_keywords_and_not_javascripts() {
        // TypeScript inherited `let ` from a shared default and read every module-level
        // `let` as immutable, which is the whole reason the keywords are per language.
        let found = mutables("let counter = 0;\nconst LIMIT = 5;\n", "typescript");
        assert!(found.contains("counter"), "{found:?}");
        assert!(!found.contains("LIMIT"), "{found:?}");
    }

    #[test]
    fn a_c_function_reaches_a_callers_record_through_its_pointer_parameters() {
        // C has no receiver keyword, and the fall-through that gave it none made the
        // member arm dead code: a struct field mutated through a pointer counted as no
        // external state on any repository ever audited.
        let source = "void put(struct Store *s, int v) { s->cache[0] = v; }\n";
        let (tree, src) = parse(source, "c");
        let cfg = lang::cfg("c").expect("c");
        let func = descendants(tree.root_node()).into_iter()
            .find(|n| n.kind() == "function_definition").expect("the function");
        let receivers = receiver_names(func, cfg, &src).expect("a declared receiver scan");
        assert!(receivers.contains("s"), "{receivers:?}");
        assert_eq!(function_name(func, &src), "put");
    }

    #[test]
    fn a_go_method_names_its_receiver_and_a_plain_function_has_none() {
        let source = "package p\nfunc (r *Foo) Bar() { r.n = 1 }\nfunc Baz() {}\n";
        let (tree, src) = parse(source, "go");
        let cfg = lang::cfg("go").expect("go");
        let method = descendants(tree.root_node()).into_iter()
            .find(|n| n.kind() == "method_declaration").expect("the method");
        let plain = descendants(tree.root_node()).into_iter()
            .find(|n| n.kind() == "function_declaration").expect("the function");
        assert!(receiver_names(method, cfg, &src).expect("a scan").contains("r"));
        assert!(receiver_names(plain, cfg, &src).expect("a scan").is_empty());
    }

    #[test]
    fn a_ratio_over_no_function_at_all_is_absent_and_never_zero() {
        // Nought over zero is not a percentage and it is not zero percent. Every stub that
        // wrote `if total else 0.0` published the absence of a measurement as a clean score.
        let root = std::env::temp_dir().join(format!("slop-l118-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("make the fixture");
        std::fs::write(root.join("empty.py"), "X = 1\n").expect("write");
        let got = analyze(&root, "python");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(got.value, "n/a");
        assert_eq!(got.band, "n/a");
        assert!(got.details.contains("absent, not zero"), "{}", got.details);
    }
}
