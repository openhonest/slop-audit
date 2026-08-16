Feature: c_trace — the L1.19 and L1.20 runtime harness for C repositories
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _cc finds the C compiler the measurement would run under
    Given the executable search path of the machine running the audit
    When _cc looks for cc, then gcc, then clang, in that order
    Then it returns the first one it finds
    But it returns nothing when none of the three is installed, and every caller turns that into an explicit not-applicable

  Scenario: _lcov finds the tool that totals the gcov data
    Given the executable search path of the machine running the audit
    When _lcov looks for lcov
    Then it returns it when it is installed
    But it returns nothing otherwise, and coverage is then not applicable with "install lcov" as the remedy, because gcov data nobody totalled is not a coverage number

  Scenario: _compiler names the compiler that measured the repository
    Given a compiler found on the path, the repository, and a timeout
    When _compiler asks that compiler for its version from inside the repository
    Then it returns the first line of the answer, so the result says which toolchain read the code
    And the probe runs against the repository rather than the analyzer's own directory, so the answer does not depend on where the audit was launched
    But a probe that fails or times out yields the phrase "an unknown C compiler" rather than an error, because naming the toolchain is never the measurement

  Scenario: _make_target finds the target that runs the repository's tests
    Given a repository that may carry a makefile under any of its three usual names
    When _make_target reads the first such file it finds and looks for a test target, then a check target
    Then it returns the name of the first one declared
    And it only reads the file, because the harness never edits the target's build
    But a repository with no makefile, an unreadable makefile, or a makefile declaring neither target yields nothing, and coverage is then not applicable

  Scenario: decision_space_coverage measures C line coverage through an instrumented make run
    Given a repository, a timeout, and a runtime override that C ignores because the compiler comes from the path
    When decision_space_coverage builds and runs the makefile's test target with coverage instrumentation, then totals the result with lcov
    Then it returns the line-coverage percentage with Healthy above 90, Not Healthy from 60 to 90, and Slop below 60, saying in the detail that line coverage is the proxy because C has no standard branch-coverage convention
    And it names the compiler, the covered and total line counts, and whether the test target itself passed
    But every failing path returns an explicit not-applicable with its reason — no compiler, no makefile test target, no lcov installed, a build that timed out, a capture that timed out, no gcov data produced, or an instrumented build that touched no instrumented lines — and never a zero that would read as real but terrible coverage

  Scenario: test_determinism declines to measure execution-order determinism for C
    Given a repository, a run count and a timeout that this harness accepts only to match its siblings
    When test_determinism confirms a compiler exists and names it
    Then it returns not applicable, because C has no standard test-order randomizer to shuffle the suite with
    And the reason names the compiler that would have run the suite, so the reader can see the measurement was declined rather than failed
    But a machine with no C compiler returns not applicable for that reason instead, and neither path ever reports a misleading zero out of five
