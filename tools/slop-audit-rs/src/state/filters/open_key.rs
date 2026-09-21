//! Guard: the container is read at a key the class does not bound, so the answer depends on
//! the key. Ported from the open-key half of l1_analyzer.state_bounds_filters.
//!
//! The rules beside this one all argue from where a reference SITS: assigned once, inside an
//! `if`, written by a plain store. None of them asks the question the classifier already
//! answered, which is what made the reference unbounded in the first place. A subscript by a
//! key the class does not bound IS the decision: the container answers one way per key and
//! the caller chooses the key, so the classes cannot be enumerated whether or not an `if`
//! follows the read. Reading the decision off the KEY rather than off the values is what let
//! `return self.cache[k]` clear in Python while C reported the same shape promiscuous.
//!
//! The guard is scoped to keys from OUTSIDE the class, and that scope is the whole of it. A
//! key that is itself state here, `self._rows[self._i]`, already carries its own finding,
//! bounded there by `self._i >= len(self._rows)`; charging the container for it as well
//! counts one decision twice. A key that arrives as a parameter is carried by no other
//! finding, so it lands here or nowhere.
//!
//! A store target is not a selection: `d[k] = v`, `d[k] += 1` and `del d[k]` put a value in
//! rather than take one out, and the accumulator rule argues separately about them.

use crate::lang_spec::LangSpec;
use crate::nodes::{field, first_arg, same, sub_collection, sub_key, text, unwrap_unary};
use tree_sitter::Node;

/// `self.x` / `cls.x`: state the enumerator reports separately, with its own verdict.
///
/// The receiver names come from the language, which declares its own. A language whose state
/// carries no receiver at all answers false here, which is right: its own enumerator finds
/// those by another route entirely.
fn is_state_of_this_class(node: Node, sp: &LangSpec, src: &[u8]) -> bool {
    sp.member_types.contains(&node.kind())
        && sp.this_idents.contains(&text(field(Some(node), sp.mem_object), src).as_str())
}

/// A single key the class does not bound.
///
/// A SLICE is not a key and never reaches this rule: `self._hash[:4]` selects a contiguous
/// run at a fixed width, and `self.alerts[-limit:]` selects a run at a caller's width, but
/// neither picks one stored value out of unboundedly many, which is the argument the guard
/// rests on.
///
/// The wrapper peeling goes through the SHARED reader, which knows that a borrow, a
/// parenthesis and a cast each leave a literal's identity alone. This rule kept its own
/// peeler over a narrower list, and the two disagreed about ordinary code in three
/// languages: `self.cache[(1)]` in Python and Java and `c.cache[&1]` in Rust were open keys
/// to one reader and bounded values to the other. An open key is what KEEPS a finding, so
/// the disagreement accused a container indexed by a constant.
pub fn is_open_key(key: Option<Node>, sp: &LangSpec, src: &[u8]) -> bool {
    if let Some(k) = key {
        if sp.slice_types.contains(&k.kind()) {
            return false;
        }
    }
    let Some(key) = unwrap_unary(key, sp) else { return false };
    if sp.literal_types.contains(&key.kind()) {
        return false;
    }
    !is_state_of_this_class(key, sp, src)
}

/// A reference SELECTS on a key nobody bounded, so the attribute's answer depends on it.
pub fn selects_on_an_open_key(refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    for &reference in refs {
        let Some(parent) = reference.parent() else { continue };
        if !sp.subscript_types.contains(&parent.kind())
            || !same(sub_collection(parent, sp), Some(reference)) {
            continue;
        }
        let gp = parent.parent();
        // A CONDITIONAL assignment is not a store. `@cache[k] ||= compute(k)` reads what is
        // at the key to decide whether to write there, so the answer depends on the key in
        // exactly the way this guard exists to catch. Counting it as a store was the last
        // thing keeping the carried-value rule Python-only: with it counted, that rule
        // cleared Ruby's commonest memoization shape with no premise checked at all.
        let conditional = sp.read_write_assign_ops
            .contains(&text(field(gp, "operator"), src).as_str());
        let store = match gp {
            None => false,
            Some(gp) => !conditional && ((sp.assign_types.contains(&gp.kind())
                && same(field(Some(gp), sp.assign_left), Some(parent)))
                || sp.key_removal_types.contains(&gp.kind())),
        };
        if !store && is_open_key(sub_key(parent, sp), sp, src) {
            return true;
        }
    }
    // THE METHOD FORM of a keyed read, which is how six of the nine spell it. Java asks
    // `d.get(k)` and C# `d.GetValueOrDefault(k)`, neither of which is a subscript, so a
    // guard reading only subscripts saw nothing and the carried-value rule cleared an
    // open-key read the cross-language vectors declare promiscuous.
    for &reference in refs {
        let Some(parent) = reference.parent() else { continue };
        if !sp.member_types.contains(&parent.kind()) {
            continue;
        }
        let called = parent.parent().is_some_and(|gp| sp.call_types.contains(&gp.kind())
            && same(field(Some(gp), sp.call_fn), Some(parent)));
        if !called {
            continue;
        }
        let Some(attr_node) = field(Some(parent), sp.mem_attr) else { continue };
        if sp.keyed_read.contains(&text(Some(attr_node), src).as_str())
            && is_open_key(first_arg(parent.parent(), sp), sp, src) {
            return true;
        }
    }
    // THE FLAT-CALL SPELLING of the same read. Java and Ruby hang the receiver, the method
    // name and the arguments off ONE node, so the loop above walks a member access those two
    // languages never build.
    if sp.flat_call {
        for &reference in refs {
            let Some(parent) = reference.parent() else { continue };
            if !sp.call_types.contains(&parent.kind())
                || !same(field(Some(parent), sp.call_recv), Some(reference)) {
                continue;
            }
            let Some(name_field) = sp.call_name else { continue };
            let Some(name) = field(Some(parent), name_field) else { continue };
            if sp.keyed_read.contains(&text(Some(name), src).as_str())
                && is_open_key(first_arg(Some(parent), sp), sp, src) {
                return true;
            }
        }
    }
    false
}
