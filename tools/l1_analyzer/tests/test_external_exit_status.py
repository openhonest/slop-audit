"""A scanner's non-zero exit is its finding, not its failure (L1.13, L1.14).

The regression this replaces: `_run_external` must return the tool's real status AND its
real output. gitleaks exits 1 and vulture exits 3 WHEN THEY FIND SOMETHING, so a reader
that treats a non-zero exit as "the tool failed" and discards the output reports Healthy
on a dirty repository. That is the worst shape of failure this project names, because the
number it publishes is the clean one.

The test that proved it was deleted in the 2026-08-17 fixture sweep. It drove a /bin/sh
stub that echoed a canned duplication percentage, so it proved the parser against the
test author's own string rather than against a tool.

This uses `grep -c`, which is a real tool exiting non-zero for its own real reason: no
match found. It prints "0" on stdout and exits 1, which is exactly the shape the contract
has to survive. No stub, and nothing here asserts a string this file wrote.
"""

import shutil

import pytest
from l1_analyzer import indicators


def test_a_tool_that_exits_non_zero_still_has_its_output_read(tmp_path):
    (tmp_path / "f.txt").write_text("alpha\nbeta\n")
    run = indicators._run_external(["grep", "-c", "needle", "f.txt"], tmp_path)
    assert run["ran"] is True
    assert run["status"] != 0          # grep says: found nothing
    assert run["output"].strip() == "0"  # and still told us what it counted


def test_the_status_is_the_tools_own_and_is_not_flattened(tmp_path):
    """`ran` answers whether the tool executed. `status` answers what it concluded. A
    reader that collapses the two cannot tell "not installed" from "found something"."""
    (tmp_path / "f.txt").write_text("alpha\n")
    found = indicators._run_external(["grep", "-c", "alpha", "f.txt"], tmp_path)
    missing = indicators._run_external(["grep", "-c", "needle", "f.txt"], tmp_path)
    absent = indicators._run_external([str(tmp_path / "no-such-binary")], tmp_path)
    assert (found["ran"], found["status"]) == (True, 0)
    assert missing["ran"] is True and missing["status"] == 1
    assert absent["ran"] is False


@pytest.mark.skipif(shutil.which("jscpd") is None, reason="jscpd is not installed on this machine")
def test_l1_13_reads_a_real_jscpd_run_that_exits_non_zero(tmp_path):
    """The end-to-end half, against the real scanner. jscpd exits non-zero when
    duplication crosses its threshold, which is the case L1.13 exists to report, so an
    exit-status guard would turn a real finding into n/a. Skipped rather than stubbed
    where jscpd is absent: a stub here would assert this file's own string."""
    block = "".join(f"def f{{i}}_{n}(a, b):\n    return (a + b) * {n}\n\n\n" for n in range(12))
    for i in range(2):
        (tmp_path / f"dup{i}.py").write_text(block.replace("{i}", str(i)))
    res = indicators._compute_external_indicators(tmp_path, "python")
    assert res["L1.13"]["band"] != "n/a", res["L1.13"]["details"]
    assert res["L1.13"]["value"] > 0
