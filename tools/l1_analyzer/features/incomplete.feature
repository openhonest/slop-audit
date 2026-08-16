Feature: incomplete — INCOMPLETE CODE, the one way a measure may have no answer
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: refuse builds the refusal for a measure that has no basis to answer
    Given a measure name and the basis it lacked
    When refuse is called
    Then it returns an IncompleteCode carrying both, its message opening "INCOMPLETE CODE: "
    But it does not raise, so the raise stays written at the site where it happens

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. This module is the mechanism the other thirty-seven use to say it, so its
  # own undecidable case is the one it cannot say: it distinguishes a zero denominator from a
  # counted zero, and nothing else. A measure whose rule table never had a row for the construct
  # counts nothing, reaches a non-zero denominator by counting other things, and passes here.
  @undecidable @not-implemented
  Scenario: undecidable a rule table that never had a row for the construct it met
    Given a measure whose denominator is non-zero because other constructs were counted, while the one in front of it matches no rule
    When ratio is called with that denominator
    Then the construct is recorded as unread rather than absent from the count, so a rate means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: ratio returns a percentage, or refuses when nothing was counted
    Given a numerator and a denominator
    When ratio is called
    Then it returns the numerator over the denominator as a percentage
    But a denominator of zero raises IncompleteCode instead, because zero over zero is the absence of a measurement and not zero percent
