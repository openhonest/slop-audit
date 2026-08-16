Feature: rust_trace — running a Rust crate's own test suite to measure coverage and determinism
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _cargo finds the Rust build tool
    Given whatever is on the search path
    When _cargo looks for cargo
    Then it returns the path to it
    But nothing at all comes back when Rust is not installed, and every measuring function in this module checks that first and reports not-applicable instead of measuring

  Scenario: _toolchain names the Rust compiler that measured the result
    Given a repository and a time limit
    When _toolchain runs the compiler's version probe from inside that repository, so the repository's own pinned toolchain answers
    Then it returns the version line, which is then quoted in the detail of every measured result
    But a missing build tool, a failed probe or an unreadable answer returns the words "an unknown rust toolchain", so the result still says something honest about where it came from rather than naming a toolchain that never ran

  # The docstrings of this module claim the audit is directory-insensitive, and every other
  # probe honours that by running from inside the target repository. This one does not: it
  # runs the version check from whatever directory the analyzer was launched in.
  Scenario: _llvm_cov_available checks that the coverage plugin can run
    Given whatever is installed alongside the Rust build tool
    When _llvm_cov_available runs the coverage plugin's version probe under a thirty-second limit
    Then it reports available only when that probe exits cleanly
    And a missing build tool short-circuits it to unavailable without running anything
    But it runs the probe from the analyzer's own working directory rather than from the repository being audited, so a repository that pins a different toolchain is not the one asked

  Scenario: _tests_run totals the tests the crate's suite reported
    Given the combined output of one build-tool test run
    When _tests_run reads every test-result summary line in it
    Then it returns the total number of tests, counting passed, failed and ignored together, and separately the number that failed
    And several summary lines are summed, because a crate reports one per test binary
    But a total of zero means the suite collected no tests at all, which the caller treats as a reason to refuse a measurement

  Scenario: _llvm_cov_report runs one instrumented coverage build and parses its output
    Given a repository and a time limit
    When _llvm_cov_report builds and runs the crate under coverage instrumentation, writing a report to a temporary file
    Then it returns the parsed report, whose file table carries every file's coverage from that one expensive build
    And a whole-repository sweep therefore pays for the instrumented build only once
    But a missing build tool, a missing coverage plugin, a timed-out run, a report that was never written or a report that will not parse returns no report at all together with the specific reason, which the caller must pass on rather than treat as zero coverage

  Scenario: _uncovered_lines picks the never-executed decision points out of one file's coverage entry
    Given one file's entry from the coverage report
    When _uncovered_lines reads the coverage segments in it
    Then it returns the line numbers of every segment that starts a region, carries a real count, and whose count is zero
    And the line numbers are one-based, matching the source as a reader sees it
    But a segment with no real count attached is not evidence of anything and is left out, so an unexecuted line and an unmeasured one are never merged

  Scenario: module_uncovered_lines reports the uncovered lines of one module inside its crate
    Given a repository, the path of one module relative to it, and a time limit
    When module_uncovered_lines runs the coverage build and looks that module up in the report's file table
    Then it returns the module's uncovered line numbers and says the measurement was taken
    And measuring the module inside its own crate is what makes the answer usable for a module that is deeply wired into the rest of the code
    But a missing build tool, a missing coverage plugin, a report with no file table, or a module that does not appear in the report returns an explicit not-measured together with the reason, and an empty line set that no caller may read as full coverage

  Scenario: repo_uncovered_lines reports the uncovered lines of every file from a single build
    Given a repository and a time limit
    When repo_uncovered_lines runs one coverage build and walks the whole file table
    Then it returns a map from each file's repository-relative path to its uncovered line numbers, and says the measurement was taken
    And only files that sit inside the repository and have at least one uncovered line appear, so dependencies compiled from elsewhere are left out
    But a missing build tool, a missing coverage plugin, a timed-out run or a report it cannot walk returns an explicit not-measured with the reason and an empty map

  Scenario: decision_space_coverage measures the share of code regions the crate's tests reach
    Given a repository and a time limit
    When decision_space_coverage runs the instrumented build and reads the report's region totals
    Then it returns the covered share of regions as a percentage, banded Healthy above 90, Not Healthy from 60 to 90, and Slop below 60
    And the detail line says the figure is region coverage rather than true branch coverage, and names the toolchain that produced it, because region coverage is the closest honest proxy available on a stable toolchain
    But a missing build tool, a missing coverage plugin, missing coverage tools inside that plugin, a timed-out suite, a report that was never written or will not parse, a report with no region totals, or a region count of zero all return not-applicable with the reason, never a zero percentage

  Scenario: test_determinism counts how many repeated test runs pass cleanly
    Given a repository, how many runs to make and a time limit
    When test_determinism runs the crate's test suite that many times, relying on the test harness scheduling tests across threads to vary the order between runs
    Then it returns the passing count over the run count, banded Healthy when every run passes, Not Healthy at one short, and Slop below that
    And a missing build tool returns not-applicable before any run is attempted, and a timed-out run returns not-applicable naming the run that hung
    But only the first run is checked for having collected any tests, so a build that starts failing on a later run is counted as a failing run rather than reported as a suite that never executed
