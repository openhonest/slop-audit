Feature: ruby_trace — running a Ruby repository's own suite to measure branch coverage and order determinism
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the coverage result is looked for at one fixed path, and its absence
  # there is reported as the coverage gem never having been started in the suite's helper, which
  # prescribes to a repository the very thing it already did.
  @undecidable @not-implemented
  Scenario: undecidable a coverage result the suite wrote somewhere other than the one path checked
    Given a repository that starts the coverage gem but sets its own coverage directory, or writes its result under a per-suite command name
    When decision_space_coverage runs the suite and looks only in the default coverage directory for the default result file
    Then it is recorded as unread rather than reported as a suite that never started the coverage gem, so a not-applicable names what was not read and never a remedy already applied
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _ruby finds the Ruby interpreter on the search path
    Given the current search path
    When _ruby looks for the ruby program on it
    Then it returns the path to ruby
    But it returns nothing when ruby is not installed, and both measurements turn that into a not-applicable naming Ruby and Bundler as the missing tools

  Scenario: _bundle finds Bundler, the program that runs the suite with the project's own gems
    Given the current search path
    When _bundle looks for the bundle program on it
    Then it returns the path to bundle
    But it returns nothing when Bundler is not installed, which stops both measurements with a not-applicable rather than a score

  Scenario: _lock_has_rspec reads the lock file for the third signal that a repository uses RSpec
    Given a repository
    When _lock_has_rspec reads its gem lock file and looks for rspec in the text
    Then it answers yes when the name appears
    And this is what detects a repository whose specs live somewhere other than a top-level spec directory
    But an unreadable or absent lock file answers no rather than raising

  Scenario: _detect_runner decides whether the repository runs RSpec, Minitest, or neither
    Given a repository
    When _detect_runner looks for a spec directory, an rspec configuration file, or rspec in the lock file, and failing all three for a test directory beside a Rakefile
    Then it names RSpec when any of the first three appear, and Minitest only when the last pair does, so RSpec wins whenever both shapes are present
    But it names neither when no suite shape is there, and both measurements then report not-applicable instead of a score of zero passing runs

  Scenario: _pin resolves the interpreter the repository pins rather than the one first on the path
    Given a repository and a time limit
    When _pin asks each version manager to resolve ruby for this directory, and takes the Bundler that sits beside the interpreter it names
    Then it returns that interpreter, that Bundler, an environment putting their directory ahead of everything else, and a note saying which manager resolved it
    And this is what stops an unrelated system ruby ahead of the shim from silently measuring the wrong interpreter
    But when no manager resolves ruby it falls back to the ambient interpreter and Bundler, with no environment change and no provenance note

  Scenario: _ruby_version asks the pinned interpreter what version it is
    Given an interpreter, a repository, a time limit, and the pinned environment
    When _ruby_version runs the interpreter's version probe inside the repository under a limit no longer than thirty seconds
    Then it returns the first line of the answer, so every measured result says which interpreter produced it
    But a probe that fails returns the words "an unknown ruby" rather than a blank

  Scenario: _ran counts how many tests the runner said it executed
    Given a runner name and the combined output of one run
    When _ran adds up the test counts in every summary line that runner writes
    Then it returns the total
    And a total of zero is the signal that the suite never ran at all, which the determinism measurement turns into a not-applicable rather than a failing run

  Scenario: _summary_line pulls out the runner's own summary so a failure carries a reason
    Given a runner name and the combined output of one run
    When _summary_line looks for that runner's summary line
    Then it returns the line as written, which names how many tests ran and how many failed
    But when no summary line is present it returns the first non-blank line of output, so the reason is never empty

  Scenario: _branch_totals adds up the branch coverage the suite recorded
    Given the coverage result the suite wrote
    When _branch_totals walks every command and every file in it and counts each branch leaf, counting one as covered when its hit count is above zero
    Then it returns the covered count and the total
    But a file stored in the older line-only format contributes nothing to either number, so an old result reads as no branch data rather than as zero coverage

  Scenario: _coverage_verdict decides L1.19 from a finished run and the branch counts the coverage gem recorded
    Given the covered and total branch counts, the exit code of the suite that produced them, and the interpreter that ran it
    When _coverage_verdict reads them
    Then a run that finished yields the covered share, banded Healthy above ninety, Not Healthy from sixty to ninety, and Slop below sixty, with both counts and the interpreter in the detail line
    And a suite that exited non-zero is still measured, with that exit named in the detail line, because tests that fail still exercise branches
    And a run that ran out of time is a not-applicable naming the timeout, decided before any count is read, because a run that was killed recorded none
    But a total of no branches is a not-applicable naming the exact change the suite's helper needs, never zero percent, since a share of no branches is absent and not zero

  Scenario: decision_space_coverage reports the branch coverage the repository's own coverage gem recorded
    Given a repository, a time limit, and a runtime override
    When decision_space_coverage runs the detected suite once and reads the branch totals from the coverage result the suite wrote
    Then it returns the covered share as a percentage, banded Healthy above ninety, Not Healthy from sixty to ninety, and Slop below sixty, with a detail line naming the counts, the suite outcome, and the interpreter
    And the runtime override is accepted and ignored, because the repository's own version manager selects the interpreter
    But a missing interpreter or Bundler, no detected suite, a timed-out run, a coverage result that was never written, an unreadable result, or a result with no branch data each returns a not-applicable naming that reason and, where it applies, the exact change the suite needs, because the coverage gem must be started inside the repository's own helper and cannot be injected from outside

  Scenario: _determinism_verdict decides L1.20 from the outcome of every randomized-order run
    Given the exit code and combined output of each seeded run, in the order the runs were made, the runner that made them, the number of runs asked for, and the interpreter that ran them
    When _determinism_verdict reads them
    Then it returns the count of clean runs over the number asked for, banded Healthy when every run passed, Not Healthy at one short, and Slop below that
    And each run that failed is named by its seed with the runner's own summary line, up to three of them, so a low score arrives carrying its own reason rather than as a bare number
    And the first run that ran out of time, and the first run in which no test executed at all, each stop the count and return a not-applicable naming that seed, rather than the misleading score of zero passes
    But no runs at all is a not-applicable too, because none clean out of none is absent and not a clean sweep

  Scenario: test_determinism counts how many randomized-order runs of the suite pass
    Given a repository, a number of runs, a time limit, and a runtime override
    When test_determinism runs the detected suite once per run with a different seed and a randomized order, counting the runs where every test passes
    Then it returns the passing count over the total, banded Healthy when all pass, Not Healthy when one short, and Slop below that, with the failing seeds' summary lines in the detail line
    And both runners randomize on their own, so no extra plugin is needed and the seed is passed straight through
    But a missing interpreter or Bundler, no detected suite, a run that times out, or a run in which no test executed each returns a not-applicable naming that reason, rather than the misleading score of zero passes
