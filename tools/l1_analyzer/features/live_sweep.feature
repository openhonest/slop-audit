Feature: live_sweep — the one boundary that spends money, and what it owes a reader
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  This is the only part of the prove loop no test can cover, because the thing under test
  is a model answering. Everything around it is covered by injection. So the module is
  built to make the spending legible rather than convenient: the key comes from a named
  file, the ceiling bounds the run and not each repository, and every repository offered
  appears in the result including the ones that refused.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A model reply that compiles, runs and fails is retained as a proven divergence. Whether the
  # divergence is a real bug or an assertion the model got wrong is not decidable here: both
  # spellings produce a failing test. The execution gate proves only that the code and the
  # asserted behaviour disagree, never which of the two is at fault.
  @undecidable @not-implemented
  Scenario: undecidable whether a retained proof found a bug or asserted the wrong thing
    Given a generated test that compiles, runs, and fails
    When the sweep retains it as a divergence
    Then nothing here can say whether the code is wrong or the assertion is
    And the retained test is offered as a proof request for a person to judge, never adopted
    But the count of retained proofs is not a count of bugs, and no report may spell it as one

  Scenario: _value strips the shell quoting off one KEY=VALUE line
    Given a line from an environment file
    When _value takes what follows the first equals sign
    Then it returns that value with any surrounding single or double quotes removed
    But a key that kept its quote marks would fail at the API as an authentication error, which sends a reader to the account rather than to the file

  Scenario: key_from reads the Anthropic key off a named file
    Given the path to an environment file
    When key_from looks for the key
    Then it returns the value when the file carries one
    But it returns nothing when the file has no such line or cannot be read, and never falls through to the ambient environment, so a run can always say which file paid for it

  Scenario: share decides how many attempts the next repository may make
    Given the run ceiling, the per-repository cap and what the run has already spent
    When share compares them
    Then it returns the smaller of the repository's cap and what the run has left
    But it never returns a negative number, so a spent run offers nothing rather than borrowing

  Scenario: language_of decides which sweep a repository gets
    Given a repository directory
    When language_of looks for a Cargo.toml or a Python project file
    Then it names rust or python
    But it names nothing when neither is present, which is reported as an outcome rather than dropped

  Scenario: sweep runs the coverage proof over several repositories under one budget
    Given a list of repositories, a key, a run ceiling and a per-repository cap
    When sweep works through them in order
    Then every repository offered appears in the result with what it attempted and retained
    And a repository that refused for a missing toolchain, an unrecognised language or an exhausted ceiling appears saying which
    But with no key nothing is swept at all, because a run whose cost nobody authorised must not start

  Scenario: fair_share divides the run ceiling so every repository gets a turn
    Given the run ceiling and how many repositories are being swept
    When fair_share divides one by the other, rounding up
    Then each repository is offered a share rather than the first taking the whole budget
    But the run ceiling still binds the total, so rounding up cannot overspend it

