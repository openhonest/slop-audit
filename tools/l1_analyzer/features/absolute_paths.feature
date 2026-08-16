Feature: absolute_paths — machine-specific absolute paths in source
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _matches locates every machine-specific absolute path in a file
    Given the text of one source file
    When _matches scans it line by line
    Then it returns the 1-based line number and the matched text of each machine root it finds
    But a path that begins with a root no rule names, such as an API route, yields nothing

  Scenario: scan reports the repository's hardcoded machine paths as a banded finding
    Given a repository and a language name
    When scan reads the production source and collects every match
    Then it returns the count, the band, a detail line naming the files hit, and the findings capped at 50
    And the band is Healthy only at zero, because a hardcoded machine path is never correct
    But the test tree is excluded, since a test proving a path detector fires must contain the path it detects
