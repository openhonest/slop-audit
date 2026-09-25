Feature: environment — what a stranger's test suite is allowed to see of this machine
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a
  # verdict. Here the unread construct is a name this list has never been shown: a toolchain
  # nobody on this machine has installed reads a variable nobody here has named, and the run
  # that discovers it is somebody's audit failing for a reason the output calls the project's.
  # Nothing collects those names today, and the honest answer is that the list is as complete
  # as the nine toolchains we have run it against and no more.
  @undecidable @not-implemented
  Scenario: undecidable a toolchain that needs a name this list has never been shown
    Given a repository whose build reads an environment variable no harness here has met
    When child_environment withholds it because nothing named it
    Then the run fails inside the audited project's own toolchain, and the failure reads as that project's
    And nothing records which withheld name the toolchain wanted, because nothing watches the child's reads
    But the list is offered as measured against nine toolchains rather than as complete, and the module says so

  Scenario: child_environment hands one untrusted run the names it is allowed to see
    Given the machine's own environment and whatever settings the caller pins for this run
    When child_environment keeps the allowed names and lays the caller's own over them
    Then a name outside the list never reaches the audited code, which is the leak this closes
    And the caller's own setting wins, because naming one is a deliberate act for one run rather than every secret leaking by default
    But both arguments are required, since a default parent would read the process environment inside the function that decides what escapes it

  Scenario: withheld names what this machine kept back without printing any of it
    Given the machine's own environment
    When withheld lists every name the allowlist does not carry
    Then a run can say how much it kept back without saying what it kept back
    And a person can check the answer against their own shell rather than against this source
    But nothing decides anything on it, so a wrong answer here misleads a reader and changes no measurement
