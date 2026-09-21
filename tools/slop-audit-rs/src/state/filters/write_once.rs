//! Rule: assigned once, and never reachable for mutation afterwards. Ported from the
//! write-once half of l1_analyzer.state_bounds_filters.
//!
//! Over-approximating writes is the safe direction throughout. A builder writes the
//! attribute through ANOTHER instance (`new._q = self._q.f()`), so a scan that looks only
//! at `self` is blind to it, and a local that happens to share the name counts as a write
//! and the rule declines to clear.

use crate::lang_spec::LangSpec;
use crate::nodes::{
    children, descendants, field, mutable_alias_value, same, sub_collection, text,
    written_in_place,
};
use tree_sitter::Node;

/// Every `<recv>.attr` node an assignment target binds, unwrapping tuple and list patterns.
///
/// A plain target yields itself; a pattern yields one node per element. A LANGUAGE THAT
/// NAMES ITS STATE WITHOUT A RECEIVER writes it as the target itself: Ruby hangs an instance
/// variable there and Java a bare identifier, and neither is a member access, so a walk
/// looking only for `<recv>.attr` found no writes at all and every such attribute read as
/// written zero times, which is not once.
fn attribute_targets<'t>(left: Option<Node<'t>>, sp: &LangSpec) -> Vec<Node<'t>> {
    let Some(left) = left else { return Vec::new() };
    if sp.member_types.contains(&left.kind()) {
        return vec![left];
    }
    let targets: Vec<Node<'t>> = children(left)
        .into_iter()
        .filter(|n| sp.member_types.contains(&n.kind()))
        .collect();
    if targets.is_empty() { vec![left] } else { targets }
}

/// Every assignment target `<recv>.attr` inside the class, through ANY receiver.
pub fn member_writes<'t>(cls: Node<'t>, attr: &str, sp: &LangSpec, src: &[u8]) -> Vec<Node<'t>> {
    let mut writes = Vec::new();
    for n in descendants(cls) {
        if !sp.assign_types.contains(&n.kind()) {
            continue;
        }
        // Every attribute IN the target, not the target itself. `self.a, self.b = m, m`
        // puts a pattern there, and reading only the target's own type counted neither
        // write, so an attribute written twice could still read as write-once.
        for t in attribute_targets(field(Some(n), sp.assign_left), sp) {
            if text(field(Some(t), sp.mem_attr), src) == attr || text(Some(t), src) == attr {
                writes.push(t);
            }
        }
    }
    writes
}

/// Any `self.attr.<method>(...)` with an in-place method, `self.attr[k] = v`, `del
/// self.attr[k]`, or a write where the reference stands: a mutation route beyond the single
/// assignment.
pub fn mutated_in_place(refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    for &reference in refs {
        let Some(parent) = reference.parent() else { continue };
        // self.attr[...] as an assignment or removal target.
        if sp.subscript_types.contains(&parent.kind())
            && same(sub_collection(parent, sp), Some(reference)) {
            if let Some(gp) = parent.parent() {
                let stored = sp.assign_types.contains(&gp.kind())
                    && same(field(Some(gp), sp.assign_left), Some(parent));
                if stored || sp.key_removal_types.contains(&gp.kind()) {
                    return true;
                }
            }
        }
        // self.attr.method(...) with an in-place method.
        if sp.member_types.contains(&parent.kind())
            && same(field(Some(parent), sp.mem_object), Some(reference)) {
            let called = parent.parent().is_some_and(|gp| sp.call_types.contains(&gp.kind())
                && same(field(Some(gp), sp.call_fn), Some(parent)));
            let method = text(field(Some(parent), sp.mem_attr), src);
            if called && sp.mutates_in_place.contains(&method.as_str()) {
                return true;
            }
        }
        // The flat-call spelling of the same mutation. Java and Ruby hang the receiver, the
        // method and the arguments off ONE node, so the branch above walks a member access
        // those two never build.
        if sp.flat_call && sp.call_types.contains(&parent.kind())
            && same(field(Some(parent), sp.call_recv), Some(reference)) {
            if let Some(name_field) = sp.call_name {
                let name = text(field(Some(parent), name_field), src);
                if sp.mutates_in_place.contains(&name.as_str()) {
                    return true;
                }
            }
        }
        // WRITTEN WHERE IT STANDS: `n++`, `@xs << x`. One runtime step spelled several ways
        // and not one of them an assignment node, so nothing above reaches any of them.
        if same(written_in_place(Some(parent), sp), Some(reference)) {
            return true;
        }
        // An assignment straight to the attribute that WRITES IN PLACE: `self.n += 1`.
        // Written as "an operator is there", not as "the operator is not `=`": an absent
        // operator read as a mutation, which is what a plain assignment has, so every
        // write-once attribute in the language came back mutated and the rule cleared
        // nothing at all.
        if sp.assign_types.contains(&parent.kind())
            && same(field(Some(parent), sp.assign_left), Some(reference))
            && field(Some(parent), "operator").is_some() {
            return true;
        }
    }
    false
}

/// `return self.attr` hands the object itself out and a caller can then mutate it.
/// Returning a slice or a copy is fine.
pub fn returned_whole(refs: &[Node], sp: &LangSpec) -> bool {
    refs.iter().any(|r| r.parent().is_some_and(|p| sp.return_types.contains(&p.kind())))
}

/// The argument list this reference is an argument of, through any wrapper, or nothing.
///
/// Answers the node rather than a bool so the caller can still reach the callee, and
/// nothing rather than raising because a reference that is not an argument is the ordinary
/// case.
fn argument_list_above<'t>(parent: Node<'t>, sp: &LangSpec) -> Option<Node<'t>> {
    if sp.arglist_types.contains(&parent.kind()) {
        return Some(parent);
    }
    if sp.argument_wrapper_types.contains(&parent.kind()) {
        let gp = parent.parent()?;
        return if sp.arglist_types.contains(&gp.kind()) { Some(gp) } else { None };
    }
    None
}

/// The attribute is invoked as a callable, handed out as a mutable alias, or passed as an
/// argument to a callee that is not a known read-only builtin. Each lets an unbounded or
/// unmodelled context act on it, so the value does not provably stay bounded.
pub fn escapes(refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    for &reference in refs {
        let Some(parent) = reference.parent() else { continue };
        // self.attr(...) : dynamic dispatch.
        if sp.call_types.contains(&parent.kind())
            && same(field(Some(parent), sp.call_fn), Some(reference)) {
            return true;
        }
        // The flat-call spelling of the same dispatch, and it is NOT every call on the
        // value. Java and Ruby hang receiver, method and arguments off one node, so
        // `@rows.size` and a stored callable being invoked look alike there; what tells them
        // apart is the method NAME, which the language declares. Reading any receiver
        // position as dispatch made every ordinary method call on a field an escape.
        if sp.flat_call && sp.call_types.contains(&parent.kind())
            && same(field(Some(parent), sp.call_recv), Some(reference)) {
            if let Some(name_field) = sp.call_name {
                let name = text(field(Some(parent), name_field), src);
                if sp.dispatch_methods.contains(&name.as_str()) {
                    return true;
                }
            }
        }
        // HANDED OUT AS A MUTABLE ALIAS. `let r = &mut self.v; r.push(1)` writes the field
        // through a local whose name has no relation to it, so from that line on there is a
        // write this rule's own references do not contain. A SHARED borrow is not this:
        // `&self.v` cannot be written through, and only the mutability marker separates the
        // two.
        if same(mutable_alias_value(Some(parent), sp), Some(reference)) {
            return true;
        }
        if let Some(arglist) = argument_list_above(parent, sp) {
            let callee = arglist.parent().and_then(|call| field(Some(call), sp.call_fn));
            if !sp.safe_arg_calls.contains(&text(callee, src).as_str()) {
                return true;                       // passed to an unknown callee
            }
        }
    }
    false
}

/// Assigned exactly once and never reachable for mutation afterwards.
pub fn is_write_once(cls: Node, attr: &str, refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    if member_writes(cls, attr, sp, src).len() != 1 {
        return false;
    }
    !mutated_in_place(refs, sp, src) && !returned_whole(refs, sp) && !escapes(refs, sp, src)
}
