Feature: Structural race-condition shapes (B1 non-atomic RMW, B2 check-then-act)
  Beyond the overridden-guarantee surface (unsafe impl Send/Sync, static mut), the
  meter locates race-condition SHAPES on shared instance state: a read-modify-write
  done as separate load and store (B1), and a check-then-act window where a condition
  reads shared state and the body mutates the same state (B2). Both are restricted to
  self.-rooted receivers so shared instance state is flagged and pure locals are not.
  Each is a suspected shape to verify or prove, never a proven race.

  Scenario: A non-atomic read-modify-write on a shared atomic is flagged
    Given a method that loads self.count and then stores a value derived from it
    When I scan the Rust file for race shapes
    Then a non-atomic read-modify-write is reported on "self.count"

  Scenario: A single atomic fetch is not a non-atomic read-modify-write
    Given a method that updates self.count with a single fetch_add
    When I scan the Rust file for race shapes
    Then no non-atomic read-modify-write is reported

  Scenario: A check-then-act on a shared collection is flagged
    Given a method that checks self.seen then inserts into it
    When I scan the Rust file for race shapes
    Then a check-then-act is reported on "self.seen"

  Scenario: A check-then-act on a purely local collection is not flagged
    Given a method that checks a local map then inserts into it
    When I scan the Rust file for race shapes
    Then no check-then-act is reported

  Scenario: A Relaxed load that gates a branch is a review-level missing-acquire
    Given a method that branches on a Relaxed load of self.ready
    When I scan the Rust file for race shapes
    Then a relaxed guard is reported on "self.ready"

  Scenario: A Relaxed store to a counter is only a candidate, not a guard
    Given a method that stores to self.count with Relaxed ordering
    When I scan the Rust file for race shapes
    Then no relaxed guard is reported
