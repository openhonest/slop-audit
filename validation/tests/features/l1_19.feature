Feature: L1.19 Decision-space coverage
  Of the *enumerable* decisions (dispatch keys, enum arms, match cases), what % are exercised by tests.
  Requires enumerating decisions + running the test suite with branch tracing.

  Scenario: 95% of dispatch keys exercised is Healthy
    Given a codebase with 20 dispatch table entries and a test suite that hits 19
    When I compute L1.19
    Then L1.19 is 95.0
    And the band is Healthy

  Scenario: 50% decision coverage is Not Healthy
    Given 100 enum variants but tests only exercise 50
    When I compute L1.19
    Then L1.19 is 50.0
    And the band is Not Healthy

  Scenario: 30% decision coverage is Slop
    Given many if/elif chains and dispatch tables with <30% exercised
    When I compute L1.19
    Then the band is Slop
