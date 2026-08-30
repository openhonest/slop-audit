Feature: honest_code_report — what an L1.21 assessment looks like when someone reads it
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Two readers and two shapes. A person reads the per-clause document, with the clauses
  nobody could decide listed apart from the score. An agent mid-edit reads where, which
  clause, and what to do instead, and reads nothing at all when the file is clean.

  Split out of honest_code on 2026-08-30, when that module crossed a thousand lines of
  code and the audit reported it as a god-file. What the clauses ARE is a different
  question from how a result PRINTS.

  Scenario: report writes the per-clause result a person reads
    Given an assessment
    When report renders it
    Then each clause is named with its number, its verdict and its findings
    But the clauses nobody could decide are listed apart from the score, with the reason for each

  Scenario: hook_report writes the one thing an agent needs mid-edit
    Given an assessment of the file just written
    When hook_report renders it
    Then each finding is one line naming the file, the line, the clause and what to do instead
    But nothing else is printed, because a hook that fires on every write has to be read in a glance rather than studied

  Scenario: undecidable whether a principle nobody wrote a clause for is held
    Given a repository this instrument reports a hundred per cent conformity on
    When someone asks whether it holds every Honest Code principle
    Then the report names the two principles no clause measures, above the score rather than inside it
    And it says why each is outside: one mitigates a failure instead of eliminating it, and the other leaves no evidence to read
    But nothing here can decide them, and offering the node types of what it could not read would offer nothing, since neither principle is a construct
