Feature: git_indicators — L1.1 through L1.8, read from git log alone
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Eight indicators about how a repository is worked on rather than what it holds. None of
  them opens a source file or builds a parse tree, which is why they run on any language.

  Split out of indicators on 2026-08-30, when that module crossed a thousand lines of code
  and the audit reported it as a god-file. These read a history and the rest read a parse
  tree, and the two have no vocabulary in common.

  Scenario: undecidable whether a commit that touches both code and documentation was one change or two
    Given a repository whose history holds commits touching source files and prose together
    When the classifier asks what kind of change each commit was
    Then a mixed commit is counted as mixed rather than split between the two, because nothing in a diff says which half was the point
    And the shape of what it could not decide is offered for collection: the file extensions in the commit, every path and message stripped
    But the operator opts in for that run only, after the whole payload is printed rather than summarised, and nothing leaves the machine when they decline

  Scenario: _classify_file sorts one commit path into doc, code or other
    Given one repository-relative path taken from a commit
    When _classify_file reads the end of the lowercased path
    Then it answers doc, code or other
    And the code list holds configuration and data as well as source, so a change to a workflow file, a lock file or a container file counts as code
    But a path matching neither list, such as a licence or a makefile, is other, and no indicator downstream counts it as either

  # The three commit-mix percentages divide by every commit, including the ones classified as neither doc nor code.

  Scenario: compute_git_indicators reads the commit history into the first eight indicators
    Given a repository and the optional earliest and latest dates
    When compute_git_indicators reads the commit log with per-file line counts and closes each commit as it goes
    Then it returns the eight results L1.1 through L1.8, each carrying the counts behind its number rather than a bare percentage
    And a commit that touched only files classified as other still raises the commit total while joining none of the three mix counts, so all three percentages are diluted by it
    But a merge commit carries no per-file lines in this log form and is invisible to every count here, and when the log fails or the date range holds no commits all eight come back as zero under the n/a band

  Scenario: _is_test_file decides whether one path is test code
    Given a path from anywhere in the repository
    When _is_test_file tries the directory rule, the dotted-project rule, the filename rule and the capitalised-stem rule in turn
    Then it answers yes as soon as one of them matches
    And the capitalised-stem rule reads the name in its original casing on purpose, so a production file whose name merely ends in the letters of the word test is not swept up with the real ones

  Scenario: _test_to_prod_ratio weighs the test tree against the production tree
    Given every source file in the repository, the test tree included
    When _test_to_prod_ratio splits the files by the test rule and counts lines on each side
    Then it returns the ratio of test lines to production lines, its band, and both line totals
    But with no production lines at all it refuses with n/a rather than divide, and a file it could not open is counted and disclosed

  Scenario: _ratio_indicator measures one of the ratio indicators by its row
    Given the code of a ratio indicator and its numerator and denominator
    When _ratio_indicator reads the row for its label, thresholds and wording
    Then the share is banded and the counts read back in that row's own words
    But a denominator of zero is absent rather than zero, and the row says why in the refusal

  Scenario: _git_refused writes the eight rows for a repository nobody could read
    Given a directory that is not a git working copy, or a date range holding no commit
    When _git_refused is asked for the panel with the reason
    Then all eight rows carry n/a for both the value and the band, and the reason in the details
    And the eight keys are written out rather than made by counting, because the panel names them and a count made at run time cannot be checked against that
    But not one row carries a zero: L1.5 is deleted over added lines, so zero is the Slop end of its own scale, and an unreadable directory would have read as a repository that measured terribly
