"""The C runtime harness (L1.19 best-effort gcov/lcov line coverage, L1.20 honest n/a - C has
no standard test-order randomizer).

Only the pure Makefile probe is tested here: a real Makefile on disk read by the real
_make_target. No stub, no monkeypatch.

decision_space_coverage and test_determinism are proved by nothing. Their old tests replaced
_cc, _lcov and _run_untrusted with a fake that answered `cc --version`, `make` and `lcov
--summary` from strings the test author wrote, so the lcov summary parser was proved against
its own input. Proving them needs a real cc, make and lcov and a real C project fixture.
"""

from l1_analyzer import c_trace


def test_make_target_detects_test_and_check(tmp_path):
    (tmp_path / "Makefile").write_text("all:\n\tgcc -o app main.c\ncheck:\n\t./t\n")
    assert c_trace._make_target(tmp_path) == "check"
    (tmp_path / "Makefile").write_text("all:\n\tgcc -o app main.c\n")
    assert c_trace._make_target(tmp_path) is None
    (tmp_path / "Makefile").unlink()
    assert c_trace._make_target(tmp_path) is None
