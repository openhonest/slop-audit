Feature: go_trace — the L1.19 and L1.20 runtime harness for Go modules
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _go finds the Go toolchain the measurement would run under
    Given the executable search path of the machine running the audit
    When _go looks for the go command
    Then it returns it when it is installed
    But it returns nothing otherwise, and both measurements then return an explicit not-applicable naming the missing toolchain, never a zero

  Scenario: _toolchain names the toolchain that measured the module
    Given the go command, the module directory, and a timeout
    When _toolchain asks go for its version from inside the module
    Then it returns the first line of the answer, so the result says which toolchain read the code
    And the probe runs inside the module, so the module's own toolchain directive selects the version rather than whatever launched the analyzer
    But a probe that fails or times out yields the phrase "an unknown go toolchain", because naming the toolchain is never the measurement

  Scenario: decision_space_coverage measures Go statement coverage from a coverage profile
    Given a module, a timeout, and a runtime override that Go ignores because the module selects its own toolchain
    When decision_space_coverage runs the whole test suite writing a coverage profile, then totals it with the cover tool
    Then it returns the statement-coverage percentage with Healthy above 90, Not Healthy from 60 to 90, and Slop below 60, and names the toolchain and whether the suite passed
    And a suite that ran but failed still yields a coverage number, because the profile is written for every package that built and ran
    But a missing toolchain, a suite that timed out, a profile that was never written or is empty, and a profile carrying no statement total each return an explicit not-applicable with its reason, never a zero that would read as real but terrible coverage

  Scenario: _ran_tests tells a real determinism data point from a suite that never executed
    Given the combined output of one test run
    When _ran_tests looks for the banners go prints when a package actually built and ran
    Then it answers yes when any of them is present
    But a build error, or a module with no test files, prints none of them and it answers no, which is what stops a suite that never ran from being scored as failing

  Scenario: test_determinism counts the shuffled-order runs where the whole module passes
    Given a module, a number of runs, a timeout, and a runtime override the module ignores
    When test_determinism runs the suite once per run with a distinct shuffle seed and no result cache
    Then it returns the count of clean runs out of the total, Healthy only when every run passed, Not Healthy when exactly one failed, and Slop below that
    And the detail names the toolchain and quotes the first line of up to three failing runs, so a flake can be chased
    But a missing toolchain, a run that timed out, and any run where the suite did not actually execute each return an explicit not-applicable with its reason rather than a misleading count of zero
