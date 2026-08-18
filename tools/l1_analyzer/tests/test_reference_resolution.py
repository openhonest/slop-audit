"""A same-named symbol in an unrelated module does not prove a definition alive (L1.12).

The corpus maps a bare NAME to its reference sites with no notion of which module a
reference resolves to, so any identifier anywhere in production keeps a definition alive.

`vacuity.py` is the case that named it: correctly detected as an island, no importer, no
main guard, no declared script, no module-level call. Yet zero of its sixty definitions
are reported, because the generic ones are rescued by coincidence. `check` is referenced
by indicators.py, pytest_trace.py and python_coverage_prove.py. `render` by card.py and
validate.py. Only names unique in the whole repository survive to be reported.

The rule: a reference in file X proves a definition in file Y alive only when X can SEE
Y, meaning X imports Y or imports the name from Y. Applied to islands alone, where the
question is already being asked and where a wrong answer is the difference between
reporting a subsystem and reporting nothing.

Python only. The import-to-module rule is Python's, and every other language keeps the
name-pooled behaviour, which under-accuses.
"""

import pathlib

from l1_analyzer import dead_code


def _flagged(tmp_path: pathlib.Path, files: dict[str, str]) -> set[str]:
    for name, body in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(body)
    return {f["name"] for f in (dead_code.analyze(tmp_path, "python").get("findings") or [])}


_ISLAND = "def check(x):\n    return helper(x)\n\n\ndef helper(x):\n    return x + 1\n"


def test_a_coincidence_elsewhere_does_not_rescue_an_island(tmp_path):
    """`other.py` defines and calls its OWN `check`. It never imports the island, so it
    says nothing about the island's `check`."""
    flagged = _flagged(tmp_path, {
        "main.py": "import other\n\n\ndef main():\n    return other.check(1)\n",
        "other.py": "def check(x):\n    return x\n",
        "island.py": _ISLAND,
    })
    assert "helper" in flagged, "the island's helper is reachable from nothing"


def test_a_real_importer_still_keeps_the_module_alive(tmp_path):
    """The guard. Once something imports the island it is not an island, and its internal
    calls count again."""
    flagged = _flagged(tmp_path, {
        "main.py": "import island\n\n\ndef main():\n    return island.check(1)\n",
        "island.py": _ISLAND,
    })
    assert "helper" not in flagged
    assert "check" not in flagged
