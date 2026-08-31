"""A chain of method calls on a piece of state is read, not reported as unmodelled.

`a.b()` was handled and `a.b().c()` was not. The reader walks from a field access to the
call it supplies, and had no row for the other half of every chain: a call RESULT reached
through another field access. So the second link fell to the total row and came back
"consumed by a piece of syntax the reader has no rule for".

It cost a real audit. A production run over a public Rust crate on 2026-08-30 published 88%
of read state finitely testable while reporting, in its own note, that 290 of 392
state-keeping places were constructs the reader had not learned. `self.sessions.entry(k)
.or_default().push(v)` is the shape, and it is the ordinary way to write into a Rust map.

Two halves to the repair, and the second is why the first is not enough on its own.
`entry` was missing from the language's keyed-read vocabulary, so even one link deep the
reader did not know that `entry(k)` asks about one cell. And a chain that resolves at a
keyed access stops there, which is why teaching the vocabulary settles the whole chain
rather than only its first link.
"""

from pathlib import Path

from l1_analyzer import state_bounds

_CHAINED = '''use std::collections::{HashMap, HashSet};

pub struct Relay {
    previous: HashSet<String>,
    sessions: HashMap<String, Vec<u64>>,
    counted: HashMap<String, u64>,
}

impl Relay {
    pub fn seen(&mut self, id: String) -> bool {
        if self.previous.contains(&id) {
            return true;
        }
        self.previous.insert(id);
        false
    }

    pub fn record(&mut self, key: String, n: u64) {
        self.sessions.entry(key).or_default().push(n);
    }

    pub fn tally(&mut self, key: String) {
        *self.counted.entry(key).or_insert(0) += 1;
    }
}
'''


def _findings(tmp_path: Path) -> dict:
    (tmp_path / "lib.rs").write_text(_CHAINED)
    reading = state_bounds.classify(tmp_path, "rust")
    return {f["state"]: f for f in reading["findings"]}


def test_no_state_in_a_method_chain_is_left_unmodelled(tmp_path):
    silent = {name: f["construct"] for name, f in _findings(tmp_path).items() if f["silence"]}
    assert silent == {}, silent


def test_a_map_written_through_an_unbounded_key_is_still_unbounded(tmp_path):
    """The half that matters. Reading the chain must not turn a silence into a clean: the
    key is a parameter, so the map grows without bound and the verdict is the same one the
    direct `insert` on the set beside it already earned."""
    found = _findings(tmp_path)
    assert found["self.sessions"]["verdict"] == found["self.previous"]["verdict"]
    assert found["self.sessions"]["verdict"] == "promiscuous"


def test_a_counter_keyed_the_same_way_reads_the_same(tmp_path):
    """`*self.counted.entry(k).or_insert(0) += 1` is the other Rust map idiom, and it
    reaches the key through a dereference the first one does not have."""
    assert _findings(tmp_path)["self.counted"]["silence"] == ""


def test_the_chain_does_not_clear_state_the_reader_should_still_flag(tmp_path):
    """The direct forms this repair must leave exactly as they were."""
    found = _findings(tmp_path)
    assert found["self.previous"]["verdict"] == "promiscuous"
    assert found["self.previous"]["silence"] == ""
