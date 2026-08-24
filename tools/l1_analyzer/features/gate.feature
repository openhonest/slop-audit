Feature: The dogfood gate

  What a pre-commit hook calls, rather than what a person calls. Split out of the CLI when
  that module crossed the god-file threshold, at the seam that was already there: everything
  else renders a panel for somebody reading it, and this answers one question for a machine.

  Scenario: _audited_language settles the language the audit actually read
    Given the results of a run, the language that was requested, and the repository
    When _audited_language is asked which language was audited
    Then it returns the language the source pass settled on, whatever was requested
    And it settles an unrequested language the same way the source pass would, when no source pass ran
    But an explicit request with no source pass stands, because that is an instruction and not a guess

  Scenario: _count_type_escapes counts this repository's own type-escape hatches
    Given a repository and the language it is written in
    When _count_type_escapes parses the production source and counts the escape hatches the L1.15 vocabulary names
    Then it returns the raw number, so the gate can ratchet on a count rather than on a density that moves with file size
    And the vocabulary travels with the language configuration, so the gate cannot count by an older rule than the indicator it enforces
    But a language with no configuration, or one whose configuration names no escape patterns, yields zero without reading anything, and that zero is indistinguishable from a repository with no escapes

  Scenario: _run_gate runs the audit against this repository and blocks the commit if it flags its own code
    Given the repository, its language, and the optional type-escape and thread-safety baselines
    When _run_gate computes the source indicators and checks the bright lines: no production god-file, no promiscuous state, and neither ratchet exceeded
    Then it prints every problem it found with the remedy and exits non-zero
    And on a clean run it prints a pass line that reports what it CHECKED rather than a property inferred from an empty count: "finitely testable" only when the classifier reached a verdict, and otherwise "no proven unbounded state, but the state classifier reached no verdict", naming how many declarations it had no rule for
    And the thread-safety half of that line says "thread-safety surface not measured", naming which of the three ways of not reading applied, and a count against the baseline only when the meter did read source, so the downward arm never demands the baseline be lowered on a reading that never happened
    But the same pass line always opens with "0 production god-files", which is asserted whether or not the indicator read any production source at all

  Scenario: _slack fails a ratchet that is looser than the reality it guards
    Given the count actually measured, the baseline the ratchet is set at, and the label to report under
    When _slack compares the two
    Then a baseline above the real count returns one problem naming the gap, the file to lower it in, and how many regressions would otherwise pass unannounced
    But a baseline equal to or below the real count returns no problem, because the upward arm of the ratchet already covers that case

  Scenario: _verdict_of reads a panel entry's verdict across a typing gap
    Given one entry from the results panel, which may be any shape
    When _verdict_of looks for a verdict inside it
    Then it returns that verdict as text when the entry is a mapping that carries one
    And it returns not-applicable for every other shape, so a caller never has to guess
    But it narrows the entry rather than widening the declared type, because either of the easier fixes is a thing this repository's own type-escape ratchet counts against it

  # The reserved case. A ratchet records a number somebody agreed to, and nothing here can
  # read why they agreed to it.
  @undecidable @not-implemented
  Scenario: undecidable whether a baseline was raised for a good reason
    Given a ratchet whose number went up in the hook config
    When someone asks whether the new violation was unavoidable
    Then the answer is in the change that raised it, not in the count
    But this gate reads only the count, and a raised baseline reaches it as agreement
