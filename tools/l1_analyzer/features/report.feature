Feature: report — the published grade, the verifiability verdict, and the evidence that can withhold both
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _meter_ran decides whether the state meter produced a reading at all
    Given whatever the finite-testability meter left behind for this repository
    When _meter_ran looks for a numeric resolvable fraction inside it
    Then it reports that the meter ran only when that fraction is a real number
    But anything else, including a missing result or a result of the wrong shape, reports that the meter did not run, and the report then has no source to grade from

  Scenario: silence_fraction gives the share of state the analyzer could not decide
    Given the verdict counts for one repository
    When silence_fraction divides the undecided count by the total of all counts
    Then it returns that share as a fraction between nothing and one
    And it works from the same counts the verdict works from, so the number that suppresses a grade and the number that sets one can never disagree about the same repository
    But a repository with no counts at all comes back as no silence, which is why an empty reading cannot be caught by this measure and needs the independent census instead

  Scenario: census_unread decides whether the reading ever started
    Given the independent census of declarations, counted straight from the parse tree
    When census_unread compares what the repository declares against what the classifier's rules can reach
    Then it reports unread only when the parser found declarations, none of them of a kind any rule can match, and the classifier produced no finding whatever
    And the denominator is the declarations whose kind a rule is capable of matching, not every declaration, so a codebase whose state a rule read and declined on the merits is not refused a grade
    But a census that carries no capability answer reads here as not counted rather than as a capability, so a missing measurement can never be mistaken for a passing one

  Scenario: unread_kinds_phrase names the declaration kinds no rule can reach
    Given the census for one repository
    When unread_kinds_phrase reads the recorded unread kinds and asks for them in prose
    Then it returns a readable phrase naming those kinds, for the sentence that tells a reader why no grade was issued
    And the kinds are read from the census rather than worked out again, so the sentence and the count that withheld the grade come from one measurement
    But a census with no kinds recorded says plainly that the kind was not recorded, rather than returning an empty phrase that would leave the sentence dangling

  Scenario: _basis names what evidence the report actually has
    Given the meter's band, the verdict counts, whether the meter ran, and the census
    When _basis works through its four cases in order
    Then a meter that did not run is no source, a repository nothing could read is unread, a repository with any proof of unbounded state is measured, a repository over the silence floor is silent, and anything else is measured
    And the proof is consulted before the silence floor on purpose, because one state that provably reaches an unbounded decision stands however much of the rest went unread, so obscurity must not be allowed to erase a bad grade any more than to buy a good one
    But the census case and the proof case can never both apply, because a repository with any finding at all is never counted as unread

  Scenario: _status turns the evidence into the verifiability verdict a reader sees
    Given the basis, the verdict counts, and whether any state came back coarse
    When _status decides the verdict
    Then only a measured basis gets a verdict at all, and every other basis is not-applicable
    And a repository with any promiscuous state cannot be verified, a repository with coarse state can be verified only coarsely, and everything else can be verified
    But undecided state no longer affects this verdict, because one call the analyzer could not read used to cap a whole repository, which reported a limit of ours as a defect in theirs; it is published as the silence index instead

  Scenario: _hygiene averages the audit checks by how much each one weighs
    Given the full set of indicator results
    When _hygiene scores each weighted check by its band, at full marks for Healthy, half for Not Healthy and none for Slop
    Then it returns the weighted average between nothing and one, with the god-file and type-escape checks weighing most
    And a check whose band is missing or unrecognized is left out of both halves of the average rather than scored as zero
    But when not one weighted check produced a band, it returns no number at all, and the grade rule downstream treats that absence generously

  Scenario: _grade turns the verdict and the hygiene score into a single letter
    Given the verifiability verdict, the finitely-testable share and the hygiene score
    When _grade applies the published rule
    Then a verdict of cannot is F, a verdict of coarse is D, and a good verdict is A, B or C according to the hygiene score against its two thresholds
    And no verdict at all, or no testable share, means no letter is issued
    But a good verdict with no hygiene score at all is graded A, so a repository on which every weighted check failed to produce a band receives the top letter rather than none

  Scenario: coarse_states lists the state whose reaching partition is too wide to cover
    Given the meter's findings and the width bound to judge them against
    When coarse_states keeps the neutral findings whose partition is finite, unordered, drives a decision, and is wider than the bound, then sorts them widest first
    Then it returns those findings, which are the evidence behind a coarse verdict
    And a finding whose count could not be recovered is left out, because an unknown count is a limit of ours rather than a fact about their code
    But the bound ships unset, and an unset bound is an explicit case here rather than a default filled in out of sight: it returns nothing, D is switched off, and no state is coarse, which is a different statement from every state being fine

  Scenario: grade_summary computes the whole published grade in one place
    Given every indicator result and the width bound the publisher chose
    When grade_summary assembles the basis, the verdict, the coarse states, the hygiene score and the letter
    Then it returns the verdict, the basis for it, the counts, the finitely-testable share, the hygiene score, the letter, the silence index, the census and the coarse states, as the single source both the command-line report and the web card read
    And the testable share is taken over decided state alone, so undecided state is not held against the grade through a second door after being dropped from the verdict
    But the bound ships unset, so as the module stands no repository can ever be judged coarse and the letter D is never issued
