"""Putting back a source file an interrupted proof run was part-way through editing.

A PROOF IS WRITTEN INTO THE CUSTOMER'S OWN SOURCE FILE. A test has to be inside the crate to
reach what it is proving, so the coverage prove loop appends one to the module's own file,
compiles, and puts the file back. The ordinary path restores it and so does every exception.
A SIGKILL does not, and this audit kills things by design: every untrusted run sits in a
process group with a hard timeout and the group is killed when a suite hangs. A kill that
reaches the analyzer itself leaves machine-written code in somebody else's file.

So the original bytes are written outside the tree before the file is touched, and the next
run puts them back. It is not a guarantee: a reader who never runs the tool again never gets
their file back, and git already holds the original for them. It is the difference between a
mess that heals and one that waits.

Its own module because it is its own concern. Everything else in the prove loop is about
finding an uncovered branch and proving it; this is about not damaging somebody's repository
while doing so, and it is the part that has to be right when everything else has gone wrong.
"""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
from pathlib import Path

from l1_analyzer.boundary import boundary


def recovery_record(repo: Path) -> Path:
    """Where this repository's in-flight edit is recorded, outside the repository itself.

    Outside, because a record inside the tree is a second thing left behind, and because a
    `git clean` between the crash and the recovery would delete the only copy of the original.
    Named from the resolved path, so two audits of two checkouts do not overwrite each other's
    record and two audits of the SAME checkout cannot both be mid-edit without noticing."""
    key = hashlib.sha256(str(repo.resolve()).encode("utf8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"l1-proof-recovery-{key}.json"


@boundary
def restore_interrupted_proof(repo: Path) -> str:
    """Put back a file an earlier run was part-way through editing, and say which.

    A PROOF IS WRITTEN INTO THE CUSTOMER'S OWN SOURCE FILE. A test has to be inside the crate
    to reach what it is proving, so the loop appends one, compiles, and puts the file back. The
    normal path and every exception restore it; a SIGKILL does not, and the audit kills things
    by design, so the kill that reaches the analyzer leaves machine-written code in somebody
    else's file.

    The record makes that survivable: the original bytes are written outside the tree before
    the file is touched, and the next run puts them back. It is not a guarantee, because a
    reader who never runs again never gets their file back, and git already holds the original
    for them. It is the difference between a mess that heals and one that waits."""
    record = recovery_record(repo)
    if not record.is_file():
        return ""
    try:
        saved = json.loads(record.read_text())
        target = repo / saved["path"]
        target.write_bytes(base64.b64decode(saved["original"]))
    except (OSError, ValueError, KeyError, TypeError):
        # The record itself is unreadable, which is a fact about the record and not about the
        # repository. Saying so beats deleting it silently: the bytes may still be in it.
        return f"a recovery record at {record} could not be read, so nothing was restored"
    record.unlink(missing_ok=True)
    return f"restored {saved['path']}, which an interrupted run had left with a proof in it"
