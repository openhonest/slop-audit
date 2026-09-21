//! Rule: a presence-gated, result-invariant memoization cache. Ported from the memoization
//! half of l1_analyzer.state_bounds_filters.
//!
//! This is the one shape allowed past the open-key guard, and the argument is narrow: a
//! cache that answers the same for a key whether or not that key is stored can be DELETED
//! without changing an observable answer, so the partition its keyed read cuts belongs to
//! the function being memoised and not to the cache. No other rule can make that argument,
//! which is why no other rule is exempt.

use crate::lang_spec::LangSpec;
use crate::nodes::{children, field, first_named, named_descendants, same, sub_collection, text};
use crate::state::filters::{enclosing, has_presence_gate};
use crate::state::filters::write_once::member_writes;
use crate::state::ref_reads as reads;
use tree_sitter::Node;

/// Writes are only `d[k] = v`, `del d[k]`, an empty-map rebind, or cache methods.
///
/// A compound assignment through the attribute (`self.attr[k] += 1`) fails: that inspects
/// and rewrites the value, which is what a counter does and not what a cache does. Told
/// from a plain store by whether the grammar hung an operator on the assignment, which
/// every one of the nine does.
pub fn writes_are_plain_stores(cls: Node, attr: &str, refs: &[Node], sp: &LangSpec,
                               src: &[u8]) -> bool {
    for &reference in refs {
        let Some(parent) = reference.parent() else { continue };
        if sp.subscript_types.contains(&parent.kind())
            && same(sub_collection(parent, sp), Some(reference)) {
            if let Some(gp) = parent.parent() {
                if sp.assign_types.contains(&gp.kind())
                    && field(Some(gp), "operator").is_some() {
                    return false;
                }
            }
        }
        if sp.member_types.contains(&parent.kind())
            && same(field(Some(parent), sp.mem_object), Some(reference)) {
            let called = parent.parent().is_some_and(|gp| sp.call_types.contains(&gp.kind())
                && same(field(Some(gp), sp.call_fn), Some(parent)));
            let method = text(field(Some(parent), sp.mem_attr), src);
            if called && sp.mutates_in_place.contains(&method.as_str())
                && !sp.cache_reads.contains(&method.as_str()) {
                return false;
            }
        }
        // The flat-call spelling of the same mutation, for the two languages that hang the
        // receiver, the method and the arguments off one node.
        if sp.flat_call && sp.call_types.contains(&parent.kind())
            && same(field(Some(parent), sp.call_recv), Some(reference)) {
            let name = match sp.call_name {
                Some(name_field) => text(field(Some(parent), name_field), src),
                None => String::new(),
            };
            if sp.mutates_in_place.contains(&name.as_str())
                && !sp.cache_reads.contains(&name.as_str()) {
                return false;
            }
        }
    }
    // A whole-attribute rebind must be to an EMPTY map. Rebinding it to anything else puts
    // values in the cache that no write in the class accounts for, so the shape is no longer
    // one this rule can argue about. A language that declares no empty-map literal cannot
    // satisfy this and the rule declines, which is the safe direction.
    for w in member_writes(cls, attr, sp, src) {
        let rhs = w.parent().and_then(|assign| field(Some(assign), sp.assign_right));
        if let Some(rhs) = rhs {
            let empty = sp.empty_map_types.contains(&rhs.kind())
                && !children(rhs).into_iter().any(|c| c.is_named());
            if !empty {
                return false;
            }
        }
    }
    true
}

/// Whether the presence of a key changes the answer, or nothing when no method gates on
/// presence at all.
///
/// Scoped to the ACCESSOR methods, those holding a presence test on the attribute: every
/// return is the keyed value or a bare return. A method that returns a different value by
/// presence is result-VARIANT, the presence IS the answer, and it stays flagged. A setter
/// elsewhere that returns the stored value is irrelevant.
///
/// NOTHING WHEN THERE IS NOTHING TO EXAMINE. The reference answered True when no method
/// contained a presence test, which is a claim about a question that was never put: the
/// loop body never ran and the function fell through to a bare `return True`. Two rules
/// downstream read that vacuous affirmative as evidence. The caller compares against False,
/// so the behaviour is the same and the answer now says which of the two it is.
pub fn result_invariant(attr: &str, refs: &[Node], sp: &LangSpec, src: &[u8]) -> Option<bool> {
    let mut gated: Vec<Node> = Vec::new();
    for &reference in refs {
        if !reads::is_presence_test(reference, sp, src) {
            continue;
        }
        if let Some(func) = enclosing(reference, sp.func_types) {
            if !gated.iter().any(|seen| seen.id() == func.id()) {
                gated.push(func);
            }
        }
    }
    if gated.is_empty() {
        return None;                 // no presence test to examine: the question does not apply
    }
    for func in gated {
        for ret in named_descendants(func).into_iter()
            .filter(|n| sp.return_types.contains(&n.kind())) {
            if let Some(val) = first_named(Some(ret)) {
                if !reads::is_keyed_read_of(Some(val), attr, sp, src) {
                    return Some(false);
                }
            }
        }
    }
    Some(true)
}

/// Whether anything WRITES into this container: `d[k] = v`, or a whole rebind.
///
/// A cache nobody writes is not a cache. The shape check above asks whether every write is
/// a plain store, and over zero writes that is vacuously true, so a container only ever
/// READ satisfied it. Rust's `if self.by_id.contains_key(&k)` with a variable key is that
/// shape exactly: a presence test on an unbounded key, no store anywhere, and the answer
/// depends on the key, which is the finding the rule then cleared.
pub fn stores_into(refs: &[Node], sp: &LangSpec) -> bool {
    for &reference in refs {
        let Some(parent) = reference.parent() else { continue };
        if sp.subscript_types.contains(&parent.kind())
            && same(sub_collection(parent, sp), Some(reference)) {
            if let Some(gp) = parent.parent() {
                if sp.assign_types.contains(&gp.kind())
                    && same(field(Some(gp), sp.assign_left), Some(parent)) {
                    return true;
                }
            }
        }
        if sp.assign_types.contains(&parent.kind())
            && same(field(Some(parent), sp.assign_left), Some(reference)) {
            return true;
        }
    }
    false
}

/// A presence-gated cache that something writes, and whose every write is a plain store.
pub fn is_memoization(cls: Node, attr: &str, refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    has_presence_gate(refs, sp, src)
        && stores_into(refs, sp)
        && writes_are_plain_stores(cls, attr, refs, sp, src)
}
