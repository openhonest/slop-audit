//! Rule: a write-only accumulator. Ported from the accumulator half of
//! l1_analyzer.state_bounds_filters.
//!
//! A per-key counter or tally: `if k not in self._h: self._h[k] = 0` followed by
//! `self._h[k] += 1`. It is not a memoization cache, because the augmented assignment
//! inspects and rewrites the stored value, which is exactly why the plain-stores check
//! rejects it, and that rejection is correct. But nothing ever reads the count back out. The
//! presence test gates a branch whose arms both fall through to the same augmented
//! assignment, so no test can tell the arms apart and none needs to. State that cannot
//! change an observable outcome cannot make anything harder to test.
//!
//! The rule has two halves and needs both. The first is that no reference reads the stored
//! value into a condition, which the module guard already establishes. The second is that no
//! reference hands the value out. Dropping the second half would clear a counter whose count
//! is returned and then branched on by the CALLER, which is the compositional hole the
//! classifier guards everywhere else: the decision moves one frame up and the finding
//! evaporates.
//!
//! Both halves are enforced by whitelisting the positions a reference may occupy. Every role
//! below is a WRITE or a presence test; none yields the stored value to anything. A
//! reference anywhere else, returned, passed as an argument, iterated, read by key into an
//! expression, invoked, is not on the list, and the rule declines.
//!
//! The read-modify-write is where the nine grammars diverge furthest and mean the same
//! thing. Python, C#, Ruby, Go, JavaScript and TypeScript write it as one compound
//! assignment. Java has to spell it `h.put(k, h.get(k) + 1)` and Rust
//! `*h.get_mut(&k).unwrap() += 1`, so in those two the read is a node of its own and the
//! rule has to follow the value it produces to the write on the other side. Same runtime
//! step, three notations.

use crate::lang_spec::{lookup, LangSpec};
use crate::nodes::{children, field, first_named, is_lvalue, same, sub_collection, text};
use crate::state::cells::MEMBERSHIP_TOKENS;
use crate::state::reach::COMPARISON_OPS;
use crate::state::ref_reads as reads;
use tree_sitter::Node;

/// The positions a reference may occupy, keyed by the PARENT node type it sits under.
///
/// A parent type with no role is a position the rule has no argument for, and the rule
/// declines rather than guessing.
enum Role {
    /// `self.attr = {}`: the attribute itself is the assignment target.
    WholeRebind,
    /// `Map<String,Integer> hits = new HashMap<>();`: the reference is the DECLARED NAME of
    /// the field. A declaration binds the state, it does not consume it.
    BindingDeclaration,
    /// `k in self.attr`: the container of a membership test, which reads no stored value.
    PresenceGate,
    /// `self.attr[k]` standing as a store target.
    ConfinedSubscript,
    /// A pure write, a presence test, or a keyed read written straight back.
    ConfinedMethodUse,
}

/// The role for one parent node type, under this language's own vocabulary.
///
/// The reference builds a dictionary and lets later entries overwrite earlier ones, so the
/// checks below run in the REVERSE of its insertion order: a type in two tables takes the
/// role the later table gives it. A grammar where a subscript type is also an assignment
/// type would otherwise be read as a whole rebind, which admits a position the rule has no
/// argument for.
fn confined_role(parent_type: &str, sp: &LangSpec) -> Option<Role> {
    if sp.flat_call && sp.call_types.contains(&parent_type) {
        return Some(Role::ConfinedMethodUse);
    }
    if sp.member_types.contains(&parent_type) {
        return Some(Role::ConfinedMethodUse);
    }
    if sp.subscript_types.contains(&parent_type) {
        return Some(Role::ConfinedSubscript);
    }
    if sp.comparison_types.contains(&parent_type) {
        return Some(Role::PresenceGate);
    }
    if lookup(sp.binding_sites, parent_type).is_some() {
        return Some(Role::BindingDeclaration);
    }
    if !sp.lvalue_wrapper.is_empty() && sp.lvalue_wrapper == parent_type {
        return Some(Role::WholeRebind);
    }
    if sp.assign_types.contains(&parent_type) {
        return Some(Role::WholeRebind);
    }
    None
}

/// The reference is the declared NAME of a field, not a use of it. The field is checked and
/// not just the node type: `int y = hits.size();` puts `hits` under a declarator too, in the
/// value.
fn is_binding_declaration(reference: Node, parent: Node, sp: &LangSpec) -> bool {
    match lookup(sp.binding_sites, parent.kind()) {
        Some(name_field) => same(field(Some(parent), name_field), Some(reference)),
        None => false,
    }
}

/// `self.attr[k]` standing as a store target: `= v`, `+= 1`, or a removal. A keyed read in
/// any other position carries the value somewhere this rule cannot follow, except Go's
/// comma-ok presence test, where the value half goes to the blank identifier and only the
/// presence flag is kept.
fn is_confined_subscript(reference: Node, parent: Node, sp: &LangSpec, src: &[u8]) -> bool {
    if !same(sub_collection(parent, sp), Some(reference)) {
        return false;
    }
    if is_lvalue(Some(parent), sp) {
        // A CONDITIONAL ASSIGNMENT IS NOT A PLAIN STORE. `@cache[k] ||= compute(k)`
        // evaluates to the stored value, so the value leaves through the expression itself,
        // and in Ruby a method's tail expression is its return. That is the compositional
        // hole this rule guards everywhere else. It is admitted only where the language can
        // PROVE the value is thrown away, and Ruby declares no discard form, so in Ruby it
        // never can and the rule declines.
        let op = text(field(parent.parent(), "operator"), src);
        if sp.read_write_assign_ops.contains(&op.as_str()) {
            return reads::result_discarded(parent.parent(), sp);
        }
        return true;
    }
    if reads::is_deleted(parent, sp) {
        return true;
    }
    reads::is_comma_ok_presence(reference, sp, src)
}

/// `self.attr.add(k)`: an in-place method that returns no stored value, whose result nobody
/// reads. Two conditions, and both are needed: the name has to be one that writes, and where
/// the write also hands back what was there before (Java's put, Rust's insert) the result
/// has to be discarded.
fn is_pure_write_call(reference: Node, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(call) = reads::receiver_call(reference, sp) else { return false };
    if !sp.write_methods.contains(&reads::method_name(call, sp, src).as_str()) {
        return false;
    }
    reads::result_discarded(Some(call), sp)
}

/// A binary node carrying an operator that is neither a comparison nor a membership test:
/// `h.get(k) + 1`. The value it produces is derived, not decided on.
///
/// Python is excluded by construction rather than by a special case: its comparison node
/// carries no operator field, so the text is empty and no arithmetic reading is available.
/// Python spells arithmetic with a different node type entirely, and one this rule has no
/// need for.
fn is_arithmetic_host(parent: Node, src: &[u8]) -> bool {
    let Some(op) = field(Some(parent), "operator") else { return false };
    let spelling = text(Some(op), src);
    !COMPARISON_OPS.contains(&spelling.as_str())
        && !MEMBERSHIP_TOKENS.contains(&spelling.as_str())
}

/// The node the value moves to when its host neither consumes nor decides on it, or nothing
/// when the host is neither. Three shapes: a declared passthrough wrapper (Rust's deref, a
/// parenthesis), arithmetic, and a method that hands back the value it was given (Rust's
/// `unwrap`, without which `get_mut(&k).unwrap()` cannot reach its assignment).
fn transparent_host<'t>(cur: Node<'t>, parent: Node<'t>, sp: &LangSpec,
                        src: &[u8]) -> Option<Node<'t>> {
    if sp.passthrough_types.contains(&parent.kind()) {
        return Some(parent);
    }
    if sp.comparison_types.contains(&parent.kind()) && is_arithmetic_host(parent, src) {
        return Some(parent);
    }
    let call = reads::receiver_call(cur, sp)?;
    if sp.value_preserving_methods.contains(&reads::method_name(call, sp, src).as_str()) {
        return Some(call);
    }
    None
}

/// `h.put(k, ...)`: a pure write whose receiver is the attribute itself.
fn is_attribute_write_call(call: Option<Node>, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(recv) = reads::call_receiver(call, sp) else { return false };
    reads::names_the_attribute(Some(recv), attr, sp, src) && is_pure_write_call(recv, sp, src)
}

/// The value this read produced is written straight back into the attribute and reaches
/// nothing else.
///
/// Two endings: it is the target of an assignment (Rust's `*h.get_mut(&k).unwrap() += 1`), or
/// it is an argument of a write on the same attribute (Java's `h.put(k, h.get(k) + 1)`).
/// Anything else on the way up and the walk declines, which is the conservative direction: a
/// value that escapes keeps the finding.
fn flows_back_into_the_attribute(read: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let mut cur = read;
    loop {
        let Some(parent) = cur.parent() else { return false };
        if sp.func_types.contains(&parent.kind()) {
            return false;
        }
        if sp.assign_types.contains(&parent.kind()) {
            return is_lvalue(Some(cur), sp);
        }
        if sp.arglist_types.contains(&parent.kind()) {
            return is_attribute_write_call(parent.parent(), attr, sp, src);
        }
        match transparent_host(cur, parent, sp, src) {
            Some(next) => cur = next,
            None => return false,
        }
    }
}

/// A read-modify-write spelled with an explicit read. `h.get(k)` in Java and `h.get_mut(&k)`
/// in Rust are the same runtime step Python writes as `h[k] += 1`: the value comes out and
/// goes straight back in, so nothing observes it.
fn is_keyed_read_written_back(reference: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(call) = reads::receiver_call(reference, sp) else { return false };
    let name = reads::method_name(call, sp, src);
    if !sp.keyed_read.contains(&name.as_str()) || sp.presence_methods.contains(&name.as_str()) {
        return false;
    }
    flows_back_into_the_attribute(call, attr, sp, src)
}

/// Every method position the rule admits: a pure write, a presence test, or a keyed read
/// written straight back. One predicate serves the flat-call grammars and the nested ones,
/// because `receiver_call` already reconciles the two shapes.
fn is_confined_method_use(reference: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    is_pure_write_call(reference, sp, src)
        || reads::is_presence_method_call(reference, sp, src)
        || is_keyed_read_written_back(reference, attr, sp, src)
}

/// The reference occupies a position the rule has an argument for.
fn is_confined_reference(reference: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(parent) = reference.parent() else { return false };
    match confined_role(parent.kind(), sp) {
        None => false,
        Some(Role::WholeRebind) => is_lvalue(Some(reference), sp),
        Some(Role::BindingDeclaration) => is_binding_declaration(reference, parent, sp),
        Some(Role::PresenceGate) => reads::is_membership_container(reference, sp),
        Some(Role::ConfinedSubscript) => is_confined_subscript(reference, parent, sp, src),
        Some(Role::ConfinedMethodUse) => is_confined_method_use(reference, attr, sp, src),
    }
}

/// `self.attr` or `self.attr[k]`, as the left-hand side of a write.
fn is_attr_write_target(node: Option<Node>, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    reads::is_keyed_read_of(node, attr, sp, src)
        || reads::names_the_attribute(node, attr, sp, src)
}

/// Which statements a gate's arm may hold.
///
/// Only Python declares a delete statement; everywhere else a key removal is a call that
/// hands the removed value back, or a unary operator that collides with a wrapper already
/// declared transparent, and the rule declines the shape rather than reading one as the
/// other.
///
/// Checked in the reverse of the reference's insertion order, for the reason `confined_role`
/// gives.
enum StatementRule {
    Assignment,
    Delete,
    WriteCall,
}

fn statement_rule(node_type: &str, sp: &LangSpec) -> Option<StatementRule> {
    if sp.call_types.contains(&node_type) {
        return Some(StatementRule::WriteCall);
    }
    if sp.delete_stmt_types.contains(&node_type) {
        return Some(StatementRule::Delete);
    }
    if sp.assign_types.contains(&node_type) {
        return Some(StatementRule::Assignment);
    }
    None
}

fn stmt_is_attr_assignment(node: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let mut left = field(Some(node), sp.assign_left);
    let wrapper = sp.lvalue_wrapper;
    if let Some(l) = left {
        if !wrapper.is_empty() && l.kind() == wrapper {
            let named: Vec<Node> = children(l).into_iter().filter(|c| c.is_named()).collect();
            left = if named.len() == 1 { Some(named[0]) } else { None };
        }
    }
    is_attr_write_target(left, attr, sp, src)
}

fn stmt_is_attr_delete(node: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    children(node).into_iter().filter(|c| c.is_named())
        .all(|c| is_attr_write_target(Some(c), attr, sp, src))
}

fn stmt_is_attr_write_call(node: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(recv) = reads::call_receiver(Some(node), sp) else { return false };
    is_attr_write_target(Some(recv), attr, sp, src) && is_pure_write_call(recv, sp, src)
}

/// `stmt` writes `attr` and does nothing else the caller could observe.
fn writes_only_the_attribute(stmt: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let mut inner = stmt;
    if sp.discard_types.contains(&stmt.kind()) {
        if let Some(first) = first_named(Some(stmt)) {
            inner = first;
        }
    }
    match statement_rule(inner.kind(), sp) {
        None => false,
        Some(StatementRule::Assignment) => stmt_is_attr_assignment(inner, attr, sp, src),
        Some(StatementRule::Delete) => stmt_is_attr_delete(inner, attr, sp, src),
        Some(StatementRule::WriteCall) => stmt_is_attr_write_call(inner, attr, sp, src),
    }
}

/// The branch whose test this presence check is.
///
/// Nothing when the test sits somewhere with no arm to read, a ternary, an assert, a
/// comprehension guard, or in a position the walk leaves without finding one. Go's comma-ok
/// sits in the initialiser of its `if` rather than in the condition, which is why the gate
/// fields are a list and not one name.
fn gate_branch<'t>(reference: Node<'t>, sp: &LangSpec) -> Option<Node<'t>> {
    let mut cur = reference;
    while let Some(parent) = cur.parent() {
        if sp.func_types.contains(&parent.kind()) {
            return None;
        }
        let branch = sp.branch_types.contains(&parent.kind())
            || sp.elif_types.contains(&parent.kind());
        if branch && sp.gate_fields.iter()
            .any(|f| same(field(Some(parent), f), Some(cur))) {
            return Some(parent);
        }
        cur = parent;
    }
    None
}

/// Every statement the gate guards, with the gate's own test left out.
///
/// Body containers are declared per language and expanded, so Java's constructor body,
/// Ruby's `then` and `else`, Go's statement list and Python's else clause all yield their
/// statements instead of reading as one unrecognised node.
///
/// An explicit stack rather than a call to itself: a body container may hold another, and
/// how deep the nesting goes is the audited file's business. Two things the obvious loop
/// gets wrong, and both changed the answer. The gate's own test is recomputed for each
/// container rather than carried down from the outermost one, which is what the recursion
/// did. And a container's statements have to land where the container stood, not after its
/// siblings, so the work goes on the stack as expand-or-emit items and the items go on
/// reversed.
fn gate_guarded_statements<'t>(gate: Node<'t>, sp: &LangSpec) -> Vec<Node<'t>> {
    let mut out = Vec::new();
    let mut stack: Vec<(bool, Node<'t>)> = vec![(true, gate)];
    while let Some((expand, node)) = stack.pop() {
        if !expand {
            out.push(node);
            continue;
        }
        let tests: Vec<Option<Node<'t>>> =
            sp.gate_fields.iter().map(|f| field(Some(node), f)).collect();
        let mut pending: Vec<(bool, Node<'t>)> = Vec::new();
        for child in children(node).into_iter().filter(|c| c.is_named()) {
            if tests.iter().any(|t| same(*t, Some(child))) {
                continue;
            }
            pending.push((sp.gate_body_types.contains(&child.kind()), child));
        }
        pending.reverse();
        stack.extend(pending);
    }
    out
}

/// Every presence gate on the attribute guards arms that write only the attribute.
///
/// Without this, `if k in self._seen: self._misses += 1` would clear: the presence decides
/// something after all, just in a neighbouring slot rather than in a return value, and the
/// module guard's result-invariance check only looks at returns.
fn gated_branches_converge(attr: &str, refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    for &reference in refs {
        if !reads::is_presence_test(reference, sp, src) {
            continue;
        }
        let Some(gate) = gate_branch(reference, sp) else { return false };
        if !gate_guarded_statements(gate, sp).into_iter()
            .all(|s| writes_only_the_attribute(s, attr, sp, src)) {
            return false;
        }
    }
    true
}

/// Every reference is a write or a presence test, and every gate's arms converge.
pub fn is_write_only_accumulator(attr: &str, refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    refs.iter().all(|r| is_confined_reference(*r, attr, sp, src))
        && gated_branches_converge(attr, refs, sp, src)
}
