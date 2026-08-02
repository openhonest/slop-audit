Feature: L1.12-L1.14 External tool indicators (dead code, clones, secrets)
  These require running language-appropriate external tools on the tree. The value
  is what the analyzer actually reports: a finding COUNT for dead code and secrets,
  and a duplication PERCENTAGE for clones. (An earlier draft asserted a dead-code
  density; the analyzer is count-based, so these scenarios state the real units.)

  Scenario: No dead-code findings is Healthy
    Given vulture reports 0 unreachable symbols
    When I compute L1.12
    Then L1.12 is 0.0
    And the band is Healthy

  Scenario: 50 dead-code findings is Slop
    Given vulture reports 50 unreachable symbols
    When I compute L1.12
    Then L1.12 is 50.0
    And the band is Slop

  Scenario: 12% fuzzy near-duplicate blocks is Slop
    Given the clone detector reports 12.0% duplication
    When I compute L1.13
    Then L1.13 is 12.0
    And the band is Slop

  Scenario: Zero secret hits is Healthy
    Given gitleaks reports 0 secret findings
    When I compute L1.14
    Then L1.14 is 0.0
    And the band is Healthy

  Scenario: 4 secret hits is Slop
    Given gitleaks reports 4 secret findings
    When I compute L1.14
    Then L1.14 is 4.0
    And the band is Slop
