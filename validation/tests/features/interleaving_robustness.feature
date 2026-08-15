Feature: Interleaving robustness (concurrency anti-coverage)
  Cross-reference the static concurrency surface against what a model checker (loom /
  shuttle) actually exercises. Surface no model touches is unmodeled: the interleavings
  its invariants depend on are never forced, so a green suite says nothing about them.
  It reports model presence, not adequacy: "unmodeled" is the confident gap; the
  finding is "force these schedules", never "this races".

  Scenario: Flagged surface with no model anywhere is unmodeled
    Given a Rust file that hand-asserts Sync on a shared struct
    And no loom or shuttle model exists in the repository
    When I run the interleaving-robustness meter
    Then the verdict is unmodeled
    And that file is listed as unmodeled

  Scenario: Flagged surface modeled in its own file is modeled
    Given a Rust file that hand-asserts Sync on a shared struct
    And that same file drives the struct under a loom model
    When I run the interleaving-robustness meter
    Then the verdict is modeled
    And that file is not listed as unmodeled

  Scenario: A model that only names the module is disclosed as a weaker signal
    Given flagged surface in "storage/coordination.rs"
    And a model file that names the "coordination" module without clearly exercising it
    When I classify the surface against the models
    Then "storage/coordination.rs" is modeled-elsewhere, not unmodeled

  Scenario: No hand-overridden surface is clean
    Given a Rust file with only an ordinary trait impl and safe atomics
    When I run the interleaving-robustness meter
    Then the verdict is clean

  Scenario: A language without loom or shuttle is n/a
    Given a repository whose language the interleaving-robustness meter does not support
    When I run the interleaving-robustness meter
    Then the verdict is n/a
