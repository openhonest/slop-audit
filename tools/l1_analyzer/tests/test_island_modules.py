"""A module nothing imports does not certify its own contents (L1.12).

`_classify_files` puts every non-test file in the production reference set, including
the file a definition is defined in. So a module whose functions call each other is
proven alive by its own internal calls, even when nothing outside it ever imports the
module. An island subsystem is invisible to the dead-code indicator by construction, and
the bigger the island the more thoroughly it certifies itself.

This repository is the case that found it: `vacuity.py` is 892 lines holding 40
functions, its only importer is its own test, and L1.12 reported 0.17 Healthy with two
of those forty named. The rest were alive because vacuity called vacuity.

The rule: a production module that no OTHER production file names is an island, and
references from inside an island do not prove its definitions alive. References from
outside still do, which is what keeps an ordinary module's private helpers alive.
"""

import pathlib

from l1_analyzer import dead_code


def _flagged(tmp_path: pathlib.Path, files: dict[str, str]) -> set[str]:
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    r = dead_code.analyze(tmp_path, "python")
    return {f["name"] for f in (r.get("findings") or [])}


_ISLAND = "def helper(x):\n    return x + 1\n\n\ndef entry(x):\n    return helper(x)\n"


def test_an_island_module_does_not_prove_its_own_functions_alive(tmp_path):
    """`entry` calls `helper` and nothing calls `entry`. Nothing imports the module, so
    neither is reachable and both are dead."""
    flagged = _flagged(tmp_path, {"main.py": "def main():\n    return 1\n", "island.py": _ISLAND})
    assert {"helper", "entry"} <= flagged


def test_an_imported_module_still_keeps_its_private_helpers_alive(tmp_path):
    """The guard. Once something outside names the module, its internal calls count
    again, so a private helper called only by its own module's public function is alive."""
    flagged = _flagged(tmp_path, {
        "main.py": "import island\n\n\ndef main():\n    return island.entry(1)\n",
        "island.py": _ISLAND,
    })
    assert "helper" not in flagged
    assert "entry" not in flagged


def test_a_module_named_only_from_the_test_tree_is_still_an_island(tmp_path):
    """A test importing the module is what `test_only` already reports. It must not also
    make the module's internal calls count as production references, or a subsystem stays
    certified by its own tests plus itself."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_island.py").write_text("import island\n\n\ndef test_it():\n    assert island.entry(1) == 2\n")
    flagged = _flagged(tmp_path, {"main.py": "def main():\n    return 1\n", "island.py": _ISLAND})
    assert "helper" in flagged
