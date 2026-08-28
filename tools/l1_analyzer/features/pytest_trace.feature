Feature: pytest_trace — running a Python repository's own test suite to measure branch coverage and determinism
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today this harness takes coverage.py's branch totals whole and never asks
  # what they left out, so a decision coverage.py does not enumerate is absent from both halves
  # of the fraction and raises the percentage instead of lowering it.
  @undecidable @not-implemented
  Scenario: undecidable a decision coverage.py never enumerated as a branch
    Given a repository whose decisions include constructs coverage.py counts in neither its covered branches nor its branch total
    When decision_space_coverage divides the covered branches by the total coverage.py reported
    Then it is recorded as unread rather than dropped out of a percentage it silently raises, so a share means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _run_untrusted runs a target repository's command in its own process group
    Given a command, a working directory, extra environment settings and a hard time limit
    When _run_untrusted starts the command in a fresh session and waits for it to finish
    Then it returns the exit code and both captured output streams
    And a command that outruns the limit has its whole process group killed, and comes back as exit code 124 with a timed-out note appended to the error stream
    But the command is treated as untrusted throughout, so nothing it starts can outlive the limit

  Scenario: _interpreter resolves a bare interpreter override
    Given the path of an interpreter the caller named, or nothing
    When _interpreter is asked which interpreter to use
    Then it returns the named path when there is one
    And it falls back to the interpreter the analyzer itself is running under
    But it never looks at the target repository, because its only caller is the import probe, which has no repository to search for an environment

  Scenario: detect_target_interpreter finds the target repository's own virtual environment
    Given a repository directory
    When detect_target_interpreter tries the six known virtual-environment layouts in order
    Then it returns the first interpreter path that exists on disk
    And a repository carrying no virtual environment yields nothing at all
    But existence is the whole test: the interpreter is never run here, so a broken environment still counts as found

  Scenario: resolve_interpreter decides which interpreter runs the suite and records why
    Given a repository and, optionally, an interpreter the caller named
    When resolve_interpreter applies its order of precedence
    Then it returns the interpreter together with a plain sentence saying where that choice came from
    And precedence runs from the caller's override, to the repository's own virtual environment, to the analyzer's own interpreter
    But the provenance sentence always travels with the answer, so a result measured under the wrong environment can never be read as if it were measured under the right one

  Scenario: resolve_via_shim asks a version manager which tool this repository pins
    Given a repository, the name of a tool and a time limit
    When resolve_via_shim asks each installed version manager in turn where that tool resolves for this directory
    Then it returns the first absolute path that exists, together with the name of the manager that gave it
    And a manager that is not installed, or that does not manage this tool, is skipped rather than treated as an answer
    But when no manager is installed or none resolves the tool, it returns nothing and an empty provenance, and the caller falls back to the ambient runtime

  Scenario: _module_available checks that a module imports in the interpreter that will run the suite
    Given a module name and, optionally, the interpreter to test it in
    When _module_available runs a bare import in that interpreter under a thirty-second limit
    Then it reports available only when the import exits cleanly
    And a crash, a timeout or an interpreter that cannot be started reports unavailable rather than raising
    But an interpreter that could not be started says so, since a caller told only "unavailable" sent a reader to install a package when the interpreter they named was the problem

  Scenario: _na packages a not-measured reason as a result the report can publish
    Given the reason a measurement could not be taken
    When _na wraps that reason
    Then it returns a result whose value and band both read n/a, and whose detail line is the reason itself
    And this is the shape every path in this harness returns in place of a guessed number, so a measurement that was never taken can never be read as a bad measurement

  Scenario: _first_line picks the first meaningful line out of a tool's output
    Given the captured output of a subprocess
    When _first_line scans it from the top
    Then it returns the first line that is not blank, trimmed and cut to 200 characters
    But output that is empty or entirely blank yields the words "no output", so the reason a reader sees is never itself blank

  Scenario: _coverage_verdict decides L1.19 from a finished run and its totals
    Given a pytest exit code, coverage.py's totals, and the provenance of the interpreter that ran
    When _coverage_verdict reads them
    Then exit 0 or 1 with enumerable branches yields the covered share and its band
    And exit 124 says the suite timed out, and 2, 3, 4 and 5 each name why the run was not valid
    And an exit code no row names reports the code itself rather than borrowing another row's reason
    But zero enumerable branches is n/a, never a percentage, because a share of no branches is absent and not zero

  Scenario: decision_space_coverage measures the share of decision branches the suite exercises
    Given a repository, a language name, a time limit and, optionally, an interpreter
    When decision_space_coverage runs the suite under branch tracing and reads the resulting coverage report
    Then it returns the covered share of branches as a percentage, banded Healthy above 90, Not Healthy from 60 to 90, and Slop below 60
    And the detail line names how many branches were exercised, whether the suite passed, and which interpreter ran it
    But any language other than Python, a missing test runner or coverage tool, a timed-out suite, a run that ended in a collection or usage error, an unreadable report, or a tree with no branches at all returns not-applicable with the reason, never a zero that would read as real but terrible coverage

  Scenario: _pytest_summary recovers the counts line from a suite run
    Given the combined output of one test run
    When _pytest_summary looks for the lines that report passed, failed or errored counts
    Then it returns the last such line, which is the run's own summary
    But output carrying no summary line yields a plain note saying so, which is what keeps a bare failure count from reaching a reader with no reason attached

  Scenario: test_determinism counts how many randomized-order runs pass cleanly
    Given a repository, a language name, how many runs to make, a time limit and, optionally, an interpreter
    When test_determinism runs the suite once per fixed seed, each seed producing a different execution order
    Then it returns the passing count over the run count, banded Healthy when every run passes, Not Healthy at one short, and Slop below that
    And the seeds whose runs had failures are named in the detail line, up to three of them, so a low score carries its own explanation
    But any language other than Python, a missing test runner, a missing order-randomizing plugin, a suite that collected no tests, a timed-out run, or a run that ended in an interruption, internal error or usage error returns not-applicable with the reason, rather than a zero score that would read as flakiness

  Scenario: coverage_band applies the one published L1.19 rule to a percentage
    Given a coverage percentage
    When coverage_band reads it
    Then strictly above 90 is Healthy, at or above 60 is Not Healthy, and below that is Slop
    And every language tracer asks this one function, so no two languages can grade the same evidence differently

  Scenario: determinism_band applies the one published L1.20 rule to a count of clean runs
    Given how many runs passed cleanly and how many were made
    When determinism_band reads them
    Then all clean is Healthy, exactly one short is Not Healthy, and worse than that is Slop
    But the caller refuses a zero denominator before reaching here, since zero clean out of zero would satisfy "every run passed" and band Healthy

  Scenario: determinism_tally counts finished runs and refuses what it cannot count
    Given a sequence of finished runs, the language's words for them, and how to read an output
    When determinism_tally walks the sequence
    Then it counts the clean runs, quotes up to three failing ones, and bands the share
    And it refuses on the first run that timed out or whose suite never executed, so the remaining runs do not each burn a timeout
    But no runs at all is refused rather than banded, since zero clean out of zero satisfies "every run passed" and would read Healthy


  Scenario: _stop_their_coverage tells a suite not to start its own coverage, where it can
    Given the Python that will run the target repository's suite
    When _stop_their_coverage asks that environment whether the coverage plugin is installed
    Then it returns the flag that turns the plugin off, because a repository with coverage in its own pytest settings starts a second session inside ours, theirs wins, ours records nothing, and we published a zero on a repository whose real coverage was high
    And it returns nothing where the plugin is absent, since passing the flag to a pytest that does not know it is an unknown argument that kills the whole run and turns a wrong number into no number
    But it asks rather than assuming, which is the difference between those two outcomes and is what the first attempt at this got wrong

  Scenario: _collection_was_empty gives our own sentence for a run that recorded nothing
    Given the output of a suite we ran
    When _collection_was_empty looks for the words coverage prints when it gathered no data
    Then it returns a sentence saying the collision is ours rather than a reading of their tests
    And ordinary output returns the empty string, because a rule that saw a collision everywhere would excuse every real zero
    But it says usually rather than certainly, since a suite that genuinely covered nothing prints the same words and this reader cannot tell the two apart
