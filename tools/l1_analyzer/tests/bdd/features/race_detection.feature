Feature: Runtime thread-safety under ThreadSanitizer
  The dynamic counterpart to the static thread-surface meter. The meter says where the
  concurrency surface is; this runs the suite under ThreadSanitizer and says whether a
  race actually fires. A race observed is proven; the absence of one is bounded by the
  test suite, never a proof of safety. Runs untrusted code, so CLI/CI only, never the
  web path. No toolchain means an explicit n/a, never a false clean.

  Scenario: An observed data race is surfaced with its location
    Given ThreadSanitizer output reporting a data race in publish_backfill
    When I parse the ThreadSanitizer report
    Then one data race is surfaced
    And the race points at "shared_wal_coordination.rs" line 1386
    And both conflicting access sites are recorded

  Scenario: Every reported race becomes its own finding
    Given ThreadSanitizer output reporting two data races
    When I parse the ThreadSanitizer report
    Then two data races are surfaced

  Scenario: Clean output is bounded-safe, not proven-safe
    Given a suite that ran under ThreadSanitizer with no race reported
    When I read the verdict
    Then the verdict is no-race-in-tests
    And the details disclose that the result is bounded by the test suite

  Scenario: A language with no race harness is n/a, never a false clean
    Given a repository whose language the race harness does not support
    When I run the race harness
    Then the verdict is n/a
    And no race is claimed either way

  Scenario: A race in a flagged file is a confirmed exposed site
    Given ThreadSanitizer output reporting a data race in publish_backfill
    And the static surface meter flagged "storage/shared_wal_coordination.rs"
    When I cross-reference the observed races against the flagged surface
    Then the race is confirmed against the flagged surface
