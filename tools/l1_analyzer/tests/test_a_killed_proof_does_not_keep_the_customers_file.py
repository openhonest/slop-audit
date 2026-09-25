"""A proof is written into the customer's own source file, and a kill used to keep it there.

A test has to be inside the crate to reach what it is proving, so the coverage prove loop
appends one to the module's own file, compiles, and puts the file back. The normal path
restores it and so does every exception. A SIGKILL does not, and this audit kills things by
design: every untrusted run is in a process group with a hard timeout and the group is killed
when a suite hangs. A kill that reaches the analyzer itself leaves machine-written code in
somebody else's source file, and nothing tells them.

The original bytes are written outside the tree before the file is touched, and the next run
puts them back. Outside, because a record inside the tree is a second thing left behind and
because a `git clean` between the crash and the recovery would delete the only copy.

It is not a guarantee, and the module says so: a reader who never runs the tool again never
gets their file back, and git already holds the original for them. It is the difference
between a mess that heals and one that waits.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from l1_analyzer.boundary import boundary
from l1_analyzer.proof_recovery import recovery_record, restore_interrupted_proof

ORIGINAL = "pub fn band(n: i32) -> &'static str {\n    if n < 0 { \"neg\" } else { \"pos\" }\n}\n"
LEFT_BEHIND = ORIGINAL + "\n#[cfg(test)]\nmod l1_coverage_proof { /* a model wrote this */ }\n"


@boundary
def a_crate_mid_edit(tmp_path: Path) -> Path:
    """A checkout whose source file carries a proof, and the record an interrupted run left."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "band.rs").write_text(LEFT_BEHIND)
    recovery_record(tmp_path).write_text(json.dumps(
        {"path": "src/band.rs",
         "original": base64.b64encode(ORIGINAL.encode("utf8")).decode("ascii")}))
    return tmp_path


def test_the_next_run_puts_the_customers_file_back(tmp_path):
    repo = a_crate_mid_edit(tmp_path)
    said = restore_interrupted_proof(repo)
    assert (repo / "src" / "band.rs").read_text() == ORIGINAL
    assert "src/band.rs" in said, said


def test_the_record_is_removed_so_a_later_run_does_not_undo_real_work(tmp_path):
    """A record left lying about would overwrite whatever the author wrote next, which is a
    worse failure than the one being repaired."""
    repo = a_crate_mid_edit(tmp_path)
    restore_interrupted_proof(repo)
    assert not recovery_record(repo).exists()
    (repo / "src" / "band.rs").write_text("what the author wrote afterwards\n")
    assert restore_interrupted_proof(repo) == ""
    assert (repo / "src" / "band.rs").read_text() == "what the author wrote afterwards\n"


def test_a_clean_checkout_is_left_alone_and_says_nothing(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "band.rs").write_text(ORIGINAL)
    assert restore_interrupted_proof(tmp_path) == ""
    assert (tmp_path / "src" / "band.rs").read_text() == ORIGINAL


def test_a_record_that_cannot_be_read_says_so_rather_than_vanishing(tmp_path):
    """The bytes may still be in it. Deleting it silently would throw away the only copy of
    somebody's file to tidy up an error message."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "band.rs").write_text(LEFT_BEHIND)
    recovery_record(tmp_path).write_text("not json")
    said = restore_interrupted_proof(tmp_path)
    assert "could not be read" in said, said
    assert recovery_record(tmp_path).exists()
    recovery_record(tmp_path).unlink()


def test_two_checkouts_do_not_share_one_record(tmp_path):
    """The sweep runs several checkouts at once, and one record for all of them would put one
    crate's file into another's."""
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir()
    second.mkdir()
    assert recovery_record(first) != recovery_record(second)
