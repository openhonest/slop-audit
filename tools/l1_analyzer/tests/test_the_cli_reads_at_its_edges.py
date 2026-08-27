"""Clause 4 in the CLI: the two decisions lifted out, and the entry point declared.

`_hazard_context` read a file and then chose a window of it. `_report_call_map` read a
module and then parsed and classified it. In both, the deciding could not be exercised
without a filesystem, so a question as small as "what does a hazard on line 2 of a
five-line file look like" needed a temporary directory to ask.

`main` is different and is declared rather than split. It IS the edge: argparse in, exit
code out, and every decision inside it already lives in a module it calls.
"""

import pathlib

from l1_analyzer import cli


def test_the_window_around_a_hazard_is_chosen_from_the_lines():
    lines = [f"line {n}" for n in range(1, 101)]
    window = cli.window_around(lines, 50)
    # Thirty either side by index, which puts line 50 at lines 21 to 80. Asserted as the
    # original computed it: this is a lift, and a refactor that quietly moves a window by
    # one is a refactor that changed what the generator was shown.
    assert window.splitlines()[0] == "line 21"
    assert window.splitlines()[-1] == "line 80"
    assert "line 50" in window


def test_a_hazard_near_the_top_does_not_run_off_the_start():
    assert cli.window_around([f"line {n}" for n in range(1, 6)], 2).startswith("line 1")


def test_a_hazard_near_the_bottom_does_not_run_off_the_end():
    assert cli.window_around([f"line {n}" for n in range(1, 6)], 4).endswith("line 5")


def test_a_file_of_no_lines_yields_no_window():
    assert cli.window_around([], 1) == ""


def test_the_window_chooser_touches_nothing():
    source = pathlib.Path(cli.__file__).read_text()
    body = source.split("def window_around")[1].split("\ndef ")[0]
    for reach in ("read_text", "read_bytes", "open(", "Path("):
        assert reach not in body, reach


def test_the_entry_point_is_declared_the_boundary():
    """It is not split, because there is nothing in it to lift: argparse in, exit code out,
    and every decision already lives in a module it calls."""
    source = pathlib.Path(cli.__file__).read_text()
    assert "@boundary\ndef main(" in source


def test_no_clause_four_finding_survives_in_the_cli():

    from l1_analyzer import honest_code_edges as edges
    from l1_analyzer import honest_code_read as read

    source = pathlib.Path(cli.__file__).read_text()
    found = edges.io_below_the_boundary(read.read_tree(source, "python")) or []
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == []
