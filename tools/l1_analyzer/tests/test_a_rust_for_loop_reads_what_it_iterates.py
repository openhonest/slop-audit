"""Iterating a Rust collection reads it, rather than reporting a shape with no rule.

`for u in &urls { .. }` reads every cell the collection holds, so its reach is the cell set
and nothing wider. That rule exists and only Go had it: Rust's own `for` was never added to
the table it reads, so the plainest loop the language has came back as a construct nobody
had taught the reader.

Found by answering a question rather than by looking for it. Another Claude session asked
whether the reader could now follow an iterator chain they had written, of the form
`self.tags.iter().filter_map(..).collect()` feeding a `for` loop. The chain resolved, walked
into the local it was collected into, and stopped dead at the loop. It is two more sites on
crates/buzz-acp beside that.

The value is read from the loop's own `value` field, not by node type alone. A Rust `for`
holds the pattern, the value and the body as three children of one node, so matching on the
node type would have counted the loop BODY as the thing being iterated.
"""

from pathlib import Path

from l1_analyzer import state_bounds

_ITERATES = '''pub struct Q {
    tags: Vec<String>,
    body: String,
}

impl Q {
    pub fn render(&self) -> String {
        let urls: Vec<String> = self.tags.iter().map(|t| t.to_string()).collect();
        let mut out = self.body.clone();
        for u in &urls {
            out.push_str(u);
        }
        out
    }
}
'''

_DIRECT = '''pub struct Q {
    tags: Vec<String>,
}

impl Q {
    pub fn count(&self) -> usize {
        let mut n = 0;
        for t in &self.tags {
            n += t.len();
        }
        n
    }
}
'''


def _findings(tmp_path: Path, source: str) -> dict:
    (tmp_path / "lib.rs").write_text(source)
    return {f["state"]: f for f in state_bounds.classify(tmp_path, "rust")["findings"]}


def test_a_chain_that_ends_in_a_loop_is_read_all_the_way(tmp_path):
    """The shape that found this. The chain resolves, follows the local it was collected
    into, and used to stop at the loop."""
    found = _findings(tmp_path, _ITERATES)
    assert found["self.tags"]["silence"] == "", found["self.tags"]["construct"]


def test_iterating_the_state_itself_is_read(tmp_path):
    assert _findings(tmp_path, _DIRECT)["self.tags"]["silence"] == ""


def test_the_loop_body_is_not_mistaken_for_the_thing_iterated(tmp_path):
    """A Rust `for` holds its pattern, its value and its body as three children of one node.
    Matching on the node type alone would read a state mentioned anywhere in the body as the
    collection being walked, which is a different claim and a false one."""
    body_only = '''pub struct Q { tags: Vec<String>, other: Vec<String> }

impl Q {
    pub fn go(&self) -> usize {
        let mut n = 0;
        for t in &self.tags {
            n += self.other.len() + t.len();
        }
        n
    }
}
'''
    found = _findings(tmp_path, body_only)
    assert found["self.other"]["verdict"] == "neutral", found["self.other"]
