"""Clause 4 on the two coverage runs: the payload reading lifted out of the running.

Both ran a suite, ran `coverage json`, and then read the report in the same function. So
the reading could only be exercised by running a real suite under coverage, and the reading
is where the interesting decisions are.

One of them carries a bug this instrument found in itself. A module that raised on import
reported 100% covered, which is unmeasured read as clean, the exact category this tool
exists to name. The guard for it lives in the running half; what comes out here is the part
that decides what a payload says about one module.
"""

import pathlib

from l1_analyzer import facets, python_coverage_prove

_PAYLOAD = {
    "files": {
        "/somewhere/m.py": {"summary": {"percent_covered": 82.5},
                            "missing_lines": [4, 9, 12]},
        "/somewhere/other.py": {"summary": {"percent_covered": 10.0},
                                "missing_lines": [1]},
    }
}


def test_the_module_entry_is_found_by_file_name():
    missing, pct = facets.coverage_in(_PAYLOAD, "m.py")
    assert missing == frozenset({4, 9, 12})
    assert pct == 82.5


def test_a_payload_naming_no_such_module_reports_nothing_rather_than_zero():
    """Nothing measured is not nothing missing. Reporting an empty set and a percentage
    would say the module was fully covered by a run that never saw it."""
    missing, pct = facets.coverage_in(_PAYLOAD, "absent.py")
    assert missing == frozenset() and pct is None


def test_an_entry_with_no_summary_percentage_still_yields_its_missing_lines():
    payload = {"files": {"/x/m.py": {"summary": {}, "missing_lines": [3]}}}
    missing, pct = facets.coverage_in(payload, "m.py")
    assert missing == frozenset({3}) and pct is None


def test_the_missing_lines_are_kept_only_for_files_inside_the_repository():
    """A suite that imports an installed package reports coverage for it too, and those
    lines are not this repository's to answer for."""
    repo = pathlib.Path("/repo")
    report = {"files": {"src/m.py": {"missing_lines": [2, 5]},
                        "/usr/lib/python3/site-packages/x.py": {"missing_lines": [7]},
                        "src/clean.py": {"missing_lines": []}}}
    found = python_coverage_prove.missing_by_file(report, repo)
    assert set(found) == {"src/m.py"}
    assert found["src/m.py"] == frozenset({2, 5})


def test_both_readers_run_nothing():
    for module, name in ((facets, "coverage_in"),
                         (python_coverage_prove, "missing_by_file")):
        body = pathlib.Path(module.__file__).read_text().split(f"def {name}")[1].split("\ndef ")[0]
        for reach in ("subprocess", "TemporaryDirectory", "read_text", "run("):
            assert reach not in body, (name, reach)
