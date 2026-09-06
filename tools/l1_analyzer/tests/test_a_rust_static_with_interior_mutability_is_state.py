"""`static mut` is how Rust used to hold global state. Nobody writes it any more.

The classifier admitted a static only when it carried the `mut` keyword and declined every
other one as immutable. `static mut` requires `unsafe` at every access and modern Rust
avoids it: global mutable state is written with interior mutability instead, which is what
the atomics, the locks and the cells are for. So the two shapes that are how Rust actually
does this both read as nothing:

    pub static COUNTER: AtomicUsize = AtomicUsize::new(0);          declined
    pub static CACHE: Mutex<Option<HashMap<String, u64>>> = ...;    declined
    pub static mut COUNTER: u64 = 0;                                admitted

Found on 2026-09-06, immediately after the same defect was found in JavaScript, where every
`const` was declined on a keyword that describes the binding rather than the thing bound.
Here the keyword describes how the state is reached rather than whether there is any.

It matters more than the JavaScript one. The type is not a hint: `Mutex` and the atomics
exist to be mutated through a shared reference, so a static of that type is mutable state by
construction and there is nothing to infer.

A static that is genuinely a constant is still declined, and that is a reading rather than a
gap: a `static NAMES: [&str; 3]` cannot be written through and nothing in the program can
change it.
"""

from __future__ import annotations

import subprocess

import pytest

_ATOMIC = """use std::sync::atomic::{AtomicUsize, Ordering};

pub static COUNTER: AtomicUsize = AtomicUsize::new(0);

pub fn bump() -> usize {{ COUNTER.fetch_add(1, Ordering::SeqCst) }}
"""

_MUTEX = """use std::collections::HashMap;
use std::sync::Mutex;

pub static CACHE: Mutex<Option<HashMap<String, u64>>> = Mutex::new(None);

pub fn put(k: String, v: u64) {{
    let mut guard = CACHE.lock().unwrap();
    if let Some(map) = guard.as_mut() {{ map.insert(k, v); }}
}}
"""

_LOCK = """use std::sync::OnceLock;

pub static CONFIG: OnceLock<String> = OnceLock::new();

pub fn set(v: String) {{ let _ = CONFIG.set(v); }}
"""

_FROZEN = """pub static NAMES: [&str; 3] = ["a", "b", "c"];

pub fn first() -> &'static str {{ NAMES[0] }}
"""


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _classify(tmp_path, source: str) -> dict:
    from l1_analyzer import state_bounds

    (tmp_path / "lib.rs").write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return state_bounds.classify(tmp_path, "rust")


@pytest.mark.parametrize("source,name", [(_ATOMIC, "atomic"), (_MUTEX, "mutex"), (_LOCK, "once")],
                         ids=["atomic", "mutex", "once"])
def test_a_static_reached_through_interior_mutability_is_state(tmp_path, source, name):
    """The three shapes that are how Rust holds global mutable state, all read as nothing."""
    counts = _classify(tmp_path, source)["counts"]
    assert sum(counts.values()) == 1, counts


def test_a_static_that_cannot_be_written_through_is_still_declined(tmp_path):
    """The other direction, and the reason this is not counting every static. An array of
    string slices cannot be written through and nothing in the program can change it, so
    declining it is a reading rather than a gap."""
    counts = _classify(tmp_path, _FROZEN)["counts"]
    assert sum(counts.values()) == 0, counts


def test_the_old_spelling_still_reads_as_state(tmp_path):
    """`static mut` was the only shape this reader ever admitted and it must keep being one.
    A fix that traded one blindness for another would be worse than the defect."""
    counts = _classify(tmp_path, "pub static mut COUNTER: u64 = 0;\n"
                                 "pub fn bump() {{ unsafe {{ COUNTER += 1; }} }}\n")["counts"]
    assert sum(counts.values()) == 1, counts
