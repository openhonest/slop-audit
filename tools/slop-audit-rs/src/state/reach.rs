//! How ONE reference to a piece of state reaches a decision. Ported from
//! l1_analyzer.state_reach.
//!
//! Given `self.sessions` at one site, this answers what the surrounding syntax does with
//! it: selects an arm, writes into it, hands it out, keys a lookup with it, or nothing
//! this reader has a rule for. Every verdict the classifier publishes is a roll-up of
//! these per-reference answers, so a construct with no rule here is a construct the whole
//! measure goes silent on.
//!
//! THE ORDER OF THE ROWS IS THE RULE. Each dispatch below is a list of rows tried in turn,
//! and several of them are correct only because an earlier row has already declined. The
//! comments say which, and moving one is a change in behaviour rather than in style.
//!
//! The dispatch ends in a TOTAL ROW that says a construct has no rule rather than reaching
//! a verdict, and that placement is the point. Every row above it has declined by the time
//! it is reached, so an unhandled shape comes out unmeasured by construction rather than
//! by whoever remembered to check.

use crate::lang_spec::{lookup, LangSpec};
use crate::nodes::{
    bare_condition, children, descendants, field, first_arg, first_named, is_opaque_unary,
    is_write_target, local_descendants, mutable_alias_value, same, sub_collection, sub_key,
    text, unwrap_unary, written_in_place,
};
use crate::state::cells::{
    is_closed_set, is_unbounded_value, keyed_read, membership_operands, cell_key, ClosedSets,
};
use crate::state::partition::{self, Reach, DYNAMIC_DISPATCH, FINITE, UNBOUNDED, UNDECIDED};
use tree_sitter::Node;

/// Builtins whose result is bounded however wide their argument is.
const BOUNDED_BUILTINS: &[&str] =
    &["len", "isinstance", "bool", "id", "type", "hash", "ord", "abs"];

/// Builtins that consume a value as an effect or assertion, not a partitioning decision.
const EFFECT_CALLS: &[&str] = &["print", "repr", "str", "format", "log", "logging"];

/// Every spelling of a comparison operator across the nine grammars.
/// Every operator that ASKS about a value rather than deriving one. Public because the
/// finite-testability filters ask the same question of the same list, and two copies of it
/// is two owners of one fact with nothing checking they agree.
pub const COMPARISON_OPS: &[&str] = &["!=", "!==", "<", "<=", "<>", "==", "===", ">", ">="];

/// How far a value is followed from the state it came from to the decision it reaches.
///
/// Three, because a fourth hop has never changed a verdict on the corpus and the walk is
/// quadratic in the reference count.
pub const REACH_DEPTH: i32 = 3;

fn callee_name(call: Option<Node>, sp: &LangSpec, src: &[u8]) -> String {
    let Some(call) = call else { return String::new() };
    if !sp.call_types.contains(&call.kind()) {
        return String::new();
    }
    let slot = if sp.flat_call { sp.call_name } else { Some(sp.call_fn) };
    match slot {
        Some(name) => text(field(Some(call), name), src),
        None => String::new(),
    }
}

/// Whether this node compares two things. An absent node compares nothing.
///
/// The reference declared that it takes one and asked it for its type on the next line.
fn is_comparison(node: Option<Node>, src: &[u8]) -> bool {
    let Some(node) = node else { return false };
    // Python always spells a comparison with its own node type.
    if node.kind() == "comparison_operator" {
        return true;
    }
    COMPARISON_OPS.contains(&text(field(Some(node), "operator"), src).as_str())
}

/// The reference is the target of an assignment whose operator READS it before writing.
///
/// Only the conditional operators, not the arithmetic ones. `x += 1` also reads x, but its
/// read is of the whole value and is already carried by the accumulator rule; a conditional
/// assignment's read is a PRESENCE test on a key, which is what decides a cache.
fn reads_its_own_target(reference: Node, sp: &LangSpec, src: &[u8]) -> bool {
    let mut node = reference;
    while let Some(parent) = node.parent() {
        if sp.assign_types.contains(&parent.kind()) {
            break;
        }
        if !sp.subscript_types.contains(&parent.kind())
            && !sp.member_types.contains(&parent.kind()) {
            return false;
        }
        node = parent;
    }
    let Some(parent) = node.parent() else { return false };
    if !same(field(Some(parent), sp.assign_left), Some(node)) {
        return false;
    }
    sp.read_write_assign_ops.contains(&text(field(Some(parent), "operator"), src).as_str())
}

/// How the READ half of a conditional assignment reaches a decision.
///
/// A keyed target is a keyed read, so an open key is unbounded exactly as it is on the
/// right-hand side. A bare name is the value itself meeting a presence test, which is the
/// two-class split any truthiness test makes.
fn categorize_read(reference: Node, sp: &LangSpec, cells: Option<i64>, src: &[u8]) -> Reach {
    if let Some(parent) = reference.parent() {
        if sp.subscript_types.contains(&parent.kind())
            && same(sub_collection(parent, sp), Some(reference)) {
            return keyed_read(sub_key(parent, sp), sp, cells, src);
        }
    }
    partition::finite(2, true, "truthy")
}

/// The local an `out` argument of this call binds, or nothing.
///
/// `_d.Remove(k, out var v)` hands the stored value back through `v`. `Remove` is a
/// mutating method, so the reference read as a write and stopped, and the value leaving
/// through the out argument was never followed: the dictionary came back neutral and
/// observe-only on a source that branches on the removed value.
///
/// A rule watching the invocation's own value cannot see it, because the invocation returns
/// a bool. The value goes out through a declaration inside the argument, which binds a
/// local, and following a local is machinery this module has.
///
/// The NAME, not the first named child: `out var v` parses as an implicit type followed by
/// the identifier, so taking the first named child took the type and the rule silently did
/// nothing.
///
/// C# alone of the nine spells this; the other eight declare an empty vocabulary.
fn out_argument_local<'t>(call: Option<Node<'t>>, sp: &LangSpec) -> Option<Node<'t>> {
    if sp.out_argument_types.is_empty() {
        return None;
    }
    let call = call?;
    for node in descendants(call).into_iter()
        .filter(|n| sp.out_argument_types.contains(&n.kind())) {
        for child in children(node).into_iter().filter(|c| c.is_named()) {
            if child.kind() == "identifier" {
                return Some(child);
            }
        }
    }
    None
}

/// The value half of a local binding, and whether the grammar names it.
///
/// Absent means "the last named child" rather than "not available": C# alone leaves the
/// initialiser unnamed, and the vocabulary records which.
fn bound_value<'t>(parent: Node<'t>, value_field: Option<&str>) -> Option<Node<'t>> {
    match value_field {
        Some(name) => field(Some(parent), name),
        None => children(parent).into_iter().filter(|c| c.is_named()).next_back(),
    }
}

/// The local this reference is being bound INTO, or nothing.
///
/// `var entries = _entries;` binds the state's value to a local. Every grammar carries the
/// link, in its own way, and the vocabulary records which.
///
/// The NAME node comes back, so the caller can look for what the function does with it.
/// Only a plain identifier counts: a destructuring pattern binds several names and none of
/// them is this value on its own.
fn local_binding_name<'t>(reference: Node<'t>, sp: &LangSpec) -> Option<Node<'t>> {
    let parent = reference.parent()?;
    let (_, name_field, value_field) =
        *sp.local_binding.iter().find(|(kind, _, _)| *kind == parent.kind())?;
    let value = bound_value(parent, value_field)?;
    if !same(Some(value), Some(reference)) {
        return None;
    }
    let name = field(Some(parent), name_field)?;
    if name.kind() == "identifier" { Some(name) } else { None }
}

/// Whether this value is bound by a declaration that names nothing to bind it to.
///
/// `let _ = f();` in Rust: the value goes nowhere and nobody reads it.
///
/// Told apart from destructuring by whether the pattern is a NAMED node. Rust spells the
/// wildcard as an anonymous token, so it is present in the tree and carries no name, while
/// a tuple pattern is named. The reference's first draft asked whether the pattern was
/// absent and found it present, which is why the distinction is written down rather than
/// assumed: destructuring takes the value apart and is a question this reader leaves to the
/// total row, and the discard is not that question.
fn bound_to_the_discard(value: Node, sp: &LangSpec) -> bool {
    let Some(parent) = value.parent() else { return false };
    let Some((_, name_field, value_field)) =
        sp.local_binding.iter().find(|(kind, _, _)| *kind == parent.kind()).copied()
    else { return false };
    let bound = bound_value(parent, value_field);
    let name = field(Some(parent), name_field);
    same(bound, Some(value)) && name.map(|n| !n.is_named()).unwrap_or(false)
}

/// The partition a switch cuts in its subject: one class per arm, plus one for the values
/// that match no arm when there is no default.
///
/// UNORDERED on purpose. There is no value just above a case label, so limit testing buys
/// nothing here and every class costs its own test. That is the distinction the worst tier
/// rests on, and counting these arms is what lets a switch contribute to it: before this
/// the subject was an unread construct, and a state whose whole job is selecting behaviour
/// contributed no classes at all.
///
/// The key is the switch's own span, so the same switch read twice is one discriminator and
/// two different switches on one state are two.
fn switch_partition(switch: Node, arm_type: &str, src: &[u8]) -> Reach {
    let arms: Vec<Node> =
        descendants(switch).into_iter().filter(|n| n.kind() == arm_type).collect();
    let has_default = arms.iter().any(|a| {
        text(Some(*a), src).split(':').next().unwrap_or("").contains("default")
    });
    let classes = arms.len() as i64 + if has_default { 0 } else { 1 };
    partition::finite(classes, false, format!("switch:{}", switch.start_byte()))
}

/// The reach of a collection being WALKED by a loop, or nothing when this shape is not
/// that.
///
/// Iterating reads every cell the collection holds, so its reach is the cell set and
/// nothing wider. `for k := range s.m` had no row anywhere and came back as a construct
/// nobody had taught the reader, which inflated Go's silence on the plainest loop it has.
///
/// Asked from BOTH the categoriser and the flow, which is why it is a function. It lived in
/// the categoriser alone, so it saw a loop over the state itself and never a loop over a
/// value derived from it.
///
/// Read from the loop's own field naming what is walked, never the node type alone. Rust
/// holds the pattern, the value and the body as three children of one node, so matching on
/// the type would read a state mentioned anywhere in the BODY as the collection being
/// walked, which is a different claim and a false one.
///
/// Matched against the field as written AND as unwrapped, because a reference arrives here
/// either way: Go's ranged value is the bare name, and Rust's arrives already peeled out of
/// the borrow the passthrough row walked through on the way up.
fn iterated_reach(value: Node, parent: Node, sp: &LangSpec, cells: Option<i64>) -> Option<Reach> {
    let walked = lookup(sp.iterate_types, parent.kind())?;
    let holder = field(Some(parent), walked)?;
    if !same(Some(holder), Some(value))
        && !same(unwrap_unary(Some(holder), sp), Some(value)) {
        return None;
    }
    Some(match cells {
        Some(cells) => partition::finite(cells + 1, false, "cells"),
        None => partition::unbounded(),
    })
}

/// Why a call's reaching-set could not be decided, carrying which KIND of silence it is.
///
/// The test is where the CALLEE comes from. A bare name is inside our reach: it is a
/// builtin missing from the lists, or a function defined in the repository, and either way
/// the fix is ours. A name reached through another object is a boundary we cannot read,
/// except when that object is the receiver of the class under analysis, whose methods are
/// in scope by the spec's own scoping rule. A callee that is not a name at all is computed,
/// so nobody can enumerate it by reading.
fn silence_kind(call: Option<Node>, sp: &LangSpec, src: &[u8]) -> Reach {
    let Some(call) = call else { return partition::undecided(DYNAMIC_DISPATCH) };
    if sp.flat_call {
        let receiver = field(Some(call), sp.call_recv);
        return partition::undecided(if receiver.is_some() {
            partition::EXTERNAL_BOUNDARY
        } else {
            partition::UNMODELED_CALLEE
        });
    }
    let Some(fn_node) = field(Some(call), sp.call_fn) else {
        return partition::undecided(DYNAMIC_DISPATCH);
    };
    if sp.member_types.contains(&fn_node.kind()) {
        let obj = field(Some(fn_node), sp.mem_object);
        let ours = obj.map(|o| sp.this_idents.contains(&text(Some(o), src).as_str()))
            .unwrap_or(false);
        return partition::undecided(if ours {
            partition::UNMODELED_CALLEE
        } else {
            partition::EXTERNAL_BOUNDARY
        });
    }
    if fn_node.kind() == "identifier" {
        return partition::undecided(partition::UNMODELED_CALLEE);
    }
    partition::undecided(DYNAMIC_DISPATCH)
}

/// What an argument position does with the value, shared by the two dispatches that reach
/// one. The rows are ordered: a writing builtin before a bounded one before an effect one,
/// and the silence kind last.
fn argument_reach(arglist: Node, sp: &LangSpec, closed_sets: &ClosedSets,
                  cells: Option<i64>, depth: i32, src: &[u8]) -> Reach {
    let call = arglist.parent();
    let name = callee_name(call, sp, src);
    if sp.writing_builtins.contains(&name.as_str()) {
        // `delete(m, k)`: removes and returns nothing.
        return partition::write();
    }
    if BOUNDED_BUILTINS.contains(&name.as_str()) || sp.extra_bounded.contains(&name.as_str()) {
        return flow(call, sp, closed_sets, cells, depth, src);
    }
    if EFFECT_CALLS.contains(&name.as_str()) {
        return partition::output();
    }
    silence_kind(call, sp, src)
}

/// How a value reaches on when a MEMBER ACCESS is taken off it, or nothing when this shape
/// is not that.
///
/// A mutating method is a write, a keyed map read is subscript-like, anything else flows
/// on. Nested-call languages only; flat-call languages spell the member access and the call
/// as one node and are handled by their own row.
///
/// Read from BOTH ends of a method chain, which is why it is a function. It lived inline in
/// the categoriser, so it decided the first link of `self.map.entry(k).or_default().push(v)`
/// and nothing decided the rest: a call RESULT reached through another member access had no
/// row anywhere, and every chain longer than one call fell to the total row.
///
/// That is not a missing case, it is the second half of every chain. A production run over
/// a public Rust crate on 2026-08-30 published 88 per cent of read state finitely testable
/// beside its own note that 290 of 392 state-keeping places were unread, and this shape was
/// most of them.
fn member_reach(value: Node, parent: Node, sp: &LangSpec, closed_sets: &ClosedSets,
                cells: Option<i64>, depth: i32, src: &[u8]) -> Option<Reach> {
    if sp.flat_call || !sp.member_types.contains(&parent.kind()) {
        return None;
    }
    if !same(field(Some(parent), sp.mem_object), Some(value)) {
        return None;
    }
    let attr = text(field(Some(parent), sp.mem_attr), src);
    let gp = parent.parent();
    let called = gp.map(|g| sp.call_types.contains(&g.kind())
                        && same(field(Some(g), sp.call_fn), Some(parent)))
        .unwrap_or(false);
    if called && sp.dispatch_methods.contains(&attr.as_str()) {
        // A stored callable: the target is unbounded.
        return Some(partition::undecided(DYNAMIC_DISPATCH));
    }
    if called && sp.mutating.contains(&attr.as_str()) {
        // A mutating call can still hand the value OUT. `_d.Remove(k, out var v)` writes
        // the dictionary AND returns the removed value through `v`, so a rule that stops
        // at the write never sees the branch on it.
        if let Some(out_local) = out_argument_local(gp, sp) {
            return Some(follow_local(value, out_local, sp, closed_sets, cells, depth, src));
        }
        return Some(partition::write());
    }
    if called && sp.keyed_read.contains(&attr.as_str()) {
        return Some(keyed_read(first_arg(gp, sp), sp, cells, src));
    }
    if called {
        // The result flows on: a clone, a length, an accessor.
        return Some(flow(gp, sp, closed_sets, cells, depth, src));
    }
    // A plain field access: `self.x.y`.
    Some(flow(Some(parent), sp, closed_sets, cells, depth, src))
}

/// What the state reaches THROUGH a local it was copied into.
///
/// The largest family of unread constructs in the corpus, 194 sites, and it needed a ROW
/// rather than a new kind of silence. The tree carries the binding and this module already
/// finds references inside a scope; following a local is that same walk bounded to the
/// enclosing function.
///
/// What the tree does NOT carry is whether the copy aliases: `var e = _m` shares the object
/// for a reference type and copies it for a value type, and no types are resolved here.
/// That matters only for a WRITE through the local reaching the state, so a write keeps its
/// own refusal and is not folded into the reads below.
///
/// `depth` bounds the walk. `a = b; b = a` inside one function would otherwise recurse
/// forever, and a chain longer than a few hops is not a chain a reader is following either.
fn follow_local(reference: Node, name: Node, sp: &LangSpec, closed_sets: &ClosedSets,
                cells: Option<i64>, depth: i32, src: &[u8]) -> Reach {
    if depth <= 0 {
        return silence_kind(Some(reference), sp, src);
    }
    let mut scope = Some(reference);
    while let Some(n) = scope {
        if sp.func_types.contains(&n.kind()) {
            break;
        }
        scope = n.parent();
    }
    // Module level: the binding is its own state.
    let Some(scope) = scope else { return partition::output() };
    let key = text(Some(name), src);
    let uses: Vec<Node> = local_descendants(scope, &[])
        .into_iter()
        .filter(|n| n.kind() == "identifier" && text(Some(*n), src) == key)
        .filter(|n| !same(Some(*n), Some(name)))
        .collect();
    // Bound and never read: the value came to rest.
    if uses.is_empty() {
        return partition::output();
    }
    let reaches: Vec<Reach> = uses.into_iter()
        .map(|u| categorize(u, sp, closed_sets, cells, depth - 1, src))
        .collect();
    if let Some(undecided) = reaches.iter().find(|r| r.kind == UNDECIDED) {
        return undecided.clone();
    }
    if reaches.iter().any(|r| r.kind == UNBOUNDED) {
        return partition::unbounded();
    }
    // The WIDEST of them, and that is a stated limit rather than a roll-up. The categoriser
    // answers with one reach per reference, so several uses of one local collapse into one
    // here and the narrower ones are lost. Taking the widest UNDER-counts the state's
    // partition, which is the direction this module takes when it cannot say more.
    match reaches.iter().filter(|r| r.kind == FINITE).max_by_key(|r| r.classes) {
        Some(widest) => widest.clone(),
        None => partition::output(),
    }
}

/// How this single reference to a state value is consumed.
pub fn categorize(reference: Node, sp: &LangSpec, closed_sets: &ClosedSets,
                  cells: Option<i64>, depth: i32, src: &[u8]) -> Reach {
    let Some(parent) = reference.parent() else { return partition::output() };

    if is_write_target(reference, Some(parent), sp) {
        // A CONDITIONAL ASSIGNMENT IS BOTH HALVES. `@cache[k] ||= compute(k)` tests what is
        // stored at k and stores only if it is absent, so the target is read as surely as
        // it is written. Reading it as a write alone was a false green: the same cache
        // written with an explicit guard came back promiscuous and had to earn its clear
        // through the memoization rule's premises, while this spelling was handed neutral
        // with no premise checked. One operation, two notations, opposite verdicts, and
        // the clean one was the commonest shape in the language.
        if reads_its_own_target(reference, sp, src) {
            return categorize_read(reference, sp, cells, src);
        }
        return partition::write();
    }

    // THE STATE AS THE NAME HALF OF A MEMBER ACCESS: `other.V = s`, `o.v`, `o->v`. In the
    // three languages whose class state is keyed by a bare identifier, a field is
    // enumerated as `v`, so a read of it off ANOTHER receiver puts that identifier on the
    // right of the dot. Every row here was written for the state as the RECEIVER, so the
    // name half fell off the bottom into the unmodelled-construct terminal. It was the
    // largest single shape in the corpus's silence: 173 sites in C# and 142 in Java.
    //
    // The member access IS the reference, so this re-enters the same dispatch one node up
    // rather than deciding anything new. Languages whose state is keyed by the member
    // itself declare no name field and never reach this row.
    if let Some(name_field) = sp.member_name_field {
        if sp.member_types.contains(&parent.kind())
            && same(field(Some(parent), name_field), Some(reference)) {
            if is_write_target(parent, parent.parent(), sp) {
                return partition::write();
            }
            return flow(Some(parent), sp, closed_sets, cells, depth, src);
        }
    }

    // THE STATE COPIED INTO A LOCAL. 194 sites in the corpus came out as constructs with no
    // rule, and the rule they needed is this one. Sits ABOVE the terminal and BELOW the
    // write row, so a local that is itself written keeps the write verdict.
    if let Some(local) = local_binding_name(reference, sp) {
        return follow_local(reference, local, sp, closed_sets, cells, depth, src);
    }

    // THE STATE IS A SWITCH SUBJECT. Its value selects one arm, and the arms are countable
    // from the tree, so this is the one row here that produces CLASSES rather than merely
    // reading a construct. Java wraps the subject in parentheses, which the value-wrapper
    // peel handles, so the comparison is against the unwrapped node.
    for (switch_type, subject_field, arm_type) in sp.switch_types {
        let mut holder = reference.parent();
        while let Some(h) = holder {
            if h.kind() == *switch_type {
                break;
            }
            if !sp.value_wrapper_types.contains(&h.kind()) {
                holder = None;
                break;
            }
            holder = h.parent();
        }
        if let Some(h) = holder {
            if same(unwrap_unary(field(Some(h), subject_field), sp), Some(reference)) {
                let arm = arm_type.unwrap_or("");
                return switch_partition(h, arm, src);
            }
        }
    }

    if let Some(walked) = iterated_reach(reference, parent, sp, cells) {
        return walked;
    }

    // `S(...)`: the state supplies WHAT RUNS. No arm selector reads its value, so
    // call-target position is compositional exactly as return position is, and the meter
    // neither fail-closes nor assumes: it follows the call RESULT like any other.
    if !sp.flat_call && sp.call_types.contains(&parent.kind())
        && same(field(Some(parent), sp.call_fn), Some(reference)) {
        return flow(Some(parent), sp, closed_sets, cells, depth, src);
    }

    // `S[x]` read: indexed by x. An unbounded key gives an unbounded partition.
    if sp.subscript_types.contains(&parent.kind())
        && same(sub_collection(parent, sp), Some(reference)) {
        return keyed_read(sub_key(parent, sp), sp, cells, src);
    }

    // `S.attr`. Nested-call languages only; flat-call languages handle receiver-and-method
    // in the row below, where the member access and the call are one node.
    if let Some(through) = member_reach(reference, parent, sp, closed_sets, cells, depth, src) {
        return through;
    }

    // `S.method(args)` flattened, which is how Java and Ruby spell it.
    if sp.flat_call && sp.call_types.contains(&parent.kind())
        && same(field(Some(parent), sp.call_recv), Some(reference)) {
        let name = match sp.call_name {
            Some(f) => text(field(Some(parent), f), src),
            None => String::new(),
        };
        if sp.dispatch_methods.contains(&name.as_str()) {
            return partition::undecided(DYNAMIC_DISPATCH);
        }
        if sp.mutating.contains(&name.as_str()) {
            return partition::write();
        }
        if sp.keyed_read.contains(&name.as_str()) {
            return keyed_read(first_arg(Some(parent), sp), sp, cells, src);
        }
        return flow(Some(parent), sp, closed_sets, cells, depth, src);
    }

    // `f(..., S, ...)`: an argument to a call.
    if sp.arglist_types.contains(&parent.kind()) {
        return argument_reach(parent, sp, closed_sets, cells, depth, src);
    }

    // Not a write, a call target, a subscript, a member access or an argument: the parent
    // does not CONSUME the value, so the reference is the value itself and the question
    // moves to where that value goes. This is a ROW of the table, not a fallthrough, and
    // the flow below is where the table ends. It matters which of the two is last, because
    // only the last one can be the total handler and only one of them can be it.
    flow(Some(reference), sp, closed_sets, cells, depth, src)
}

/// Categorise how a value DERIVED from the state reaches a decision.
///
/// An absent node reaches no decision, and that is the same answer as a node with nothing
/// above it: the value goes out of the function.
pub fn flow(node: Option<Node>, sp: &LangSpec, closed_sets: &ClosedSets, cells: Option<i64>,
            depth: i32, src: &[u8]) -> Reach {
    let Some(node) = node else { return partition::output() };
    let Some(parent) = node.parent() else { return partition::output() };

    if sp.return_types.contains(&parent.kind()) {
        return partition::output();
    }
    // The value COMES TO REST. Either the language discards it, or hands it back with no
    // keyword, which is what the tail expression of a Ruby body and of a Rust block is.
    // Both reach no arm selector, which is the conclusion the row above draws for a
    // spelled return, so they sit together.
    if sp.sink_types.contains(&parent.kind()) {
        return partition::output();
    }
    // A PATTERN TESTED AGAINST THIS VALUE, which binds on success: `if let Some(v) = x`.
    // The pattern matches or it does not, which is the same two-class split this reader
    // draws for a plain condition, so it shares that key. The branch's own condition field
    // holds the let-condition node rather than the value inside it, so the truthiness row
    // below never sees this and thirteen sites on one crate came back with no rule.
    if sp.binding_condition_types.contains(&parent.kind()) {
        return partition::finite(2, true, "truthy");
    }
    // THE VALUE COMES TO REST in a shape that is not an assignment: `Reply { body: x }`.
    // The assignment row further down draws this conclusion for a value stored in a
    // binding, and a record literal stores it just as finally.
    if sp.resting_types.contains(&parent.kind()) {
        return partition::output();
    }
    // A SWITCH SUBJECT REACHED BY A DERIVED VALUE: `match self.child.id() { .. }`. The
    // categoriser has this rule for the state itself and nothing had it for a value derived
    // from the state, which is the COMMONER of the two.
    for (switch_type, subject_field, arm_type) in sp.switch_types {
        if parent.kind() == *switch_type
            && same(unwrap_unary(field(Some(parent), subject_field), sp), Some(node)) {
            return switch_partition(parent, arm_type.unwrap_or(""), src);
        }
    }
    // The state value itself is INVOKED, possibly through a wrapper: `(self.f)(x)` in Rust
    // reaches the call via a parenthesised expression. Same rule as a direct call in the
    // categoriser: follow the result, do not fail closed.
    //
    // A call RESULT being invoked is method chaining, not state dispatch: `app.get(p)(h)`
    // calls what `app.get` returns and not `app`, so nodes that are themselves a call are
    // excluded here and handled two rows down.
    if !sp.flat_call && !sp.call_types.contains(&node.kind())
        && sp.call_types.contains(&parent.kind())
        && same(field(Some(parent), sp.call_fn), Some(node)) {
        return flow(Some(parent), sp, closed_sets, cells, depth, src);
    }
    // A MEMBER ACCESS TAKEN OFF THIS VALUE, the other half of every method chain. The row
    // above walks from a field access to the call it supplies; this walks from a call
    // result to the next field access, and without it a chain of two calls had a rule for
    // its first link and none for its second.
    //
    // It sits above the rows that store, alias and pass through, because those ask what
    // HAPPENS TO a value and this asks what is TAKEN OFF it, and a chain is the second
    // question before it is ever the first.
    if let Some(through) = member_reach(node, parent, sp, closed_sets, cells, depth, src) {
        return through;
    }
    // A LOOP WALKING THIS VALUE, asked here as well as in the categoriser. A chain that
    // ends in a `for` reaches the loop through this path and not that one.
    if let Some(walked) = iterated_reach(node, parent, sp, cells) {
        return walked;
    }
    // THE TWO ROWS AN EARLIER COMMENT PROMISED AND NOBODY WROTE. Excluding a shape from one
    // row is not the same as handling it, and until 2026-08-17 both forms fell through to
    // the total row. That is why a reference server came back unresolved on its own route
    // table: the decorator is the whole of what that server does with its app object.
    //
    // Both spellings reach the same conclusion. The state is consumed by the inner call,
    // and what comes back is a registrar applied to a definition. The app never reaches an
    // arm selector: nothing branches on it, compares it, or keys a lookup with it.
    // Registration is an effect, which is what the sink row already concludes for the bare
    // statement form.
    if sp.decorator_types.contains(&parent.kind()) {
        return partition::output();
    }
    if !sp.flat_call && sp.call_types.contains(&node.kind())
        && sp.call_types.contains(&parent.kind())
        && same(field(Some(parent), sp.call_fn), Some(node)) {
        return partition::output();
    }
    // THE VALUE IS STORED. A derived value comes to rest in a binding, reaching no arm
    // selector at this site. That is the same conclusion the sink row draws for a value the
    // language discards, and the difference between stored and discarded is not one this
    // row has to settle: neither selects an arm.
    //
    // A DESTRUCTURING TARGET is excluded, and finding out why cost a red test. `first,
    // *rest = self.row` takes the value APART rather than storing it, and a starred target
    // takes an unbounded slice of it, so the two are not the same question. This row first
    // claimed that shape as clean and broke the test that exists to hold exactly this line:
    // a construct with no rule must read as unmeasured, never as clean.
    if sp.assign_types.contains(&parent.kind())
        && same(field(Some(parent), sp.assign_right), Some(node)) {
        let left = field(Some(parent), sp.assign_left);
        let destructuring = left.map(|l| sp.destructuring_types.contains(&l.kind()))
            .unwrap_or(false);
        if !destructuring {
            return partition::output();
        }
    }
    // THE VALUE IS HANDED OUT UNDER ANOTHER NAME, and that name can be written through:
    // `let r = &mut self.v; r.push(1);`. Every rule below and every rule in the filters
    // argues from where this state's OWN references sit, and from this line on there is a
    // write that none of them contains. So the walk stops and says so.
    //
    // It sits ABOVE the wrapper row because Rust's reference expression is on the wrapper
    // list, correctly: a shared borrow cannot be written through. Only the mutability
    // marker separates the two, so the order here is the rule.
    if same(mutable_alias_value(Some(parent), sp), Some(node)) {
        return partition::undecided(partition::MUTABLE_ALIAS);
    }
    // A DERIVED VALUE BOUND TO A LOCAL: `var n = _m.Count;`. The categoriser catches the
    // state bound straight to a local; this catches it bound after passing through
    // something, which is the commoner half.
    if let Some(local) = local_binding_name(node, sp) {
        return follow_local(node, local, sp, closed_sets, cells, depth, src);
    }
    // BOUND TO NOTHING: `let _ = self.deadline.take()`. An ABSENT pattern is the discard; a
    // pattern that is present and is not a plain name is destructuring, which takes the
    // value apart and is a different question this reader leaves to the total row.
    if bound_to_the_discard(node, sp) {
        return partition::output();
    }
    // THE OPERAND IS NOT READ. `sizeof(state)` asks about the TYPE at compile time and
    // never looks at the value, so the state reaches no decision through it and costs no
    // test. Reporting it as unread said we could not tell, when there is nothing to tell.
    if sp.unread_operand_types.contains(&parent.kind()) {
        return partition::output();
    }
    // A transparent wrapper, EXCEPT where the operator consumes rather than wraps.
    if sp.passthrough_types.contains(&parent.kind()) && !is_opaque_unary(Some(parent), sp, src) {
        return flow(Some(parent), sp, closed_sets, cells, depth, src);
    }
    // The host WRITES this value where it stands: `n++`, `c.n++`, `@xs << x`. The host is
    // transparent for the flow, because it also produces a value and that value may still
    // reach a decision: `if (n++ > 3)` is a comparison whichever way the counter moves.
    if same(written_in_place(Some(parent), sp), Some(node)) {
        return flow(Some(parent), sp, closed_sets, cells, depth, src);
    }
    if sp.comparison_types.contains(&parent.kind()) {
        if let Some((left, right)) = membership_operands(Some(parent), sp) {
            if same(Some(node), Some(right)) {
                // `x in S`: the container is asked whether it holds ONE value: two classes,
                // and no boundary between holding it and not. A closed container answers
                // the same way, so the size of the container is not what is split here.
                if is_closed_set(Some(node), closed_sets, src)
                    || !is_unbounded_value(Some(left), sp) {
                    // The SAME discriminator as the subscript read of that key. `"a" in S`
                    // and `S["a"]` ask about one cell: one whether it is there, the other
                    // what is in it, and both cut the partition at that key and nowhere
                    // else. Keying them apart made the commonest table idiom there is count
                    // every key twice: two keys read both ways reported five classes where
                    // three is the count.
                    //
                    // Wrong for a sequence, where `1 in xs` asks about a value and `xs[1]`
                    // about a position, and merging those under-counts. That direction is
                    // the one this module already declares safe for a measure that only
                    // accuses, and the over-count it replaces was not.
                    return partition::finite(2, false, cell_key(Some(left), src));
                }
                return partition::unbounded();
            }
            // `S in FIXED`.
            if is_closed_set(Some(right), closed_sets, src) {
                return crate::state::partition::membership_reach(right, closed_sets, src);
            }
            return partition::unbounded();
        }
        if is_comparison(Some(parent), src) {
            // `S <cmp> constant`: the constant is a cut in an ordered domain, and n
            // distinct cuts leave n+1 intervals that boundary values reach. Keyed on the
            // comparison text so the same cut written twice is one cut, not two.
            return partition::finite(2, true, format!("cmp:{}", text(Some(parent), src)));
        }
        // Arithmetic or logical: the derived value flows on.
        return flow(Some(parent), sp, closed_sets, cells, depth, src);
    }
    // Truthiness is the SAME two-class split wherever it is written, so every site shares
    // one key: `if S:` in fifty methods is two classes, not fifty-one.
    if sp.branch_types.contains(&parent.kind())
        && same(field(Some(parent), sp.branch_cond), Some(node)) {
        return partition::finite(2, true, "truthy");
    }
    if sp.elif_types.contains(&parent.kind())
        && same(field(Some(parent), sp.branch_cond), Some(node)) {
        return partition::finite(2, true, "truthy");
    }
    // The same two-class split, in a branch that names no condition field. Go's `for` holds
    // its condition as a bare first child, so the row above reads nothing there whatever
    // the node type says, and a loop on a bool field came back as a construct with no rule.
    if same(bare_condition(Some(parent), sp), Some(node)) {
        return partition::finite(2, true, "truthy");
    }
    if sp.arglist_types.contains(&parent.kind()) {
        return argument_reach(parent, sp, closed_sets, cells, depth, src);
    }
    if sp.subscript_types.contains(&parent.kind())
        && same(sub_collection(parent, sp), Some(node)) {
        return keyed_read(sub_key(parent, sp), sp, cells, src);
    }
    // THE VALUE AN IN-PLACE WRITE PRODUCED, WHICH NOTHING READS. Every row above has now
    // been offered it and declined, so a bare `c.n++` statement is a write and nothing
    // more. This sits at the bottom rather than beside the transparent-host row on purpose:
    // putting it higher would swallow `if (n++ > 3)`, where the produced value is exactly
    // what the branch decides on.
    if written_in_place(Some(node), sp).is_some() {
        return partition::write();
    }
    // THE TOTAL ROW. Every row above declined, so no rule in this table describes how this
    // construct consumes the value, and the handler says exactly that and stops. It used to
    // be the output verdict, which is a VERDICT: compositional, reaches no decision, costs
    // no tests. That is how a match on a piece of state, a walrus in a condition and a
    // comprehension source came back neutral with an empty silence field: not unhandled,
    // CLEARED.
    partition::unmeasured(node.kind(), parent.kind())
}

/// This reference supplies what RUNS at a call site: `S(...)`, `await S(...)`.
pub fn is_call_target(reference: Node, sp: &LangSpec) -> bool {
    if sp.flat_call {
        return false;
    }
    let Some(parent) = reference.parent() else { return false };
    sp.call_types.contains(&parent.kind())
        && same(field(Some(parent), sp.call_fn), Some(reference))
}

/// The first named child of a node, exposed for the classifier's own rows.
pub fn first_named_child<'t>(node: Option<Node<'t>>) -> Option<Node<'t>> {
    first_named(node)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lang_spec::spec_for;
    use crate::parser_for;

    fn parse(source: &str, lang: &str) -> (tree_sitter::Tree, Vec<u8>) {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        (parser.parse(&bytes, None).expect("a parse"), bytes)
    }

    /// The reach of the LAST reference to `name` in this source, which is the one the
    /// fixture puts in the interesting position.
    fn reach_of(source: &str, lang: &str, name: &str) -> Reach {
        let (tree, src) = parse(source, lang);
        let sp = spec_for(lang).expect("a language row");
        let closed = crate::state::cells::collect_closed_sets(tree.root_node(), &src);
        let refs: Vec<Node> = descendants(tree.root_node())
            .into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == name)
            .collect();
        let last = *refs.last().expect("a reference to the state");
        categorize(last, sp, &closed, None, REACH_DEPTH, &src)
    }

    #[test]
    fn a_truthiness_test_is_two_classes_and_shares_one_key_everywhere() {
        // `if S:` in fifty methods is two classes, not fifty-one.
        let reach = reach_of("S = {}\n\ndef f():\n    if S:\n        pass\n", "python", "S");
        assert_eq!(reach.kind, FINITE);
        assert_eq!(reach.classes, 2);
        assert_eq!(reach.key, "truthy");
    }

    #[test]
    fn a_write_is_a_write_and_reaches_no_decision() {
        let reach = reach_of("S = {}\n\ndef f(v):\n    S = v\n", "python", "S");
        assert_eq!(reach.kind, partition::WRITE);
    }

    #[test]
    fn a_return_hands_the_value_out() {
        let reach = reach_of("S = {}\n\ndef f():\n    return S\n", "python", "S");
        assert_eq!(reach.kind, partition::OUTPUT);
    }

    #[test]
    fn an_open_keyed_read_is_unbounded() {
        let reach = reach_of("S = {}\n\ndef f(k):\n    return S[k]\n", "python", "S");
        assert_eq!(reach.kind, UNBOUNDED);
    }

    #[test]
    fn a_comparison_against_a_constant_cuts_an_ordered_domain() {
        let reach = reach_of("S = 0\n\ndef f():\n    if S > 3:\n        pass\n", "python", "S");
        assert_eq!(reach.kind, FINITE);
        assert!(reach.ordered, "a number has a neighbour, so boundary values reach it");
        assert!(reach.key.starts_with("cmp:"));
    }

    #[test]
    fn a_membership_test_and_a_keyed_read_of_one_cell_share_a_discriminator() {
        // The commonest table idiom there is. Keying them apart counted every key twice:
        // two keys read both ways reported five classes where three is the count.
        let holds = reach_of("S = {}\n\ndef f():\n    return 'a' in S\n", "python", "S");
        let (tree, src) = parse("S = {}\n\ndef f():\n    return S['a']\n", "python");
        let sp = spec_for("python").expect("python");
        let closed = crate::state::cells::collect_closed_sets(tree.root_node(), &src);
        let refs: Vec<Node> = descendants(tree.root_node()).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == "S").collect();
        let reads = categorize(*refs.last().unwrap(), sp, &closed, None, REACH_DEPTH, &src);
        assert_eq!(holds.key, reads.key, "one cell, one cut");
    }

    #[test]
    fn a_switch_cuts_one_class_per_arm_plus_one_for_no_match() {
        // Unordered on purpose: no value sits just above a case label, so limit testing
        // buys nothing and every class costs its own test.
        let source = "class P { static int S = 0;\n\
                      int f() { switch (S) { case 1: return 1; case 2: return 2; } return 0; } }\n";
        let reach = reach_of(source, "java", "S");
        assert_eq!(reach.kind, FINITE);
        assert_eq!(reach.classes, 3, "two arms and no default");
        assert!(!reach.ordered);
    }

    #[test]
    fn a_construct_with_no_rule_is_unmeasured_and_never_cleared() {
        // The defect the total row exists for. Running off the bottom into the output
        // verdict CLEARS the reference, and across eleven repositories that terminal
        // decided 55 per cent of every reference the classifier read.
        let reach = reach_of("S = {}\n\ndef f():\n    return [x for x in S]\n", "python", "S");
        assert_ne!(reach.kind, partition::OUTPUT,
                   "an unhandled construct must not read as compositional");
    }

    #[test]
    fn a_loop_walking_the_state_reads_every_cell_it_holds() {
        // Go declares which child its range clause walks, so the rule can fire. `for k :=
        // range s.m` had no row anywhere before that and came back as a construct nobody
        // had taught the reader, which inflated Go's silence on the plainest loop it has.
        let source = "package p\n\nvar S = map[string]int{}\n\n                      func f() {\n\tfor k := range S {\n\t\t_ = k\n\t}\n}\n";
        assert_eq!(reach_of(source, "go", "S").kind, UNBOUNDED,
                   "an unbounded collection has unbounded cells");
    }

    #[test]
    fn a_python_for_loop_has_no_rule_and_says_so() {
        // Python declares NO iterate types, so the loop row never fires for it and the
        // construct reaches the total row. The reference answers the same, and this holds
        // the behaviour rather than the aspiration: a rule nobody wrote must read as
        // unmeasured, and filing it under a verdict would clear it.
        let reach = reach_of("S = {}\n\ndef f():\n    for k in S:\n        print(k)\n",
                             "python", "S");
        assert_eq!(reach.kind, UNDECIDED);
        assert_eq!(reach.silence, partition::UNMODELED_CONSTRUCT);
    }

    #[test]
    fn a_bounded_builtin_lets_the_result_flow_on() {
        // `len(S)` is bounded however wide S is, so what matters is where the length goes.
        let reach = reach_of("S = {}\n\ndef f():\n    if len(S) > 3:\n        pass\n",
                             "python", "S");
        assert_eq!(reach.kind, FINITE);
        assert!(reach.ordered);
    }

    #[test]
    fn an_effect_call_consumes_the_value_without_deciding_anything() {
        let reach = reach_of("S = {}\n\ndef f():\n    print(S)\n", "python", "S");
        assert_eq!(reach.kind, partition::OUTPUT);
    }

    #[test]
    fn a_call_we_cannot_read_names_whose_problem_the_silence_is() {
        // A bare name is inside our reach: a builtin we have not listed, or a function in
        // the repository. Either way the fix is ours, and it must not report under the
        // adopter's boundary.
        let reach = reach_of("S = {}\n\ndef f():\n    return helper(S)\n", "python", "S");
        assert_eq!(reach.kind, UNDECIDED);
        assert_eq!(reach.silence, partition::UNMODELED_CALLEE);
    }

    #[test]
    fn a_call_through_another_object_is_a_boundary_only_the_adopter_can_open() {
        let reach = reach_of("S = {}\n\ndef f():\n    return workbook.save(S)\n", "python", "S");
        assert_eq!(reach.kind, UNDECIDED);
        assert_eq!(reach.silence, partition::EXTERNAL_BOUNDARY);
    }
}
