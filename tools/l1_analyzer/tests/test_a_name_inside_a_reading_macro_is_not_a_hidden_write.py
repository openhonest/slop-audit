"""A state named inside a macro that only READS its arguments is not an unread state.

Rust hands a macro's arguments back as a flat token tree, so a reference inside one is never
built and no walk can reach it. The reader answers that honestly: any state whose field name
appears inside any such region is forced to unresolved, because a write could be hiding
there and a verdict from the references that WERE built would report a partial reading as a
clean one.

The protection is against an unseen WRITE, and `format!`, `println!`, `assert_eq!`,
`matches!`, `vec!` and the tracing macros cannot write what they are given. So the region is
opaque and the danger is not there, and forcing the state unresolved reports a reading that
was complete as one that was not.

It is 72 of the 102 remaining silences on crates/buzz-acp in github.com/block/buzz, measured
on 2026-08-31, and the macros in that crate are the ordinary ones: assert, assert_eq, vec,
format, json, matches, panic and four tracing levels, 3600 uses between them.

Named macros, never a general rule. A macro can expand to anything, so this is a list of the
ones whose contract is known, and `write!` is deliberately absent: it writes its first
argument.
"""

from pathlib import Path

from l1_analyzer import state_bounds

_READS = '''pub struct S {
    items: Vec<u32>,
    label: String,
    kind: u8,
}

impl S {
    pub fn log(&self) {
        tracing::info!("items={} label={}", self.items.len(), self.label);
    }

    pub fn describe(&self) -> String {
        format!("{}", self.kind)
    }

    pub fn check(&self) {
        assert_eq!(self.kind, 3);
    }

    pub fn plain(&self) -> usize {
        let l = self.label.len();
        self.items.len() + l
    }

    pub fn hot(&self) -> bool {
        self.kind > 3
    }
}
'''

_WRITES = '''use std::fmt::Write;

pub struct S {
    sink: String,
}

impl S {
    pub fn emit(&mut self) {
        write!(self.sink, "x").unwrap();
    }

    pub fn size(&self) -> usize {
        self.sink.len()
    }
}
'''


def _reading(tmp_path: Path, source: str) -> dict:
    (tmp_path / "lib.rs").write_text(source)
    return {f["state"]: f for f in state_bounds.classify(tmp_path, "rust")["findings"]}


def test_a_state_only_formatted_and_logged_is_read(tmp_path):
    found = _reading(tmp_path, _READS)
    silent = {k: v["silence"] for k, v in found.items() if v["silence"]}
    assert silent == {}, silent


def test_a_state_a_macro_can_write_stays_unread(tmp_path):
    """`write!` takes its destination first and writes it. The whole point of the override
    is an unseen write, so the one macro that performs one keeps it."""
    assert _reading(tmp_path, _WRITES)["self.sink"]["silence"] == "unparsed_region"


def test_the_verdict_under_a_reading_macro_is_the_one_the_visible_references_earned(tmp_path):
    """Not cleared to neutral by fiat: the references outside the macro are read as they
    always were, and the macro simply stops overriding them."""
    found = _reading(tmp_path, _READS)
    assert found["self.kind"]["verdict"] == "neutral"
    assert found["self.items"]["verdict"] == "neutral"
