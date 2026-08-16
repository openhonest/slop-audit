"""The Go runtime harness (L1.19 statement coverage, L1.20 shuffle determinism).

Only the pure output predicate is tested here: real `go test` output lines in, verdict out.
No fixture, no stub, no monkeypatch.

decision_space_coverage and test_determinism are proved by nothing. Their old tests replaced
_go and _run_untrusted with a fake that both answered `go version` and wrote the coverage
profile the module then read back, so the total parser was proved against the test's own
string. Proving them needs a real Go toolchain and a real module fixture.
"""

from l1_analyzer import go_trace


def test_ran_tests_detects_execution():
    assert go_trace._ran_tests("ok  pkg 0.1s")
    assert go_trace._ran_tests("--- FAIL: TestX")
    assert not go_trace._ran_tests("build failed: cannot find package")
