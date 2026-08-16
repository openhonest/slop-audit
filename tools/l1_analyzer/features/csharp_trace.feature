Feature: csharp_trace — the L1.19 and L1.20 runtime harness for C# repositories
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today a project that targets several frameworks runs its suite once per
  # framework, each writing its report into its own run directory, and the first path in sort
  # order is read; the frameworks compile different conditional regions, so a run identifier
  # rather than the code decides which branch counts get published.
  @undecidable @not-implemented
  Scenario: undecidable a project that targets several frameworks in one run
    Given a test project naming more than one target framework, whose conditional compilation directives include different code in each, so the run wrote one report per framework
    When decision_space_coverage sorts the reports it found and reads the branch counts out of the first
    Then it is recorded as unread rather than scored from whichever framework's report sorted first, so a percentage means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _dotnet finds the SDK command the measurement would run under
    Given the executable search path of the machine running the audit
    When _dotnet looks for the dotnet command
    Then it returns it when it is installed
    But it returns nothing otherwise, and both measurements then return an explicit not-applicable naming the missing SDK, never a zero

  Scenario: _sdk names the SDK version that measured the repository
    Given the dotnet command, the repository, and a timeout
    When _sdk asks dotnet for its version from inside the repository
    Then it returns that version prefixed with the word dotnet, so the result says which environment measured it
    And the probe runs inside the repository, so the repository's own SDK pin selects the version rather than whatever launched the analyzer
    But a probe that fails or times out yields the phrase "an unknown dotnet SDK", because naming the SDK is never the measurement

  Scenario: decision_space_coverage measures C# branch coverage from a Cobertura report
    Given a repository, a timeout, and a runtime override that C# ignores because the repository selects its own SDK
    When decision_space_coverage runs the test suite with the cross-platform coverage collector and reads the branch counts out of the report it wrote
    Then it returns covered branches over valid branches as a percentage, Healthy above 90, Not Healthy from 60 to 90, and Slop below 60, naming the SDK and whether the suite passed
    And it reads the first report it finds when several projects each wrote one, so a multi-project repository is scored on one project's branches
    But a missing SDK, a suite that timed out, a report that was never written because the collector is not referenced, a report carrying no branch counts, and a report where nothing had a branch to cover each return an explicit not-applicable with its remedy, never a zero that would read as real but terrible coverage

  Scenario: _ran_tests tells a real determinism data point from a suite that never executed
    Given the combined output of one test run
    When _ran_tests looks for the banners the test runner prints only when it executed a suite
    Then it answers yes when any of them is present
    But a build error, or a project with no discovered tests, prints none of them and it answers no, which is what stops a suite that never ran from being scored as failing

  Scenario: test_determinism counts the repeated runs where the whole C# suite passes
    Given a repository, a number of runs, a timeout, and a runtime override the repository ignores
    When test_determinism runs the suite that many times and counts the runs that passed
    Then it returns the count of clean runs out of the total, Healthy only when every run passed, Not Healthy when exactly one failed, and Slop below that
    And the detail says the order was varied by the scheduler rather than controlled by a seed, because the runner takes no seed, and it quotes the first line of up to three failing runs
    But a missing SDK, a run that timed out, and any run where the suite did not actually execute each return an explicit not-applicable with its reason rather than a misleading count of zero
