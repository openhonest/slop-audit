Feature: toolchain — what ran the measurement, read from the tool's own version banner
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: named reads the toolchain out of a version probe, or says it is unknown
    Given what the probe printed and the code it exited with
    When named reads them
    Then the first line is the toolchain, since a version banner runs to several lines and only the first names it
    And a probe that failed is named unknown rather than the empty string, because the name sits beside the number and a reader uses it to decide whether to believe the reading
    But which stream the tool printed to is the caller's fact, so this takes the text: Java prints its version to standard error and the other six to standard output

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built.
  @undecidable @not-implemented
  Scenario: undecidable a version banner whose first line does not name a version
    Given a tool that exits zero and prints a warning, a licence header or a prompt before its version
    When named takes the first line and that line names no toolchain
    Then the reading says the banner was not recognised rather than quoting a line that tells a reader nothing about what measured their code
    And the shape of the unrecognised banner is offered for collection: its line count and whether a version-like number appeared at all, with no text
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
