Feature: prove_gap — how one located gap becomes a retained proof, for both coverage provers
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: prove_one drives one gap from proposal to verdict
    Given a located gap, a way to propose a test for it, a way to render and run one, a way to repair it, the verdict worth repairing, and how many rounds the caller allowed
    When prove_one proposes, runs, and repairs while the verdict is the repairable one
    Then a model that declined is a named outcome and nothing is run, because the call still cost money and a hit rate over calls nobody admits making is not a hit rate
    And the explanation comes back from the proposal that actually ran, since a repaired proposal's verdict beside the first proposal's words describes a test nobody ran
    But repair stops at the rounds the caller allowed, or a model that keeps writing code that will not build spends without a ceiling

  Scenario: prove_each counts every gap in a module and keeps only what fired
    Given the module's gaps, a way to attempt one, a way to build the record a retained proof becomes, and the tally this language names its verdicts in
    When prove_each attempts each gap in turn
    Then only a divergence is retained, because a test that passes against the code as written has proven nothing and keeping it would report a hit rate of one
    And every other outcome is counted rather than dropped, declines included
    But a verdict the caller's tally does not name raises, since a prover and a report that disagree about what can happen is the reading this instrument exists to refuse

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built.
  @undecidable @not-implemented
  Scenario: undecidable a test that fails for a reason nobody can attribute
    Given a generated test that fails while the runner cannot tell a proven divergence from a fixture that blew up on its way in
    When the runner settles on neither and the gap gets a verdict its language's tally has no arm for
    Then the run says the failure could not be attributed, rather than counting it as a proof or discarding it as noise
    And the shape of the unattributed failure is offered for collection: the runner's verdict word and the exit status, with no source and no output
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
