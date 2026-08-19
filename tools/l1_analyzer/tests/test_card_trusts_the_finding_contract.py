"""The card reads a Finding by its contract, not by guessing at absent keys.

`Finding` is a total TypedDict: state, verdict, drives_decision, file, line, silence,
construct and partition are present on every finding the analyzer produces. The card read
them as `f.get("line", 0)` and `f.get("state", "?")` anyway.

Those defaults are two failures at once. They defend a contract the type already holds,
which is distrust of our own signature; and if the contract ever did break they would
render a fabricated line 0 at file "" with a state of "?" as though it were measured. An
absent field must stop the render, not fill itself in with something that looks like data.

The distinction the test draws: `results.get("interleaving_robustness")` stays, because an
indicator that did not run is genuinely absent from the panel. Reading a field OF a
finding is what has a contract.
"""

import pathlib
import re

from l1_analyzer import card

_SOURCE = pathlib.Path(card.__file__).read_text()

_CONTRACT_FIELDS = ("state", "verdict", "drives_decision", "file", "line",
                    "silence", "construct", "partition", "classes")


def test_no_finding_field_is_read_with_a_fall_through_default():
    offenders = []
    for number, line in enumerate(_SOURCE.split("\n"), start=1):
        code = line.split("#", 1)[0]
        for field in _CONTRACT_FIELDS:
            if re.search(rf'\.get\(\s*"{field}"\s*,', code):
                offenders.append(f"card.py:{number} {field}")
    assert not offenders, f"contract fields read with a fabricated default: {offenders}"
