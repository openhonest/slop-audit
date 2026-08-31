"""The shapes an ordinary Rust file is written in are read, not reported as unmodelled.

Measured, not guessed. On 2026-08-31 the reader was run over crates/buzz-acp in the public
github.com/block/buzz, and its own silence report ranked what it could not read. Four
constructs came back with no rule, and each is a plain way to write Rust:

    19  a call awaited                 `self.pool.acquire().await`
     8  a call bound in a condition    `if let Some(v) = self.map.get(k)`
     5  a call matched on              `match self.state.kind() { .. }`
     5  a call bound to a local        `let n = self.items.len();`
     4  a call in a struct literal     `Reply { body: self.buf.clone() }`

None needs a new idea. Awaiting a value hands back the value, which is what the passthrough
list already says about parentheses and a `?`. The other three are rows this reader has for
every other language and Rust's own node types were missing from the tables they read.

The five shapes are held here together because they were found together, in one report, on
one crate, and because the count beside each is the only reason to work them in this order.
"""

from pathlib import Path

from l1_analyzer import state_bounds

_ORDINARY = '''use std::collections::HashMap;

pub struct Pool {
    conns: Vec<u32>,
    names: HashMap<String, u32>,
    items: Vec<u32>,
    buf: String,
    child: Child,
    observer: Option<Observer>,
    deadline: Option<u64>,
    pending: Option<String>,
}

impl Pool {
    pub async fn acquire(&mut self) -> u32 {
        self.conns.pop().unwrap_or(0)
    }

    pub async fn take(&mut self) -> u32 {
        self.acquire().await
    }

    pub fn kill(&mut self) {
        match self.child.id() {
            Some(pid) => drop(pid),
            _ => {}
        }
    }

    pub fn observe(&self, kind: String) {
        if let Some(observer) = &self.observer {
            observer.emit(kind);
        }
    }

    pub fn clear(&mut self) {
        let _ = self.deadline.take();
    }

    pub fn cancel(&mut self) {
        if let Some(id) = self.pending.clone() {
            drop(id);
        }
    }

    pub fn count(&self) -> usize {
        let n = self.items.len();
        n
    }

    pub fn reply(&self) -> Reply {
        Reply { body: self.buf.clone() }
    }

    pub fn named(&self, k: &str) -> u32 {
        if let Some(v) = self.names.get(k) {
            return *v;
        }
        0
    }
}
'''


def _silent(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "lib.rs").write_text(_ORDINARY)
    reading = state_bounds.classify(tmp_path, "rust")
    return {f["state"]: f["construct"] or f["silence"]
            for f in reading["findings"] if f["silence"]}


def test_a_call_awaited_is_read(tmp_path):
    """Nineteen of the crate's silences, the largest cluster with a rule available.
    Awaiting hands back the value, which is what this reader already says about a
    parenthesised expression and a `?`."""
    assert "self.conns" not in _silent(tmp_path), _silent(tmp_path)


def test_a_call_result_matched_on_is_read(tmp_path):
    """`match self.child.id()`. The reader has a rule for a match on the state itself and
    none for a match on a value derived from it, which is the commoner of the two."""
    assert "self.child" not in _silent(tmp_path), _silent(tmp_path)


def test_a_borrow_tested_by_if_let_is_read(tmp_path):
    """`if let Some(observer) = &self.observer`. The pattern matches or it does not, which
    is the same two-class split this reader already draws for a plain condition."""
    assert "self.observer" not in _silent(tmp_path), _silent(tmp_path)


def test_a_call_bound_by_if_let_is_read(tmp_path):
    """`if let Some(id) = self.pending.clone()`. The earlier draft of this test used a
    keyed read here and passed by accident: the keyed rule answers before the condition is
    ever reached, so it proved nothing about the condition."""
    assert "self.pending" not in _silent(tmp_path), _silent(tmp_path)


def test_a_result_bound_to_the_discard_is_read(tmp_path):
    """`let _ = self.deadline.take()`. Nobody reads it, which is the conclusion this reader
    already draws for a value the language discards."""
    assert "self.deadline" not in _silent(tmp_path), _silent(tmp_path)


def test_a_value_placed_in_a_struct_literal_is_read(tmp_path):
    """`Reply { body: self.buf.clone() }`. The value comes to rest in a field, reaching no
    arm selector at this site."""
    assert "self.buf" not in _silent(tmp_path), _silent(tmp_path)


def test_a_call_bound_to_a_local_is_read(tmp_path):
    assert "self.items" not in _silent(tmp_path), _silent(tmp_path)


def test_nothing_in_an_ordinary_rust_file_is_left_unmodelled(tmp_path):
    """The whole file, so a repair that clears one shape and leaves the next is visible."""
    assert _silent(tmp_path) == {}, _silent(tmp_path)
