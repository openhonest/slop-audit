//! What each language's concurrency surface looks like. Ported from the per-language
//! scanners of l1_analyzer.thread_surface.
//!
//! Six scanners, one per language that has one, and nothing shared between them but the
//! vocabulary next door. They live apart from the reading itself because they answer a
//! different question: that module says what a surface reading IS and how a repository gets
//! one, and this one says what the surface looks like in Rust, Python, JavaScript, Go, Java
//! and Ruby.
//!
//! A language with no scanner here reaches the n/a row rather than a clean one. An empty
//! finding list reads exactly like clean code, and the two must not be spelled the same.

use crate::indicators::thread_surface::{
    method_receiver, mk, receivers_by_method, Finding, CANDIDATE, EXPOSED, REVIEW,
};
use crate::lang_spec::LangSpec;
use crate::nodes::{children, descendants, field, text};
use std::collections::BTreeSet;
use tree_sitter::Node;

// --- the Rust scanner ------------------------------------------------------------
//
// Category A (an overridden guarantee: `unsafe impl Send`/`Sync`, `static mut`) and the
// relaxed-ordering footgun are whole-file node matches. B1 (a non-atomic read-modify-write)
// and B2 (check-then-act) are per-function shapes, restricted to receivers rooted at the
// object so the rule flags shared INSTANCE state and skips pure locals. Each B finding is a
// suspected race SHAPE to verify, never a proven race.
//
// The static taxonomy stops there on purpose. Advancing past a live reader is semantic and
// cross-file, so no per-file pattern reaches it and it is a runtime catch. An escaped shared
// reference and lock discipline are enforced by Rust's own type system, so there is little
// honest static signal left in them here.

/// B1: a load and a store on the same atomic in one function is a read-modify-write done
/// non-atomically.
const ATOMIC_STORE: &[&str] = &["store", "swap"];
/// B2: a collection read in a condition, then a mutation in the body.
const CHECK_METHODS: &[&str] = &["contains_key", "contains", "is_empty", "is_none", "is_some",
                                 "get", "get_mut", "len", "capacity"];
const MUTATE_METHODS: &[&str] = &["insert", "push", "push_back", "remove", "pop", "clear",
                                  "extend", "append", "set", "store", "swap"];
/// Comparison operators that, together with a branch, make a relaxed load control-bearing.
const CMP_OPS: &[&str] = &["==", "!=", "<", ">", "<=", ">="];

/// True only when the method takes a SHARED borrow of the object, so two threads can call it
/// at once.
///
/// An exclusive borrow and a by-value receiver are exclusive by the borrow checker, so no
/// concurrent aliasing is possible and a check-then-act or read-modify-write there is not a
/// race. Skipping them is what keeps the two rules off exclusive methods.
fn rust_takes_shared_self(func: Node) -> bool {
    let Some(params) = field(Some(func), "parameters") else { return false };
    let Some(sp) = descendants(params).into_iter().find(|c| c.kind() == "self_parameter")
        else { return false };
    let kids = children(sp);
    kids.iter().any(|c| c.kind() == "&") && !kids.iter().any(|c| c.kind() == "mutable_specifier")
}

/// B1: the same atomic on the object is both loaded and stored in one function.
///
/// A receiver that also uses a compare-exchange or a fetch in the same function is running a
/// real atomic protocol, not an unguarded read-modify-write, so it is excluded. That is what
/// keeps the shape off correct lock-free code.
fn rust_nonatomic_rmw(func: Node, rel: &str, sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    let mut loads: Vec<(String, Node)> = Vec::new();
    let mut stores: BTreeSet<String> = BTreeSet::new();
    let mut atomic_protocol: BTreeSet<String> = BTreeSet::new();
    for n in descendants(func) {
        let Some((method, receiver)) = method_receiver(n, sp, src) else { continue };
        if !receiver.starts_with("self.") {
            continue;
        }
        if method == "load" {
            if !loads.iter().any(|(held, _)| *held == receiver) {
                loads.push((receiver, n));
            }
        } else if ATOMIC_STORE.contains(&method.as_str()) {
            stores.insert(receiver);
        } else if method.starts_with("fetch_")
            || matches!(method.as_str(),
                        "compare_exchange" | "compare_exchange_weak" | "compare_and_swap") {
            atomic_protocol.insert(receiver);
        }
    }
    loads.into_iter()
        .filter(|(recv, _)| stores.contains(recv) && !atomic_protocol.contains(recv))
        .map(|(recv, node)| mk("nonatomic_rmw", &recv, CANDIDATE, rel, node))
        .collect()
}

/// Whether the call names a relaxed ordering among its arguments.
fn call_uses_relaxed(call: Node, src: &[u8]) -> bool {
    let Some(args) = field(Some(call), "arguments") else { return false };
    descendants(args).into_iter().any(|n| {
        n.kind() == "scoped_identifier"
            && text(Some(n), src).replace(' ', "").ends_with("Ordering::Relaxed")
    })
}

/// True when the call's result reaches a branch condition or a comparison, through a few
/// transparent wrappers.
///
/// The let-bound case is out of scope on purpose: only the directly control-bearing shape,
/// to stay high-precision.
fn result_feeds_branch(call: Node) -> bool {
    let mut node = call;
    for _ in 0..5 {
        let Some(parent) = node.parent() else { return false };
        match parent.kind() {
            "if_expression" | "while_expression" => {
                return match field(Some(parent), "condition") {
                    Some(cond) => cond.id() == node.id(),
                    None => false,
                };
            }
            "binary_expression" => {
                return children(parent).iter().any(|c| CMP_OPS.contains(&c.kind()));
            }
            "parenthesized_expression" | "unary_expression" | "reference_expression"
            | "try_expression" => {
                node = parent;
            }
            _ => return false,
        }
    }
    false
}

/// B2: an `if` whose condition checks a collection on the object and whose body mutates the
/// same one, which is a check-then-act window.
fn rust_check_then_act(func: Node, rel: &str, sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    let mut findings = Vec::new();
    for n in descendants(func).into_iter().filter(|n| n.kind() == "if_expression") {
        let checked = receivers_by_method(field(Some(n), "condition"), CHECK_METHODS, sp, src);
        let mut mutated =
            receivers_by_method(field(Some(n), "consequence"), MUTATE_METHODS, sp, src);
        mutated.extend(
            receivers_by_method(field(Some(n), "alternative"), MUTATE_METHODS, sp, src));
        for recv in checked.intersection(&mutated) {
            findings.push(mk("check_then_act", recv, REVIEW, rel, n));
        }
    }
    findings
}

fn is_test_file(rel: &str) -> bool {
    let low = rel.to_lowercase();
    low.ends_with("tests.rs") || low.ends_with("test.rs")
        || low.contains("/tests/") || low.contains("/test/")
}

pub(crate) fn scan_rust(root: Node, rel: &str, sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    let mut findings = Vec::new();
    for n in descendants(root) {
        // `unsafe impl Send`/`Sync` for a type: the guarantee is hand-asserted.
        if n.kind() == "impl_item" && children(n).iter().any(|c| c.kind() == "unsafe") {
            let trait_name = text(field(Some(n), "trait"), src);
            if trait_name == "Send" || trait_name == "Sync" {
                let target = text(field(Some(n), "type"), src);
                findings.push(mk(&format!("unsafe_impl_{}", trait_name.to_lowercase()),
                                 &target, EXPOSED, rel, n));
            }
            continue;
        }
        // `static mut NAME`: global mutable state with no compiler guard.
        if n.kind() == "static_item" && children(n).iter().any(|c| c.kind() == "mutable_specifier") {
            findings.push(mk("static_mut", &text(field(Some(n), "name"), src), EXPOSED, rel, n));
            continue;
        }
        // The remaining shapes are not production concurrency surface in a test file.
        if is_test_file(rel) {
            continue;
        }
        if n.kind() == "call_expression" {
            // C1: a relaxed LOAD whose value gates control flow is a review-level missing
            // acquire; every other relaxed use is the low-precision candidate tier, because
            // relaxed is correct for a counter or a statistic.
            if let Some((method, receiver)) = method_receiver(n, sp, src) {
                if call_uses_relaxed(n, src) {
                    if method == "load" && result_feeds_branch(n) {
                        findings.push(mk("relaxed_guard", &receiver, REVIEW, rel, n));
                    } else {
                        findings.push(mk("relaxed_ordering", &receiver, CANDIDATE, rel, n));
                    }
                }
            }
        } else if n.kind() == "function_item" && rust_takes_shared_self(n) {
            findings.extend(rust_nonatomic_rmw(n, rel, sp, src));
            findings.extend(rust_check_then_act(n, rel, sp, src));
        }
    }
    findings
}

// --- the Python scanner ----------------------------------------------------------
//
// Python has no compiler thread-safety guarantee, so the surface is shared mutable state
// that free-threading makes concurrent, not a hand-override. The module-scoped rule is
// conservative and disclosed: a module container is surfaced only when the file itself uses
// a concurrency primitive, and it is downgraded when any lock is present in the file.

/// Right-hand sides that bind a mutable container.
const PY_MUTABLE_LITERALS: &[&str] = &["dictionary", "list", "set", "dictionary_comprehension",
                                       "list_comprehension", "set_comprehension"];
const PY_MUTABLE_CTORS: &[&str] = &["dict", "list", "set", "defaultdict", "OrderedDict",
                                    "Counter", "deque"];
/// Modules whose presence means the file runs work concurrently.
const PY_CONCURRENCY_MODULES: &[&str] = &["threading", "multiprocessing", "concurrent"];
const PY_CONCURRENCY_CALLS: &[&str] = &["Thread", "Process", "ThreadPoolExecutor",
                                        "ProcessPoolExecutor"];
/// Names whose presence means some synchronisation exists in the file.
const PY_LOCK_NAMES: &[&str] = &["Lock", "RLock", "Semaphore", "BoundedSemaphore", "Condition",
                                 "Barrier"];
const PY_MUTATE_METHODS: &[&str] = &["add", "append", "update", "setdefault", "pop", "remove",
                                     "extend", "insert", "popitem", "clear", "discard"];

fn py_rhs_is_mutable(rhs: Option<Node>, src: &[u8]) -> bool {
    let Some(rhs) = rhs else { return false };
    if PY_MUTABLE_LITERALS.contains(&rhs.kind()) {
        return true;
    }
    rhs.kind() == "call"
        && PY_MUTABLE_CTORS.contains(&text(field(Some(rhs), "function"), src).as_str())
}

/// Top-level module names the file imports.
fn py_imported_modules(root: Node, src: &[u8]) -> BTreeSet<String> {
    let mut mods = BTreeSet::new();
    let head = |spelling: String| -> String {
        spelling.split('.').next().unwrap_or("").split(' ').next().unwrap_or("").to_string()
    };
    for n in children(root) {
        if n.kind() == "import_statement" {
            for c in children(n) {
                if matches!(c.kind(), "dotted_name" | "aliased_import") {
                    mods.insert(head(text(Some(c), src)));
                }
            }
        } else if n.kind() == "import_from_statement" {
            if let Some(module) = field(Some(n), "module_name") {
                mods.insert(text(Some(module), src).split('.').next().unwrap_or("").to_string());
            }
        }
    }
    mods
}

fn py_uses_concurrency(root: Node, nodes: &[Node], src: &[u8]) -> bool {
    if py_imported_modules(root, src).iter()
        .any(|m| PY_CONCURRENCY_MODULES.contains(&m.as_str())) {
        return true;
    }
    // A direct constructor call, however imported.
    nodes.iter().any(|n| {
        n.kind() == "call" && match field(Some(*n), "function") {
            Some(f) => {
                let spelling = text(Some(f), src);
                let name = spelling.rsplit('.').next().unwrap_or("").to_string();
                PY_CONCURRENCY_CALLS.contains(&name.as_str())
            }
            None => false,
        }
    })
}

/// The assignment a top-level statement carries, past Python's expression wrapper.
fn py_top_assignment<'t>(stmt: Node<'t>) -> Node<'t> {
    if stmt.kind() == "expression_statement" {
        if let Some(first) = children(stmt).into_iter().next() {
            return first;
        }
    }
    stmt
}

fn py_module_containers(root: Node, src: &[u8]) -> BTreeSet<String> {
    let mut names = BTreeSet::new();
    for stmt in children(root) {
        let assign = py_top_assignment(stmt);
        if assign.kind() != "assignment" {
            continue;
        }
        if let Some(left) = field(Some(assign), "left") {
            if left.kind() == "identifier"
                && py_rhs_is_mutable(field(Some(assign), "right"), src) {
                names.insert(text(Some(left), src));
            }
        }
    }
    names
}

/// Shared containers a membership test checks: the container operand of `x in C`.
fn py_condition_containers(cond: Option<Node>, containers: &BTreeSet<String>,
                           src: &[u8]) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let Some(cond) = cond else { return out };
    for n in descendants(cond) {
        if n.kind() != "comparison_operator" {
            continue;
        }
        if !children(n).iter().any(|c| matches!(c.kind(), "in" | "not in")) {
            continue;
        }
        let named: Vec<Node> = children(n).into_iter().filter(|c| c.is_named()).collect();
        if let Some(last) = named.last() {
            let spelling = text(Some(*last), src);
            if last.kind() == "identifier" && containers.contains(&spelling) {
                out.insert(spelling);
            }
        }
    }
    out
}

/// Shared containers a block mutates, by key assignment or by a mutating method.
fn py_body_mutated(body: Option<Node>, containers: &BTreeSet<String>,
                   src: &[u8]) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let Some(body) = body else { return out };
    for n in descendants(body) {
        if n.kind() == "assignment" {
            if let Some(left) = field(Some(n), "left") {
                if left.kind() == "subscript" {
                    if let Some(value) = field(Some(left), "value") {
                        let spelling = text(Some(value), src);
                        if value.kind() == "identifier" && containers.contains(&spelling) {
                            out.insert(spelling);
                        }
                    }
                }
            }
        } else if n.kind() == "call" {
            let Some(func) = field(Some(n), "function") else { continue };
            if func.kind() != "attribute" {
                continue;
            }
            let Some(recv) = field(Some(func), "object") else { continue };
            let spelling = text(Some(recv), src);
            let method = text(field(Some(func), "attribute"), src);
            if recv.kind() == "identifier" && containers.contains(&spelling)
                && PY_MUTATE_METHODS.contains(&method.as_str()) {
                out.insert(spelling);
            }
        }
    }
    out
}

fn py_check_then_act(root: Node, containers: &BTreeSet<String>, rel: &str,
                     src: &[u8]) -> Vec<Finding> {
    let mut findings = Vec::new();
    for n in descendants(root).into_iter().filter(|n| n.kind() == "if_statement") {
        let checked = py_condition_containers(field(Some(n), "condition"), containers, src);
        let mut mutated = py_body_mutated(field(Some(n), "consequence"), containers, src);
        mutated.extend(py_body_mutated(field(Some(n), "alternative"), containers, src));
        for name in checked.intersection(&mutated) {
            findings.push(mk("check_then_act", name, REVIEW, rel, n));
        }
    }
    findings
}

/// The names a function declares global, which is the shared module state it writes.
fn py_global_names(func: Node, src: &[u8]) -> BTreeSet<String> {
    let mut names = BTreeSet::new();
    for n in descendants(func).into_iter().filter(|n| n.kind() == "global_statement") {
        names.extend(children(n).into_iter().filter(|c| c.kind() == "identifier")
                     .map(|c| text(Some(c), src)));
    }
    names
}

/// B1 for Python: a compound assignment on a name the function declares global. The
/// load-add-store is not atomic, so under free-threading two threads lose an update.
fn py_nonatomic_rmw(root: Node, rel: &str, guarded: bool, src: &[u8]) -> Vec<Finding> {
    let severity = if guarded { CANDIDATE } else { REVIEW };
    let mut findings = Vec::new();
    for func in descendants(root).into_iter().filter(|n| n.kind() == "function_definition") {
        let globals_ = py_global_names(func, src);
        if globals_.is_empty() {
            continue;
        }
        for n in descendants(func).into_iter().filter(|n| n.kind() == "augmented_assignment") {
            if let Some(left) = field(Some(n), "left") {
                let spelling = text(Some(left), src);
                if left.kind() == "identifier" && globals_.contains(&spelling) {
                    findings.push(mk("nonatomic_rmw", &spelling, severity, rel, n));
                }
            }
        }
    }
    findings
}

fn py_has_lock(nodes: &[Node], src: &[u8]) -> bool {
    nodes.iter().any(|n| {
        if n.kind() == "identifier" && PY_LOCK_NAMES.contains(&text(Some(*n), src).as_str()) {
            return true;
        }
        // A lock is being taken somewhere in the file.
        n.kind() == "call" && match field(Some(*n), "function") {
            Some(f) => f.kind() == "attribute"
                && text(field(Some(f), "attribute"), src) == "acquire",
            None => false,
        }
    })
}

pub(crate) fn scan_python(root: Node, rel: &str, _sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    let mut findings = Vec::new();
    let nodes = descendants(root);

    // A mutable default argument is shared across calls, always decidable, and a race under
    // free-threading. A footgun whatever the file's concurrency imports say.
    for n in &nodes {
        if matches!(n.kind(), "default_parameter" | "typed_default_parameter")
            && py_rhs_is_mutable(field(Some(*n), "value"), src) {
            findings.push(mk("mutable_default_arg", &text(field(Some(*n), "name"), src),
                             REVIEW, rel, *n));
        }
    }

    // Module-level mutable containers, only where the file actually runs concurrently.
    if !py_uses_concurrency(root, &nodes, src) {
        return findings;
    }
    let guarded = py_has_lock(&nodes, src);
    let containers = py_module_containers(root, src);
    findings.extend(py_check_then_act(root, &containers, rel, src));
    findings.extend(py_nonatomic_rmw(root, rel, guarded, src));
    for stmt in children(root) {
        let assign = py_top_assignment(stmt);
        if assign.kind() != "assignment" {
            continue;
        }
        let Some(left) = field(Some(assign), "left") else { continue };
        if left.kind() != "identifier" {
            continue;
        }
        if py_rhs_is_mutable(field(Some(assign), "right"), src) {
            let name = text(Some(left), src);
            if guarded {
                findings.push(mk("possibly_unguarded_shared_state", &name, REVIEW, rel, assign));
            } else {
                findings.push(mk("unguarded_shared_state", &name, EXPOSED, rel, assign));
            }
        }
    }
    findings
}

// --- the JavaScript and TypeScript scanner -----------------------------------------
//
// One event loop, so the race is not a data race: it is an async check-then-act. A check on
// shared instance state, then an await that yields the loop to another task, then a mutation
// of the same state. The awaited gap is where a concurrent task can invalidate the check,
// and the await in the body IS the concurrency, so the shape is self-gating.

const JS_CHECK: &[&str] = &["has", "get", "includes", "find", "indexOf", "hasOwnProperty"];
const JS_MUTATE: &[&str] = &["set", "add", "push", "delete", "unshift", "pop", "splice"];

pub(crate) fn scan_jsts(root: Node, rel: &str, sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    let mut findings = Vec::new();
    for n in descendants(root).into_iter().filter(|n| n.kind() == "if_statement") {
        let Some(cons) = field(Some(n), "consequence") else { continue };
        // No awaited yield in the body means no async check-then-act.
        if !descendants(cons).into_iter().any(|x| x.kind() == "await_expression") {
            continue;
        }
        let checked = receivers_by_method(field(Some(n), "condition"), JS_CHECK, sp, src);
        let mutated = receivers_by_method(Some(cons), JS_MUTATE, sp, src);
        for recv in checked.intersection(&mutated) {
            findings.push(mk("async_toctou", recv, REVIEW, rel, n));
        }
    }
    findings
}

// --- the Go scanner ----------------------------------------------------------------
//
// The canonical Go race: a goroutine writes to a variable captured from the enclosing scope
// with no synchronisation. Go has no borrow checker and its maps are not concurrent-safe, so
// this is a genuine data race. A write to a name NOT declared inside the closure is a
// captured write, downgraded where the body holds a lock or sends on a channel.

const GO_SYNC_METHODS: &[&str] = &["Lock", "Unlock", "RLock", "RUnlock", "Store", "Add",
                                   "CompareAndSwap", "Swap"];

/// The base variable a write targets: `x` is x, `m[k]` is m, `obj.f` is obj.
///
/// A loop rather than a call to itself: `a.b.c[i][j].d` is one wrapper per step, and the
/// depth is the audited file's business rather than anyone's choice here.
fn go_assign_base(node: Option<Node>, src: &[u8]) -> Option<String> {
    let mut current = node;
    while let Some(n) = current {
        if n.kind() == "identifier" {
            return Some(text(Some(n), src));
        }
        if matches!(n.kind(), "index_expression" | "selector_expression") {
            current = children(n).into_iter().find(|c| c.is_named());
            continue;
        }
        return None;
    }
    None
}

fn go_assign_bases(left: Option<Node>, src: &[u8]) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let mut stack: Vec<Node> = left.into_iter().collect();
    while let Some(node) = stack.pop() {
        if node.kind() == "expression_list" {
            stack.extend(children(node).into_iter().filter(|c| c.is_named()));
            continue;
        }
        if let Some(base) = go_assign_base(Some(node), src) {
            out.insert(base);
        }
    }
    out
}

/// Names local to the closure: its parameters and its short declarations.
fn go_declared_inside(fl: Node, body: Node, src: &[u8]) -> BTreeSet<String> {
    let mut names = BTreeSet::new();
    if let Some(params) = field(Some(fl), "parameters") {
        names.extend(descendants(params).into_iter().filter(|c| c.kind() == "identifier")
                     .map(|c| text(Some(c), src)));
    }
    for n in descendants(body).into_iter().filter(|n| n.kind() == "short_var_declaration") {
        names.extend(go_assign_bases(field(Some(n), "left"), src));
    }
    names
}

fn go_has_sync(body: Node, src: &[u8]) -> bool {
    descendants(body).into_iter().any(|n| {
        if n.kind() == "send_statement" {
            return true;
        }
        n.kind() == "call_expression" && match field(Some(n), "function") {
            Some(f) => f.kind() == "selector_expression"
                && GO_SYNC_METHODS.contains(&text(field(Some(f), "field"), src).as_str()),
            None => false,
        }
    })
}

pub(crate) fn scan_go(root: Node, rel: &str, _sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    let mut findings = Vec::new();
    for go in descendants(root).into_iter().filter(|n| n.kind() == "go_statement") {
        let Some(fl) = descendants(go).into_iter().find(|x| x.kind() == "func_literal")
            else { continue };
        let Some(body) = field(Some(fl), "body") else { continue };
        let declared = go_declared_inside(fl, body, src);
        let severity = if go_has_sync(body, src) { CANDIDATE } else { REVIEW };
        let mut seen: BTreeSet<String> = BTreeSet::new();
        for n in descendants(body) {
            let targets = if n.kind() == "assignment_statement" {
                go_assign_bases(field(Some(n), "left"), src)
            } else if matches!(n.kind(), "inc_statement" | "dec_statement") {
                // Filtered rather than subtracted: a set that still admits the absence makes
                // every reader below handle a value the line above had just removed.
                go_assign_base(children(n).into_iter().find(|c| c.is_named()), src)
                    .into_iter().collect()
            } else {
                BTreeSet::new()
            };
            for t in targets {
                // The blank identifier is a discard, not a write.
                if !t.is_empty() && t != "_" && !declared.contains(&t) && !seen.contains(&t) {
                    seen.insert(t.clone());
                    findings.push(mk("goroutine_shared_write", &t, severity, rel, n));
                }
            }
        }
    }
    findings
}

// --- the Java scanner ---------------------------------------------------------------
//
// The distinctly Java hazard: a non-final static field of a mutable, non-thread-safe
// collection, which is shared class-level state reachable from every thread with no
// synchronisation on the field itself. Concurrent and synchronised types are excluded,
// because those are safe by design.

const JAVA_MUTABLE_TYPES: &[&str] = &["Map", "HashMap", "LinkedHashMap", "TreeMap", "List",
                                      "ArrayList", "LinkedList", "Set", "HashSet",
                                      "LinkedHashSet", "TreeSet", "Collection", "Queue",
                                      "Deque", "ArrayDeque"];

fn java_base_type(typ: Option<Node>, src: &[u8]) -> Option<String> {
    let typ = typ?;
    let last_segment = |s: String| s.rsplit('.').next().unwrap_or("").to_string();
    if typ.kind() == "generic_type" {
        let base = children(typ).into_iter()
            .find(|c| matches!(c.kind(), "type_identifier" | "scoped_type_identifier"))?;
        return Some(last_segment(text(Some(base), src)));
    }
    if matches!(typ.kind(), "type_identifier" | "scoped_type_identifier") {
        return Some(last_segment(text(Some(typ), src)));
    }
    None
}

pub(crate) fn scan_java(root: Node, rel: &str, _sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    let mut findings = Vec::new();
    for fd in descendants(root).into_iter().filter(|n| n.kind() == "field_declaration") {
        let mods = children(fd).into_iter().find(|c| c.kind() == "modifiers");
        let words: Vec<String> =
            text(mods, src).split_whitespace().map(|w| w.to_string()).collect();
        if !words.iter().any(|w| w == "static") || words.iter().any(|w| w == "final") {
            continue;
        }
        let base = java_base_type(field(Some(fd), "type"), src);
        if base.map(|b| JAVA_MUTABLE_TYPES.contains(&b.as_str())).unwrap_or(false) {
            let name = field(Some(fd), "declarator").and_then(|d| field(Some(d), "name"));
            findings.push(mk("static_mutable_field", &text(name, src), REVIEW, rel, fd));
        }
    }
    findings
}

// --- the Ruby scanner ---------------------------------------------------------------
//
// The interpreter lock serialises bytecode, but a compound update is several bytecodes, so a
// compound assignment to a class variable, which is shared across every instance and thread,
// still loses updates under a thread, and the alternative implementations have true
// parallelism.

fn ruby_uses_threads(root: Node, src: &[u8]) -> bool {
    descendants(root).into_iter().any(|n| {
        if n.kind() == "constant" && text(Some(n), src) == "Thread" {
            return true;
        }
        n.kind() == "call" && match field(Some(n), "receiver") {
            Some(recv) => text(Some(recv), src) == "Thread",
            None => false,
        }
    })
}

pub(crate) fn scan_ruby(root: Node, rel: &str, _sp: &LangSpec, src: &[u8]) -> Vec<Finding> {
    if !ruby_uses_threads(root, src) {
        return Vec::new();
    }
    let mut findings = Vec::new();
    for n in descendants(root).into_iter().filter(|n| n.kind() == "operator_assignment") {
        if let Some(left) = field(Some(n), "left") {
            if left.kind() == "class_variable" {
                findings.push(mk("nonatomic_rmw", &text(Some(left), src), REVIEW, rel, n));
            }
        }
    }
    findings
}


#[cfg(test)]
mod tests {
    use super::*;
    use crate::indicators::thread_surface::scanner_for;
    use crate::lang_spec::spec_for;
    use crate::parser_for;

    /// Every finding one scanner makes over one source, as (kind, symbol, severity).
    fn found(source: &str, lang: &str, rel: &str) -> Vec<(String, String, &'static str)> {
        let mut parser = parser_for(lang);
        let src = source.as_bytes().to_vec();
        let tree = parser.parse(&src, None).expect("a parse");
        let sp = spec_for(lang).expect("a language row");
        let scanner = scanner_for(lang).expect("a scanner");
        scanner(tree.root_node(), rel, sp, &src)
            .into_iter()
            .map(|f| (f.kind, f.symbol, f.severity))
            .collect()
    }

    #[test]
    fn a_hand_asserted_send_or_sync_is_the_motivating_case() {
        let got = found("pub struct Coord;\nunsafe impl Sync for Coord {}\n\
                         unsafe impl Send for Coord {}\n", "rust", "src/lib.rs");
        assert_eq!(got, vec![
            ("unsafe_impl_sync".to_string(), "Coord".to_string(), EXPOSED),
            ("unsafe_impl_send".to_string(), "Coord".to_string(), EXPOSED),
        ]);
    }

    #[test]
    fn a_static_mut_is_global_state_with_no_compiler_guard() {
        let got = found("static mut COUNTER: u32 = 0;\nstatic LIMIT: u32 = 5;\n",
                        "rust", "src/lib.rs");
        assert_eq!(got, vec![("static_mut".into(), "COUNTER".into(), EXPOSED)]);
    }

    #[test]
    fn an_atomic_protocol_is_not_an_unguarded_read_modify_write() {
        // The exclusion that keeps the shape off correct lock-free code: a receiver using a
        // compare-exchange in the same function is running a real protocol.
        let racy = "impl S {\n  fn bump(&self) {\n    let v = self.n.load(Ordering::SeqCst);\n\
                    self.n.store(v + 1, Ordering::SeqCst);\n  }\n}\n";
        let protocol = "impl S {\n  fn bump(&self) {\n    let v = self.n.load(Ordering::SeqCst);\n\
                        let _ = self.n.compare_exchange(v, v + 1, Ordering::SeqCst, \
                        Ordering::SeqCst);\n    self.n.store(v, Ordering::SeqCst);\n  }\n}\n";
        assert_eq!(found(racy, "rust", "src/lib.rs"),
                   vec![("nonatomic_rmw".into(), "self.n".into(), CANDIDATE)]);
        assert!(found(protocol, "rust", "src/lib.rs").is_empty());
    }

    #[test]
    fn an_exclusive_borrow_cannot_be_called_by_two_threads_at_once() {
        // `&mut self` is exclusive by the borrow checker, so the same body is not a race.
        let shared = "impl S {\n  fn f(&self) {\n    let v = self.n.load(Ordering::SeqCst);\n\
                      self.n.store(v, Ordering::SeqCst);\n  }\n}\n";
        let exclusive = shared.replace("&self", "&mut self");
        assert_eq!(found(shared, "rust", "src/lib.rs").len(), 1);
        assert!(found(&exclusive, "rust", "src/lib.rs").is_empty());
    }

    #[test]
    fn a_relaxed_load_that_gates_a_branch_outranks_one_that_counts() {
        let gating = "impl S {\n  fn f(&self) {\n    if self.flag.load(Ordering::Relaxed) \
                      { }\n  }\n}\n";
        let counting = "impl S {\n  fn f(&self) {\n    self.hits.fetch_add(1, \
                        Ordering::Relaxed);\n  }\n}\n";
        assert_eq!(found(gating, "rust", "src/lib.rs"),
                   vec![("relaxed_guard".into(), "self.flag".into(), REVIEW)]);
        assert_eq!(found(counting, "rust", "src/lib.rs"),
                   vec![("relaxed_ordering".into(), "self.hits".into(), CANDIDATE)]);
    }

    #[test]
    fn a_test_file_keeps_its_overrides_and_loses_the_rest() {
        // The overrides are concurrency surface wherever they sit; the per-function shapes
        // are not production surface in a test file.
        let source = "unsafe impl Sync for T {}\nimpl S {\n  fn f(&self) {\n    \
                      let v = self.n.load(Ordering::SeqCst);\n    \
                      self.n.store(v, Ordering::SeqCst);\n  }\n}\n";
        assert_eq!(found(source, "rust", "src/lib.rs").len(), 2);
        assert_eq!(found(source, "rust", "src/tests.rs"),
                   vec![("unsafe_impl_sync".into(), "T".into(), EXPOSED)]);
    }

    #[test]
    fn python_flags_a_mutable_default_whatever_the_file_imports() {
        let got = found("def f(seen={}):\n    return seen\n", "python", "m.py");
        assert_eq!(got, vec![("mutable_default_arg".into(), "seen".into(), REVIEW)]);
    }

    #[test]
    fn a_module_container_is_surface_only_where_the_file_runs_work_concurrently() {
        let alone = "CACHE = {}\n";
        let threaded = "import threading\nCACHE = {}\n";
        let guarded = "import threading\nLOCK = threading.Lock()\nCACHE = {}\n";
        assert!(found(alone, "python", "m.py").is_empty());
        assert_eq!(found(threaded, "python", "m.py"),
                   vec![("unguarded_shared_state".into(), "CACHE".into(), EXPOSED)]);
        // A lock in the file downgrades it: the guard is present but unproven.
        let with_lock = found(guarded, "python", "m.py");
        assert!(with_lock.iter().any(|(kind, symbol, severity)|
            kind == "possibly_unguarded_shared_state" && symbol == "CACHE" && *severity == REVIEW),
            "{with_lock:?}");
    }

    #[test]
    fn javascript_wants_the_awaited_gap_and_not_merely_the_branch() {
        let awaited = "class S {\n  async f(k) {\n    if (this.seen.has(k)) {\n      \
                       await g();\n      this.seen.set(k, 1);\n    }\n  }\n}\n";
        let immediate = awaited.replace("      await g();\n", "");
        assert_eq!(found(awaited, "javascript", "m.js"),
                   vec![("async_toctou".into(), "this.seen".into(), REVIEW)]);
        assert!(found(&immediate, "javascript", "m.js").is_empty());
    }

    #[test]
    fn a_goroutine_writing_its_own_local_is_not_a_captured_write() {
        let captured = "package p\nfunc f() {\n  n := 0\n  go func() { n = 1 }()\n}\n";
        let local = "package p\nfunc f() {\n  go func() { m := 0; m = 1; _ = m }()\n}\n";
        assert_eq!(found(captured, "go", "m.go"),
                   vec![("goroutine_shared_write".into(), "n".into(), REVIEW)]);
        assert!(found(local, "go", "m.go").is_empty());
    }

    #[test]
    fn a_synchronised_goroutine_body_is_the_lower_tier() {
        let source = "package p\nfunc f() {\n  n := 0\n  go func() { mu.Lock(); n = 1 }()\n}\n";
        assert_eq!(found(source, "go", "m.go"),
                   vec![("goroutine_shared_write".into(), "n".into(), CANDIDATE)]);
    }

    #[test]
    fn a_java_static_collection_is_surface_unless_it_cannot_be_rebound() {
        let source = "class C {\n  static Map<String,Integer> hits = new HashMap<>();\n  \
                      static final Map<String,Integer> fixed = new HashMap<>();\n  \
                      static ConcurrentHashMap<String,Integer> safe = new ConcurrentHashMap<>();\n\
                      }\n";
        assert_eq!(found(source, "java", "C.java"),
                   vec![("static_mutable_field".into(), "hits".into(), REVIEW)]);
    }

    #[test]
    fn ruby_wants_a_class_variable_in_a_file_that_uses_threads() {
        let threaded = "class C\n  @@count = 0\n  def self.bump\n    @@count += 1\n  end\n  \
                        Thread.new { bump }\nend\n";
        let alone = "class C\n  @@count = 0\n  def self.bump\n    @@count += 1\n  end\nend\n";
        assert_eq!(found(threaded, "ruby", "c.rb"),
                   vec![("nonatomic_rmw".into(), "@@count".into(), REVIEW)]);
        assert!(found(alone, "ruby", "c.rb").is_empty());
    }

}
