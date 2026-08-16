Feature: c_trace — the L1.19 and L1.20 runtime harness for C repositories
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the only build this harness can drive is a makefile carrying a test or
  # check target, and every other build is reported as C having no standard coverage convention,
  # which describes the language rather than the one build system we taught this harness to run.
  @undecidable @not-implemented
  Scenario: undecidable a C build system this harness has no rule for driving
    Given a repository whose tests are built and run by CMake with its test driver, by Meson, or by a configure step that writes the makefile only after it runs
    When decision_space_coverage looks at the repository root for a makefile declaring a test or check target
    Then it is recorded as unread rather than reported as a language with no coverage convention, so a not-applicable names the build we could not drive and never the language
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

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
