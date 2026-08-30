"""A record extending a record is not inheritance, wherever the base was written.

The clause clears `class Row(TypedDict)` and `class Wide(Row)` when both sit in one file,
and reported `class Wide(Row)` when `Row` sits in the next file along. That is not a rule
about inheritance, it is a rule about which file a declaration happens to be in, and this
repository hit it twice in one afternoon: two record shapes extending one that lives in
another module, each needing the same written excuse.

The whole-repository run reads every file, so it can see that the base is a declared shape.
The per-file run behind the write hook cannot, and still says so: it reports the finding and
a reader looks, which is the honest answer when nothing here can decide.
"""

import pytest
from l1_analyzer import honest_code

_BASE = '''from typing import TypedDict


class Row(TypedDict):
    a: int
'''

_WIDE = '''from base import Row


class Wide(Row):
    b: int
'''


def _write(repo, files):
    for name, text in files.items():
        (repo / name).write_text(text)
    return repo


def test_the_whole_repository_run_follows_a_base_into_another_file(tmp_path):
    _write(tmp_path, {"base.py": _BASE, "wide.py": _WIDE})
    found = [f for f in honest_code.analyze(tmp_path, "python")["findings"]
             if f["clause"] == "L1.21.5"]
    assert found == [], found


def test_a_base_nothing_in_the_repository_declares_is_still_reported(tmp_path):
    """The rule this must not switch off. A base that reaches no declared shape anywhere is
    inheritance for reuse, and that is what the clause is for."""
    _write(tmp_path, {"engine.py": "class Engine:\n    def run(self):\n        return 1\n",
                      "car.py": "from engine import Engine\n\n\nclass Car(Engine):\n    pass\n"})
    found = [f for f in honest_code.analyze(tmp_path, "python")["findings"]
             if f["clause"] == "L1.21.5"]
    assert [f["symbol"] for f in found] == ["Car"], found


def test_the_single_file_run_still_reports_what_it_cannot_follow():
    """Behind a write hook there is one file and no tree to search, so the finding stands
    and sends a reader to look. Reporting it is the honest answer; clearing it would be a
    guess about a file this run never opened."""
    found = [f for f in honest_code.assess_file_text(_WIDE, "wide.py")["clauses"]
             if f["code"] == "L1.21.5"]
    assert found and found[0]["findings"], found


@pytest.mark.parametrize("depth", [2, 3])
def test_a_chain_through_another_file_is_followed_all_the_way(tmp_path, depth):
    """Followed to the root, the same as within one file. A three-deep record hierarchy
    split across three files is records all the way down."""
    files = {"base.py": _BASE}
    previous = "Row"
    for n in range(depth):
        name = f"wide{n}"
        files[f"{name}.py"] = f"from prev import {previous}\n\n\nclass Step{n}({previous}):\n    b: int\n"
        previous = f"Step{n}"
    _write(tmp_path, files)
    found = [f for f in honest_code.analyze(tmp_path, "python")["findings"]
             if f["clause"] == "L1.21.5"]
    assert found == [], found
