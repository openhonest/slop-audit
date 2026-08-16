Feature: cli — the command that runs the audit and the gate that runs it on this repository
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _count_type_escapes counts this repository's own type-escape hatches
    Given a repository and the language it is written in
    When _count_type_escapes parses the production source and counts the escape hatches the L1.15 vocabulary names
    Then it returns the raw number, so the gate can ratchet on a count rather than on a density that moves with file size
    And the vocabulary travels with the language configuration, so the gate cannot count by an older rule than the indicator it enforces
    But a language with no configuration, or one whose configuration names no escape patterns, yields zero without reading anything, and that zero is indistinguishable from a repository with no escapes

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

  Scenario: _run_gate runs the audit against this repository and blocks the commit if it flags its own code
    Given the repository, its language, and the optional type-escape and thread-safety baselines
    When _run_gate computes the source indicators and checks the bright lines: no production god-file, no promiscuous state, and neither ratchet exceeded
    Then it prints every problem it found with the remedy and exits non-zero
    And on a clean run it prints a pass line that reports what it CHECKED rather than a property inferred from an empty count: "finitely testable" only when the classifier reached a verdict, and otherwise "no proven unbounded state, but the state classifier reached no verdict", naming how many declarations it had no rule for
    And the thread-safety half of that line says "thread-safety surface not measured" when the meter read no source, and a count against the baseline only when it read some, so the downward arm never demands the baseline be lowered on a reading that never happened
    But the same pass line always opens with "0 production god-files", which is asserted whether or not the indicator read any production source at all

  Scenario: _hazard_context assembles the only code the generator gets to see
    Given the repository and one located hazard naming a file, a line, a kind and a symbol
    When _hazard_context reads the file and cuts a window of thirty lines either side of the hazard
    Then it returns that window under a heading naming the hazard, and nothing else from the repository
    But a file it cannot read yields the heading alone, so generation is attempted on a weaker context rather than abandoned

  Scenario: _run_prove drives locate, generate, run and retain across the review-tier hazards
    Given the repository, its language, the thread-surface result, a cap on hazards, and a timeout
    When _run_prove takes the review-tier findings up to the cap and proves each one in its own throwaway directory
    Then it returns every outcome with its verdict, its detail, and the generated test kept alongside, so a demonstrated proof can be offered as an adoptable test
    And a language other than Rust, or a missing model key, returns not-applicable with the reason and attempts nothing
    But the summary verdict is only "demonstrated" or "none", so a sweep where nothing was generated and nothing was run reads the same at that line as a sweep that ran and fired no race; the per-hazard verdicts are where the two stay distinguishable

  Scenario: main parses the command line and dispatches the requested audit
    Given the arguments the operator typed
    When main validates the repository path, then either runs the gate or collects the git, config and source indicators plus any opt-in runtime stage
    Then it prints the scorecard, or the JSON envelope recording whether the additive state-bounds classifier was on, and returns zero
    And a path that does not exist, and a path that is a file rather than a repository root, each print a plain message and return two rather than crashing inside the coverage runner
    But the stages that generate and run code — the race run and the two prove modes — happen only when explicitly asked for, never by default
