Feature: L1.12-L1.14 External tool indicators (dead code, clones, secrets)
  These require running language-appropriate external tools on the tree.

  Scenario: <1% unreachable code is Healthy
    Given a Python codebase with 10000 LOC and vulture reports 50 unreachable
    When I compute L1.12
    Then L1.12 is 0.5
    And the band is Healthy

  Scenario: 12% fuzzy near-duplicate blocks is Slop
    Given a codebase where PMD CPD with --ignore-identifiers reports 1200 LOC in clones >=50 tokens
    When I compute L1.13
    Then L1.13 is 12.0
    And the band is Slop

  Scenario: Zero secret hits is Healthy
    Given a clean tree with gitleaks reporting 0 hits
    When I compute L1.14
    Then L1.14 is 0
    And the band is Healthy

  Scenario: 4 secret hits (or any confirmed) is Slop
    Given gitleaks reports 4 hits including one real AWS key
    When I compute L1.14
    Then the band is Slop
