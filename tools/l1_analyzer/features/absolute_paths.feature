Feature: absolute_paths — machine-specific absolute paths in source
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _matches locates every machine-specific absolute path in a file
    Given the text of one source file
    When _matches scans it line by line
    Then it returns the 1-based line number and the matched text of each machine root it finds
    But a path that begins with a root no rule names, such as an API route, yields nothing

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today this module simply does not match, so an absolute path under a root
  # nobody enumerated is indistinguishable from a file containing no path at all.
  @undecidable @not-implemented
  Scenario: undecidable an absolute path under a root no rule names
    Given source carrying an absolute path whose root is in none of the declared unix or windows roots
    When scan reads the file
    Then the path is recorded as unread rather than counted clean, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: scan reports the repository's hardcoded machine paths as a banded finding
    Given a repository and a language name
    When scan reads the production source and collects every match
    Then it returns the count, the band, a detail line naming the files hit, and the findings capped at 50
    And the band is Healthy only at zero, because a hardcoded machine path is never correct
    But the test tree is excluded, since a test proving a path detector fires must contain the path it detects
