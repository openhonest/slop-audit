Feature: java_trace — running a Maven project's own test suite to measure branch coverage and determinism
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the coverage report is looked for at one path under the repository
  # root, so a build whose modules each write their own report, and whose root writes one only
  # when an aggregate goal is configured, is reported as a build carrying no coverage plugin.
  @undecidable @not-implemented
  Scenario: undecidable a multi-module build whose coverage reports are written one per module
    Given a project whose build file declares modules, each writing its own coverage report under its own build directory and none at the repository root
    When decision_space_coverage runs the build and looks only for the report at the root's own coverage path
    Then it is recorded as unread rather than reported as a build with the coverage plugin missing, so a not-applicable names what was not read and never a plugin the build already carries
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _maven picks the build command this project should be driven with
    Given a repository directory
    When _maven looks for the project's own build wrapper and then for a system build tool
    Then it returns the wrapper in the repository when there is one, because the wrapper pins the build version the project expects
    And it falls back to whatever build tool is on the search path
    But nothing at all comes back when neither exists, and the callers turn that into a stated reason rather than attempting a build

  Scenario: _unsupported_reason says exactly why this project cannot be measured here
    Given a repository directory
    When _unsupported_reason checks what kind of build the project has and whether a build tool is available
    Then it returns nothing when the project can be measured
    And a project with no Maven build file is told either that Gradle is not yet supported by this harness, when it has a Gradle build, or that a Maven build is needed
    But a Maven project with no build tool anywhere returns the specific reason naming both ways to supply one, so a missing toolchain is always an explicit not-applicable and never a failed build reported as a bad score

  Scenario: _pin_jdk pins the Java runtime a version manager chose for this project
    Given a repository and a time limit
    When _pin_jdk asks the installed version managers which Java this directory resolves to
    Then it returns the environment settings that point the build at that runtime, together with a note naming the manager that chose it
    And pinning it this way is what stops a different Java sitting earlier on the search path from silently winning over the one the project pinned
    But when no version manager is installed or none resolves Java, it returns no settings and no note, and the build runs under whatever Java is ambient

  Scenario: _jdk names the Java runtime that measured the result
    Given a repository, a time limit and the environment settings the pinning step produced
    When _jdk runs the runtime's version probe from inside the repository
    Then it returns the version line, read from the error stream because that is where the probe prints it
    But a probe that fails or finds no Java returns the words "an unknown JDK", so the result still says honestly where it came from rather than naming a runtime that never ran

  Scenario: _branch_totals reads the project-wide branch counts out of the coverage report
    Given the text of a coverage report
    When _branch_totals looks for the report-level branch counter
    Then it returns the covered and missed branch counts, taken from the grand total across every package so no level is counted twice
    But a report carrying no branch counter yields zero and zero, which the caller treats as a project with no branches rather than as a project with none covered

  Scenario: _coverage_verdict decides L1.19 from a finished build and the report's branch counts
    Given the covered and missed branch counts the coverage report carried, or the fact that no report was written at all, together with the build's exit status and the name of the Java runtime that ran it
    When _coverage_verdict reads them
    Then a build that finished yields the covered share of branches as a percentage, banded Healthy above 90, Not Healthy from 60 to 90 and Slop below 60, with the detail naming the counts, whether the suite passed and the runtime
    And a build that ran out of time says so, and a build that wrote no coverage report says the coverage plugin is missing from the build rather than reporting nothing covered
    But a report whose branch counts add to nothing is not-applicable, never a percentage, because a share of no branches is absent and not zero

  Scenario: decision_space_coverage measures the share of decision branches the suite exercises
    Given a repository, a time limit and a runtime override
    When decision_space_coverage runs the project's tests with coverage reporting and reads the report the build writes
    Then it returns the covered share of branches as a percentage, banded Healthy above 90, Not Healthy from 60 to 90, and Slop below 60
    And the detail line says these are real branch counts, whether the suite passed, and which Java runtime ran it
    But an unsupported or unbuildable project, a missing build tool, a timed-out suite, a coverage plugin that was never wired into the build, an unreadable report or a project with no branches at all returns not-applicable with the reason, never a zero that would read as real but terrible coverage; and the runtime override is accepted only to keep the harness signature uniform, because the project's own build picks the runtime

  Scenario: _ran_tests tells a real determinism data point from a suite that never executed
    Given the combined output of one build run
    When _ran_tests looks for the test runner's own summary marker
    Then it reports that tests ran only when that marker is present
    But a compilation failure, or a module with no tests, produces no marker and reports that nothing ran, which is the difference between a failing run and a run that never happened

  Scenario: _surefire_summary recovers the counts line from a build run
    Given the combined output of one build run
    When _surefire_summary looks for the test runner's summary lines
    Then it returns the last one, which carries that run's own counts of tests, failures and errors
    But output with no summary line yields a plain note saying so, which keeps a failing run from reaching a reader with no reason attached

  Scenario: _determinism_verdict decides L1.20 from the outcome of every randomized-order run
    Given the exit status and combined output of each randomized-order run, in the order they were made, and the name of the Java runtime that ran them
    When _determinism_verdict reads them
    Then it returns the count of clean runs over the count of runs made, banded Healthy when every run passed, Not Healthy at one short and Slop below that
    And each run that failed is named by its seed with that run's own counts of tests, failures and errors, up to three of them, so a low score arrives carrying its own reason instead of a bare score
    But the first run that ran out of time, and the first run that executed no tests at all, each stop the count and return not-applicable naming that seed, and no runs at all is not-applicable too, because none clean out of none is absent and not a clean sweep

  Scenario: test_determinism counts how many randomized-order runs pass cleanly
    Given a repository, how many runs to make, a time limit and a runtime override
    When test_determinism runs the project's tests that many times with the runner re-randomizing execution order each time
    Then it returns the passing count over the run count, banded Healthy when every run passes, Not Healthy at one short, and Slop below that
    And the runs that had failures are named in the detail line with their counts, up to three of them, so a low score carries its own explanation
    But an unsupported project, a missing build tool, a timed-out run, or any run that executed no tests at all returns not-applicable with the reason rather than a zero score that would read as flakiness; and unlike the other harnesses this one re-checks that tests ran on every run, not only the first

  Scenario: _toolchain resolves this repo's Maven toolchain once, or refuses
    Given a repository and the time budget for probing it
    When _toolchain looks for Maven, pin a JDK and name it with its provenance
    Then it returns a refusal and no tools, or tools and no refusal, so exactly one of the two is ever populated
    And both L1.19 and L1.20 ask it, so the two indicators cannot come to hold different preconditions for the same repo

