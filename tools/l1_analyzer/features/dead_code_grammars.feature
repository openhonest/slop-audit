Feature: dead_code_grammars — the grammars this reader parses with, and the extension that picks one
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: parser builds one parser per grammar and keeps it for the rest of the run
    Given the name of one of the ten grammars this module parses
    When parser is asked for that grammar's parser
    Then it builds the parser on first use and returns the same one on every later call
    And the cache is held by the caching decorator rather than by a dictionary a function writes into, because this package's own external-state indicator counts a written module global as hidden state and caught the dictionary version of exactly this
    But a name that is not one of the ten raises rather than returning a default parser


  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built.
  @undecidable @not-implemented
  Scenario: undecidable a file extension this table has no entry for
    Given a source file whose suffix is in none of the nine languages this table names
    When a caller asks the table which grammar to parse it with
    Then it gets nothing back, and the caller says the file was not parsed rather than reporting a reading of it
    And the unmatched suffix is offered for collection: the extension alone, with no path and no content
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
