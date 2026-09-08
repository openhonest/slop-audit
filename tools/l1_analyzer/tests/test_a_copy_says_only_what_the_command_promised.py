"""`cp --reflink=auto` means "reflink or copy", and the report read it as "reflinked".

The pool records how each checkout was made, so a reader can tell eight nearly-free copies
from eight full ones. It decided that from the copy command's exit status, and one of the
commands does not answer that question.

`--reflink=auto` falls back to a full copy when the filesystem cannot share blocks, and
exits 0 either way. Measured on ext4 on 2026-09-07 by the session auditing turso: a 100 MB
directory copied with `--reflink=auto` exited 0 and cost 102,404K of real disk. So a run
that paid 48 GB for eight checkouts printed "8 checkouts copied by reference".

`--reflink=always` is the spelling that refuses when it cannot share, which is the question
being asked. It is what the code asks now, and a filesystem that says no falls through to
the plain copy and is reported as the plain copy.

The run before the GNU spelling was added said "byte for byte" and was right. Adding a
command that answers a different question made a true sentence false, which is the same
defect as a coverage row banding a tree with no tests: a confident answer to a question
nobody asked.
"""

from __future__ import annotations

from l1_analyzer import sweep_pool


def test_no_command_that_may_silently_fall_back_is_asked():
    """`--reflink=auto` cannot answer "did this share blocks", so it is not asked."""
    commands = [" ".join(c) for c, _how in sweep_pool.copy_commands("/from", "/to")]
    assert not any("reflink=auto" in c for c in commands), commands


def test_the_command_that_refuses_rather_than_falling_back_is_the_one_asked():
    commands = [" ".join(c) for c, _how in sweep_pool.copy_commands("/from", "/to")]
    assert any("reflink=always" in c for c in commands), commands


def test_every_command_says_which_answer_it_would_prove():
    """A command in this list carries the sentence its success earns. A command whose
    success means something weaker must carry the weaker sentence or not be here."""
    for command, how in sweep_pool.COPY_COMMANDS:
        assert how in {"by reference", "byte for byte"}, (command, how)
        if "reflink" in " ".join(command) or "-Rc" in command:
            assert how == "by reference", command
        else:
            assert how == "byte for byte", command


def test_the_plain_copy_is_last_so_it_is_what_a_refusal_falls_through_to():
    assert sweep_pool.COPY_COMMANDS[-1][1] == "byte for byte"
