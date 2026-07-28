Feature: L1.15-L1.17 Text and structural indicators (type escapes, whitespace, god files)
  Pure static text/structural scans. Language-specific patterns for escapes.

  Scenario: 0.5 any/ignore per KLOC is Healthy
    Given a 10000 LOC TS codebase with 5 `# type: ignore` or `any`
    When I compute L1.15
    Then L1.15 is 0.5 per KLOC
    And the band is Healthy

  Scenario: 4% trailing whitespace is Slop
    Given a codebase where 400 of 10000 production lines end with spaces
    When I compute L1.16
    Then L1.16 is 4.0
    And the band is Slop

  Scenario: 3% god files (>1000 LOC) is Slop
    Given 30 of 1000 production files are >1000 LOC
    When I compute L1.17
    Then L1.17 is 3.0
    And the band is Slop

  Scenario: One 5000 LOC god file is Slop even if percentage low
    Given one 5000 LOC file in a 100k LOC tree
    When I compute L1.17
    Then the band is Slop
