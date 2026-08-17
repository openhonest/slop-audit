Feature: L1.12-L1.14 dead code, clones and secrets
  L1.12 and L1.14 went native on tree-sitter in 4c2e805 and no longer shell out to
  vulture or gitleaks. These scenarios stubbed those binaries on PATH and asserted
  the stub's output, so after that commit the stubs were never invoked and the
  assertions measured the real analyzer reading a one-line fixture instead. Two of
  them failed for that reason and one passed for the wrong reason, which is worse.
  They now state what the native measures actually do, over real source.

  L1.12 is a PERCENTAGE of definitions that nothing references, not a count. The
  header here claimed it was count-based, which was true of the delegation and has
  not been true since. L1.14 is a count, and in a regulated enterprise any non-zero
  count is disqualifying.

  L1.13 still delegates, to jscpd, so its scenario keeps the stub and is the one
  place in this feature where an external tool is genuinely exercised.

  Scenario: Every definition referenced is Healthy
    Given a codebase where every definition is referenced
    When I compute L1.12
    Then L1.12 is 0.0
    And the band is Healthy

  Scenario: An unreferenced definition is Slop
    Given a codebase with 1 of 2 definitions unreferenced
    When I compute L1.12
    Then L1.12 is 22.22
    And the band is Slop

  Scenario: 12% fuzzy near-duplicate blocks is Slop
    Given the clone detector reports 12.0% duplication
    When I compute L1.13
    Then L1.13 is 12.0
    And the band is Slop

  Scenario: Zero secret hits is Healthy
    Given a codebase carrying 0 credential-shaped strings
    When I compute L1.14
    Then L1.14 is 0.0
    And the band is Healthy

  Scenario: 4 secret hits is Slop
    Given a codebase carrying 4 credential-shaped strings
    When I compute L1.14
    Then L1.14 is 4.0
    And the band is Slop
