"""The ratchet message says which tree produced the number it wants written down.

It said "the repo has 20. Lower it to 20 in .pre-commit-config.yaml" after counting one
subdirectory, while that config gates the repository root where the count is 27. Following
the instruction loosened the gate by seven and the message read as authoritative, because
nothing in it said which tree it had measured.

Two owners again: the tree the run measured and the tree the config gates. Nothing checked
they were the same, and the message asserted they were by naming a file it had not read.
"""

from pathlib import Path

from l1_analyzer.gate import _slack


def test_the_message_names_the_tree_the_count_came_from():
    said = _slack(20, 27, "type escapes (L1.15)", Path("/repo/tools/analyzer"))
    assert "tools/analyzer" in said[0]


def test_the_message_does_not_name_a_config_file_it_did_not_read():
    """Naming .pre-commit-config.yaml turns a count over one subtree into an instruction
    about a file that gates another. The number goes in the message; where it belongs is
    the reader's to decide, because only the reader knows which tree the gate runs on."""
    said = _slack(20, 27, "type escapes (L1.15)", Path("/repo/tools/analyzer"))
    assert ".pre-commit-config.yaml" not in said[0]


def test_the_message_still_says_the_two_numbers_and_the_gap():
    said = _slack(20, 27, "type escapes (L1.15)", Path("/repo"))
    assert "27" in said[0] and "20" in said[0] and "7 regression" in said[0]


def test_a_ratchet_at_or_below_reality_says_nothing():
    assert _slack(27, 27, "type escapes (L1.15)", Path("/repo")) == []
    assert _slack(30, 27, "type escapes (L1.15)", Path("/repo")) == []
