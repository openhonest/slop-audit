Feature: honest_code_grammars — the grammars an embedded block is parsed with
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _grammars states which grammars this reader loaded
    Given the two languages no clause reads, markup and stylesheets
    When _grammars loads them once at import
    Then a caller asks the table what is present instead of parsing to find out
    But a grammar that failed to install is a missing key, not a rejection that reads like prose


  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built.
  @undecidable @not-implemented
  Scenario: undecidable a language named by a caller that this table has no grammar for
    Given a caller asking for a grammar by a language name
    When the table has no entry under that name
    Then the lookup raises rather than returning nothing, because a reader handed nothing would report a file it never parsed as a file with no embedded source
    And the name asked for is offered for collection: the language name alone, with no path and no content
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
