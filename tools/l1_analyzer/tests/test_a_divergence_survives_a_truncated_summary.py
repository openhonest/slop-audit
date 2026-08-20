"""A fired assertion is a divergence, however pytest wraps its summary line.

Found live on 2026-08-20 by a positive control: a repository with two PLANTED bugs at
uncovered branches. The model proposed the correct assertions (900.0 for the discounted
total, "heavy" for the 25kg parcel), both fired against the planted code, and the sweep
reported both as "passed (branch correct)". Zero retained, over bugs planted to be found.

Two faults chained. `_classify` recognised a divergence only from pytest's short-summary
line `FAILED file::proof_0 - AssertionError: ...`, and pytest truncates that line's
` - reason` suffix to the terminal width. The proof file lives under a macOS tmpdir whose
path alone overflows 80 columns, so the reason NEVER survived and every real divergence
was binned "incidental". Then the repair loop, which exists to fix setup errors, saw
"incidental" and asked the model to rewrite the test until it stopped failing - which it
did, by asserting what the buggy code does. The machinery for repairing broken tests was
laundering proven bugs into clean passes.

The classifier now also reads the `--tb=line` row, `file.py:N: ExceptionName: msg`, which
pytest does not truncate, anchored to the proof file's own name so another file's
traceback cannot claim the verdict.
"""

from l1_analyzer import python_coverage_prove as pcp

# What pytest 8 actually printed on macOS: the tb=line row carries the exception, the
# summary row lost it to width truncation. Captured from the live run, not composed.
_TRUNCATED_DIVERGENCE = """\
                   [100%]
=================================== FAILURES ===================================
E   AssertionError: expected 10% discount applied to total, got 1100.0
    assert 1100.0 == 900.0
/var/folders/qr/T/l1-pyproof-x/test_l1_coverage_proof.py:4: AssertionError: expected 10% discount applied to total, got 1100.0
=========================== short test summary info ============================
FAILED ../../../var/folders/qr/T/l1-pyproof-x/test_l1_coverage_proof.py::proof_0
1 failed in 0.00s
"""

_TRUNCATED_INCIDENTAL = """\
                   [100%]
=================================== FAILURES ===================================
/var/folders/qr/T/l1-pyproof-x/test_l1_coverage_proof.py:2: TypeError: unsupported operand
=========================== short test summary info ============================
FAILED ../../../var/folders/qr/T/l1-pyproof-x/test_l1_coverage_proof.py::proof_0
1 failed in 0.00s
"""


def test_a_fired_assertion_is_a_divergence_when_the_summary_is_truncated():
    assert pcp._classify(_TRUNCATED_DIVERGENCE, 1) == "divergence"


def test_a_setup_exception_is_still_incidental_when_the_summary_is_truncated():
    """The half that keeps the fix honest: a TypeError in the arrange step is noise, and
    reading every truncated failure as a divergence would fabricate proofs from typos."""
    assert pcp._classify(_TRUNCATED_INCIDENTAL, 1) == "incidental"


def test_the_untruncated_summary_still_classifies():
    out = "FAILED test_l1_coverage_proof.py::proof_0 - AssertionError: expected 900\n1 failed\n"
    assert pcp._classify(out, 1) == "divergence"
    out2 = "FAILED test_l1_coverage_proof.py::proof_0 - TypeError: bad operand\n1 failed\n"
    assert pcp._classify(out2, 1) == "incidental"


def test_another_files_traceback_cannot_claim_the_verdict():
    """Anchored to the proof file's own name. A conftest that raises AssertionError while
    the proof errors on import must not read as a proven divergence."""
    out = ("/repo/conftest.py:9: AssertionError: fixture broke\n"
           "ERROR ../../t/test_l1_coverage_proof.py::proof_0\n1 error in 0.01s\n")
    assert pcp._classify(out, 1) == "incidental"


def test_a_passing_run_is_still_a_pass():
    assert pcp._classify(".\n1 passed in 0.01s\n", 0) == "pass"


def test_a_namespace_package_module_gets_its_full_dotted_path(tmp_path):
    """The second fault the planted control found. `_import_path` walks up while
    `__init__.py` exists, and a PEP 420 namespace package has none, so `planted/pricing.py`
    resolved to `pricing`. The model was then told a module name that does not import: its
    correct proposals failed on ModuleNotFoundError, were binned incidental, and the repair
    loop took over from there."""
    pkg = tmp_path / "planted"
    pkg.mkdir()
    (pkg / "pricing.py").write_text("def f():\n    return 1\n")
    assert pcp._import_path(tmp_path, pkg / "pricing.py") == "planted.pricing"


def test_a_classic_src_layout_still_resolves_to_the_installed_name(tmp_path):
    src = tmp_path / "src" / "mypkg" / "sub"
    src.mkdir(parents=True)
    (tmp_path / "src" / "mypkg" / "__init__.py").write_text("")
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text("")
    assert pcp._import_path(tmp_path, src / "mod.py") == "mypkg.sub.mod"


def test_a_repo_root_module_is_just_its_stem(tmp_path):
    (tmp_path / "single.py").write_text("")
    assert pcp._import_path(tmp_path, tmp_path / "single.py") == "single"
