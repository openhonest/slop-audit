Feature: boundary — declaring where this package meets the world
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Honest Code rule 4 puts I/O at the boundary and pure logic in the middle. L1.21.4 infers
  the boundary from the call graph, because most projects say nothing, and it cannot tell a
  function that is ONLY I/O from business logic that has swallowed a read.

  This is how a function says which it is. The decorator changes nothing at runtime; it is
  a declaration in the source, and the framework's own architecture format spells the same
  fact as a `boundary_in` or `boundary_out` prefix.

  It is not a suppression. A suppression silences a rule over code that still breaks it.
  This is only honest after the decision has been lifted out, so that what remains under the
  decorator obtains data and decides nothing. The split comes first and the declaration
  records that it happened.

  Scenario: boundary marks a function as one of this package's edges
    Given a function that obtains data from the world and decides nothing
    When boundary is applied to it
    Then the function is returned unchanged, because a declaration that altered behaviour would be a wrapper rather than a statement
    But it is only honest once the decision has been lifted out, since a decorator over business logic that reads a file is a suppression wearing a declaration's name

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # Nothing here reads whether the declaration is deserved. A decorator on a function that still
  # decides things looks identical to one on a function that only reads, and separating them
  # needs a reader's judgement about what the body is for.
  @undecidable @not-implemented
  Scenario: undecidable whether a declared boundary earned its declaration
    Given a function carrying the boundary decorator
    When someone asks whether the decision was really lifted out of it
    Then the declaration is recorded and read by the clause
    But nothing here can tell an earned declaration from a stamp, so the split is a discipline rather than a check

  Scenario: text_or_empty hands back one small file's text, or nothing
    Given a path that may or may not exist
    When text_or_empty reads it
    Then the text comes back, and an absent or unreadable file comes back as nothing
    But those two are one answer on purpose, because neither says the thing the caller is asking about
