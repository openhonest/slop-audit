Feature: L1.1-L1.8 Git-history indicators (doc/code discipline, delete discipline, test discipline)
  These eight indicators are computed purely from `git log` over a date range.
  They require no source reading. They measure the visible practice of
  writing specs before code, cleaning up AI output, and writing tests.
  High doc/mixed/net-negative ratios are Healthy. High code-only, low delete,
  low test ratios are Slop.

  # L1.1 Doc-only commit ratio
  Scenario: 20% doc-only commits is Healthy
    Given a git history with:
      | kind | count |
      | doc  | 2     |
      | code | 8     |
    When I compute L1.1
    Then L1.1 is 20.0
    And the band is Healthy

  Scenario: 0% doc-only is Slop
    Given a git history with only code commits
    When I compute L1.1
    Then L1.1 is 0.0
    And the band is Slop

  # L1.2 Code-only commit ratio
  Scenario: 60% code-only is Healthy
    Given a git history with:
      | kind | count |
      | code | 6     |
      | doc  | 4     |
    When I compute L1.2
    Then L1.2 is 60.0
    And the band is Healthy

  # L1.3 Mixed commit ratio
  Scenario: 15% mixed commits is Healthy
    Given a git history with:
      | kind  | count |
      | mixed | 3     |
      | code  | 17    |
    When I compute L1.3
    Then L1.3 is 15.0
    And the band is Healthy

  # L1.4 Doc lines as % of total added
  Scenario: 30% doc lines added is Healthy
    Given a git history with added lines:
      | kind | lines |
      | doc  | 300   |
      | code | 700   |
    When I compute L1.4
    Then L1.4 is 30.0
    And the band is Healthy

  # L1.5 Code delete/add ratio
  Scenario: 70% delete/add is Healthy (aggressive cleanup)
    Given a git history with code deltas:
      | added | deleted |
      | 100   | 70      |
    When I compute L1.5
    Then L1.5 is 70.0
    And the band is Healthy

  # L1.6 Net-negative commit ratio
  Scenario: 20% net-negative commits is Healthy
    Given a git history with:
      | delta_kind   | count |
      | net-negative | 2     |
      | positive     | 8     |
    When I compute L1.6
    Then L1.6 is 20.0
    And the band is Healthy

  # L1.7 High-delete-ratio commit ratio
  Scenario: 25% high-delete commits is Healthy
    Given a git history with:
      | delete_ratio | count |
      | >40%         | 5     |
      | <40%         | 15    |
    When I compute L1.7
    Then L1.7 is 25.0
    And the band is Healthy

  # L1.8 Test-to-production code ratio
  Scenario: 0.5 test/prod LOC is Healthy
    Given a repo with 1000 prod LOC and 500 test LOC
    When I compute L1.8
    Then L1.8 is 0.5
    And the band is Healthy

  Scenario: 0.05 test/prod is Slop (no tests written for AI code)
    Given a repo with 1000 prod LOC and 50 test LOC
    When I compute L1.8
    Then L1.8 is 0.05
    And the band is Slop
