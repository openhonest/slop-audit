"""The findings list serializes in one order, so a diff of two runs over unchanged code
is empty.

This is a SERIALIZATION defect, not a determinism defect, and the distinction decides what
the fix has to guarantee. The measurement is deterministic: every run produces identical
verdicts, identical counts, identical bands and an identical grade. Only the order of the
rows moved. Calling it non-determinism says the opposite of what is true and would send a
reader looking for a wobble in the numbers, where there is none.

The requirement is that an agent watching for change is not shown change that is not there.
Bead slop-audit-8rt.

Where it came from: `_enum_module_state` and `_enum_instance_state` returned `set[str]`, and
`_analyze_file` iterated them to build findings. The final `findings.sort` keys on verdict,
drives_decision, file and line, so two states declared on the same line tie on all four.
Python's sort is stable, so a tie preserves the order the enumerator handed over, which for
a set of strings varies between processes.

The fixture has to defeat the sort's own tiebreak or it proves nothing. Six states are
declared on ONE line, so file and line are equal, and all six are read the same way, so
verdict and drives_decision are equal too. A fixture where line numbers already separate the
states would pass before the fix as well as after, which is the trap to avoid.

The runs are separate PROCESSES with the hash seed left random, because string hashing is
randomized per interpreter start: five calls inside one process would agree with each other
whatever the enumerator returned.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Six module-level dicts on one line, each read with a variable key in one function, so
# every finding lands on file `m.py`, line 1, verdict promiscuous, drives_decision True.
ONE_LINE_SOURCE = (
    "alpha = {}; bravo = {}; charlie = {}; delta = {}; echo = {}; foxtrot = {}\n"
    "def use(k):\n"
    "    return alpha[k], bravo[k], charlie[k], delta[k], echo[k], foxtrot[k]\n"
)

_PROBE = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "from l1_analyzer import state_bounds\n"
    "r = state_bounds.classify(Path(sys.argv[1]), 'python')\n"
    "print(json.dumps([[f['state'], f['line'], f['verdict']] for f in r['findings']]))\n"
)

RUNS = 6


def _findings_in_a_fresh_process(repo: Path) -> list[list[object]]:
    env = {**os.environ, "PYTHONHASHSEED": "random"}
    out = subprocess.run([sys.executable, "-c", _PROBE, str(repo)],
                         capture_output=True, text=True, check=True, env=env).stdout
    return json.loads(out)


def test_six_states_on_one_line_serialize_in_the_same_order_every_run(tmp_path):
    (tmp_path / "m.py").write_text(ONE_LINE_SOURCE)
    runs = [_findings_in_a_fresh_process(tmp_path) for _ in range(RUNS)]

    states = [row[0] for row in runs[0]]
    assert len(states) == 6, f"the fixture must produce six findings, got {states}"
    assert len({row[1] for row in runs[0]}) == 1, "all six must share one line, or the sort breaks the tie"
    assert len({row[2] for row in runs[0]}) == 1, "all six must share one verdict, or the sort breaks the tie"

    distinct = {json.dumps(r) for r in runs}
    assert len(distinct) == 1, (
        f"{len(distinct)} different orders across {RUNS} runs of unchanged code:\n"
        + "\n".join(sorted(distinct))
    )


def test_the_order_is_the_order_the_states_appear_in_the_source(tmp_path):
    """Insertion order is source order, and a reader scanning findings down a file is better
    served by that than by an alphabetical list. Sorting the keys would also be stable, so
    this is the assertion that says which stable order was chosen."""
    (tmp_path / "m.py").write_text(ONE_LINE_SOURCE)
    states = [row[0] for row in _findings_in_a_fresh_process(tmp_path)]
    assert states == ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]


def test_instance_state_on_one_line_also_serializes_stably(tmp_path):
    """The other enumerator. `_enum_instance_state` returned a set too, and a class whose
    attributes are assigned on one line ties on every sort key exactly as module state does."""
    (tmp_path / "c.py").write_text(
        "class Store:\n"
        "    def __init__(self):\n"
        "        self.one = {}; self.two = {}; self.three = {}; self.four = {}\n"
        "    def read(self, k):\n"
        "        return self.one[k], self.two[k], self.three[k], self.four[k]\n"
    )
    runs = [json.dumps(_findings_in_a_fresh_process(tmp_path)) for _ in range(RUNS)]
    assert len(set(runs)) == 1, f"{len(set(runs))} different orders:\n" + "\n".join(sorted(set(runs)))
    states = [row[0] for row in _findings_in_a_fresh_process(tmp_path)]
    assert states == ["self.one", "self.two", "self.three", "self.four"]
