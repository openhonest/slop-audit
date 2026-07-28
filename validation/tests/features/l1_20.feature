Feature: L1.20 Test determinism
  Run the full test suite 5 times in random order. Count how many runs are completely clean.
  Pure code (low L1.18) tends to be deterministic; heavy mutable state produces order-dependent flakes.

  Scenario: All 5 randomized runs pass is Healthy (100% determinism)
    Given a test suite with no shared mutable state between tests
    When I run the suite 5 times with --randomly-seed=random
    Then 5 of 5 runs pass
    And L1.20 band is Healthy

  Scenario: 3 of 5 randomized runs pass is Not Healthy
    Given tests that depend on DB fixtures or singletons created in previous tests
    When I run the suite 5 times randomized
    Then only 3 of 5 runs are clean
    And the band is Not Healthy

  Scenario: <4/5 (e.g. 2/5) is Slop
    Given heavy order dependence (many tests fail when order changes)
    When I run randomized 5 times
    Then <= 3 of 5 runs pass
    And the band is Slop
