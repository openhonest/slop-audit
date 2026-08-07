Feature: Stress concurrency runner
  A second concurrency runner, and the one that needs no nightly: it builds and runs the
  suite under contention on the stable toolchain. The code's own invariant checks
  (assert!, turso_assert!) are the oracle; the runner only supplies a schedule that trips
  one. A panic that fires on some runs but not all is a proven nondeterministic failure -
  a race the suite's asserts caught. No panic across the runs is bounded by the suite,
  never a proof of safety.

  Scenario: A panic in the old Rust format is surfaced with its location
    Given stress output where a test panicked on an assertion (old format)
    When I parse the panic output
    Then a panic is surfaced at "src/storage/wal.rs" line 3498

  Scenario: A panic in the new Rust format is surfaced with its location
    Given stress output where a test panicked on an assertion (new format)
    When I parse the panic output
    Then a panic is surfaced at "src/storage/wal.rs" line 3498
    And the panic message mentions the failed invariant

  Scenario: Every panic becomes its own finding
    Given stress output with two distinct panics
    When I parse the panic output
    Then two panics are surfaced

  Scenario: A language without a stress runner is n/a, never a false clean
    Given a repository whose language the stress runner does not support
    When I run the stress runner
    Then the stress verdict is n/a
