Feature: L1.20 Test determinism
  Run the suite 5 times in random order; count fully clean runs. Pure code tends to
  be deterministic; shared mutable state across tests produces order-dependent
  flakes. (An earlier draft asserted an exact 3/5 Not-Healthy case. Order-dependence
  cannot be reliably constructed to a single intermediate count, so these assert the
  two ends that are reproducible: fully clean, and reliably broken.)

  Scenario: All 5 randomized runs pass is Healthy
    Given a test suite with no shared mutable state between tests
    When I measure L1.20 determinism
    Then all 5 runs pass
    And the band is Healthy

  Scenario: Order-dependent tests are Slop
    Given a chain of tests that each depend on state set by the previous test
    When I measure L1.20 determinism
    Then fewer than 5 of 5 runs pass
    And the band is Slop
