Feature: budget — how much the next unit of work may spend
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  One rule, and it was two spellings: live_sweep wrote it as a min and the module sweeps
  wrote it as a slice. The package's duplicate-rule guard compares parse trees and cannot
  see through that, and it was still two places for a budget to drift. This budget decides
  how much money a run spends.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # An allowance is a count of ATTEMPTS, and an attempt is not a fixed cost. One gap may take a
  # single model call or four, depending on how many repair rounds it needs, and a call's price
  # depends on how much source the prompt carried. Nothing here can convert an allowance into
  # money, so a ceiling bounds the number of tries and not the bill.
  @undecidable @not-implemented
  Scenario: undecidable what an allowance costs in money
    Given a ceiling expressed as a number of attempts
    When a run spends it
    Then the number of attempts is bounded exactly
    And the price of each is not, since a repair round is another call and a call is priced by its payload
    But nothing here reads a price, so an operator authorising a ceiling is authorising tries rather than a sum

  Scenario: allowance offers the smaller of the two bounds
    Given a unit's own cap, the ceiling for the whole run, and what the run has spent
    When allowance compares them
    Then it returns the smaller, so neither bound can be exceeded
    And it never returns a negative number, so a run already over its ceiling offers nothing rather than borrowing
    But both bounds are needed and answer different questions: the cap stops one large unit consuming everything, and the ceiling is what an operator authorises
