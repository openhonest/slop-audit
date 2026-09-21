//! What the generated language table must hold, asserted by hand.
//!
//! `src/lang_spec.rs` is generated and must stay generated: appending anything to it makes
//! `generate_lang_spec.py --check` read it as stale, which is the check working. So the
//! assertions about it live here, in a file a person writes.
//!
//! These are not a substitute for `--check`, which compares the whole table against the
//! reference. They catch a different failure: a generator that writes the right SHAPE with
//! the wrong contents would pass a compile and pass a round-trip against itself.

#[cfg(test)]
mod tests {
    use crate::lang_spec::{lookup, spec_for, LANG_SPECS};

    /// Nine rows, one per language the reference declares. A tenth added there and not
    /// regenerated here would make the crate read a grammar it has no vocabulary for.
    #[test]
    fn every_language_the_reference_declares_has_a_row() {
        let keys: Vec<&str> = LANG_SPECS.iter().map(|r| r.key).collect();
        assert_eq!(keys.len(), 9, "{keys:?}");
        for lang in ["c", "csharp", "go", "java", "javascript", "python", "ruby", "rust",
                     "typescript"] {
            assert!(spec_for(lang).is_some(), "no row for {lang}");
        }
    }

    /// A language with no row is refused, never defaulted. An empty vocabulary recognises
    /// no construct, so it would report a repository the reader never understood as one
    /// holding no state.
    #[test]
    fn a_language_with_no_row_is_refused_rather_than_emptied() {
        assert!(spec_for("cobol").is_none());
    }

    /// Spot checks against values a reader can verify by opening the reference.
    #[test]
    fn the_generated_values_are_the_reference_values() {
        let python = spec_for("python").expect("python");
        assert!(python.this_idents.contains(&"self"));
        assert_eq!(python.assign_left, "left");
        assert_eq!(python.call_fn, "function");

        let rust = spec_for("rust").expect("rust");
        assert!(rust.this_idents.contains(&"self"));
        // Rust is the one language that spells a mutable alias, and the marker is what
        // tells `&mut self.v` from `&self.v`. The other eight declare neither.
        assert_eq!(rust.alias_marker, "mutable_specifier");
        assert!(!rust.alias_types.is_empty());

        let go = spec_for("go").expect("go");
        // Go's state spans methods rather than a class body, grouped by receiver type.
        assert!(go.scope_by_receiver);
        assert!(!python.scope_by_receiver);
    }

    /// Go's `for` takes its condition as a bare first named child with no field, so a
    /// reader keying on the field name reads nothing there: `for p.running {}` was a loop
    /// on a bool field that no row could see. Every other grammar names the field.
    #[test]
    fn the_one_grammar_that_hides_its_loop_condition_declares_it() {
        let go = spec_for("go").expect("go");
        assert!(!go.bare_cond_types.is_empty(), "go must declare its bare condition");
        for lang in ["python", "rust", "java", "csharp"] {
            let row = spec_for(lang).expect(lang);
            assert!(row.bare_cond_types.is_empty(), "{lang} names its condition field");
        }
    }

    /// A lookup answers absent for a node type nobody assigned a rule, so the caller
    /// decides what that means rather than inheriting somebody's zero.
    #[test]
    fn a_lookup_refuses_a_node_type_the_table_does_not_carry() {
        let python = spec_for("python").expect("python");
        assert!(lookup(python.cond_at_index, "no_such_node").is_none());
    }
}
