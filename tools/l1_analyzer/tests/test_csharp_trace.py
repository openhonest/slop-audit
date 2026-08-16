"""The C# runtime harness (L1.19 Cobertura branch coverage, L1.20 repeat-run determinism).

Only the pure output predicate is tested here: real dotnet-test summary lines in, verdict out.
No fixture, no stub, no monkeypatch.

decision_space_coverage and test_determinism are proved by nothing. Their old tests replaced
_dotnet and _run_untrusted with a fake that both answered `dotnet --version` and wrote the
Cobertura report the module then read back, so the parser was proved against the test's own
XML. Proving them needs a real .NET SDK and a real project fixture.
"""

from l1_analyzer import csharp_trace


def test_ran_tests_detects_execution():
    assert csharp_trace._ran_tests("Passed!  - Failed: 0, Total: 5")
    assert csharp_trace._ran_tests("Failed!  - Failed: 2, Total: 5")
    assert not csharp_trace._ran_tests("Build FAILED. error CS0246")
