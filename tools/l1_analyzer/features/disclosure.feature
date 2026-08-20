Feature: disclosure — the notes a result owes a reader when it did less than it looks like
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Two notes, and they were in two places: one in indicators and one in absolute_paths,
  which is a module about hardcoded paths and no home for a general reporting rule. They
  are the same kind of sentence and share one rule, so they sit together.

  Both are silent when there is nothing to say. A note on every result is one a reader
  learns to skip, which is how the one that mattered would be missed.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # Neither note can tell whether the reader will act on it. A sentence appended to a details
  # line is read by whoever reads details, and a consumer taking the value and the findings
  # list programmatically never sees it. Making the truncation a FIELD rather than prose would
  # settle that, and would change the published result shape for every consumer.
  @undecidable @not-implemented
  Scenario: undecidable whether a disclosure written as prose reaches its reader
    Given a result whose details line names a cut list or an unreadable file
    When a consumer reads the result programmatically
    Then nothing here can say whether the sentence was read or the fields were taken alone
    And a field would settle it, at the cost of changing the published shape for every consumer
    But the note is appended either way, because a disclosure nobody reads is still better than one nobody wrote

  Scenario: with_skipped names the files a scan could not read
    Given a details line and how many files were unreadable
    When with_skipped is asked to disclose them
    Then the count is appended, so a count over a subset is not read as a count over the tree
    But nothing is appended when every file was read

  Scenario: listed_note names a finding list that was cut
    Given how many findings are listed and how many were found
    When listed_note compares them
    Then it names the shorter number, so the list stops disagreeing with the count beside it
    But it says nothing when the cap did not bite, since the only way to notice the disagreement was to compare two fields, which nobody does when one is a list they are iterating
