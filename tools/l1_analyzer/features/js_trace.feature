Feature: js_trace — running a JavaScript or TypeScript project's own suite to measure branch coverage and order determinism
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _node finds the Node runtime the harness needs before anything else runs
    Given the current search path
    When _node looks for the node program on it
    Then it returns the path to node
    But it returns nothing when node is not installed, and every measurement above it turns that into a not-applicable naming Node as the missing tool

  Scenario: _nvm_dir finds the nvm install, which cannot be found the way a program is found
    Given the nvm directory named in the environment, or the default one in the home directory
    When _nvm_dir checks whether that directory holds the nvm script
    Then it returns the directory
    But it returns nothing when the script is absent, because nvm lives inside the shell rather than on the search path and there is nowhere else for it to be

  Scenario: _wrap makes a command run under the node version the target repository pins
    Given a repository and a command to run in it
    When _wrap prepares that command
    Then with nvm installed it returns the command wrapped in a shell that loads nvm, selects the version the repository's version file names, and then hands over to the command
    And without nvm it returns the command untouched, so the ambient node runs it
    But it never installs a version, so a pinned version nvm does not already hold simply does not get selected

  Scenario: _using_nvm supplies the words that tell a reader nvm chose the runtime
    Given the presence or absence of an nvm install
    When _using_nvm is asked how the runtime was selected
    Then it returns a short phrase naming nvm when nvm is installed, and an empty phrase otherwise
    And every measured result carries that phrase, so no reader has to guess which node was measured

  Scenario: _node_version asks the selected node what version it is
    Given a repository and a time limit
    When _node_version runs node's version probe in that repository, under a limit no longer than thirty seconds
    Then it returns the first line of the answer
    But a probe that fails returns the words "an unknown node runtime" rather than a blank, so the result still says something true about what measured it

  Scenario: _runtime_name names the runtime and the pin together for the result line
    Given a repository and a time limit
    When _runtime_name joins the resolved node version, the nvm phrase, and the version the repository pins
    Then it returns one phrase naming all three
    And a repository with no version file, or one that cannot be read, contributes no pin and the phrase names only the runtime
    But it reports the pin as written rather than checking that the running node matches it

  Scenario: _node_modules_present asks whether the project's dependencies are installed
    Given a repository
    When _node_modules_present looks for the installed-dependencies directory in it
    Then it answers yes only when that directory exists
    And a no stops both measurements with a not-applicable telling the reader to run the project's own install first, because this harness never installs anything on the subject's behalf

  Scenario: _package_json reads the project manifest that names the test command and the dependencies
    Given a repository
    When _package_json reads and parses the manifest at its root
    Then it returns the manifest contents
    But an unreadable or malformed manifest returns nothing, which both measurements turn into a not-applicable rather than a guess

  Scenario: _test_command takes the project's own test command from its manifest
    Given a parsed manifest
    When _test_command reads the test entry of its scripts
    Then it returns that command
    But it returns nothing when the entry is missing, blank, or the placeholder a new project ships with, since that placeholder is a real command that runs no tests and would otherwise be measured as a suite

  Scenario: _installed_major reads the major version of a package as installed in this repository
    Given a repository and a package name
    When _installed_major reads the version from that package's own installed manifest and takes the leading number
    Then it returns that number
    And it reads the target's installed copy rather than any globally installed one, so the answer describes the code that will actually run
    But an unreadable manifest, a missing version, or a version that is not a number returns nothing, and the caller then declines to rule the runner out

  Scenario: _c8_available asks whether the coverage tool is installed in this project
    Given a repository and a time limit
    When _c8_available runs the coverage tool's version probe there without allowing an install, under a limit no longer than sixty seconds
    Then it answers yes only when that probe succeeds
    And a no becomes a not-applicable naming the coverage tool and how to add it, never a coverage number

  Scenario: decision_space_coverage reports branch coverage measured by the engine's own coverage tool
    Given a repository, a time limit, and a runtime override
    When decision_space_coverage runs the project's own test command under the coverage tool and reads the branch percentage from the summary report
    Then it returns that percentage with a band that is Healthy above ninety, Not Healthy from sixty to ninety, and Slop below sixty, and a detail line naming the suite outcome and the runtime that measured it
    And the runtime override is accepted and ignored, because the project's own node selects itself and its runner
    But a missing node, missing dependencies, an unreadable manifest, no test command, a missing coverage tool, a timed-out suite, a summary that was never written, a summary with no branch totals, or a tree with no countable branches each returns a not-applicable naming that exact reason, never a zero that would read as real but terrible coverage

  Scenario: _detect_runner names the test runner the project uses
    Given a parsed manifest
    When _detect_runner looks through the project's dependencies and its test command for a runner it knows
    Then it returns the name of a runner it can drive into a random order when it finds one
    And it returns the name of a runner it recognises but cannot randomize when it finds one of those instead, so the not-applicable can say what was detected
    But it returns nothing when no runner it knows appears, and determinism is then declined rather than scored

  Scenario: _suite_ran decides whether the runner actually executed a suite
    Given a runner name and the combined output of one run
    When _suite_ran looks for that runner's own summary markers in the output
    Then it answers yes only when a marker appears
    And this is what separates failing tests from a runner that never ran, so a build error or an empty suite is never counted as a failing run

  Scenario: _failure_summary pulls out a line a reader can act on when a run fails
    Given the combined output of a failed run
    When _failure_summary looks for the first line mentioning failure
    Then it returns that line, trimmed to two hundred characters
    But when no line mentions failure it returns the first non-blank line, so the reason is never empty

  Scenario: test_determinism counts how many shuffled-order runs of the project's own suite pass
    Given a repository, a number of runs, a time limit, and a runtime override
    When test_determinism runs the project's runner once per run with a different seed and a shuffled order, counting the runs where every test passes
    Then it returns the passing count over the total, banded Healthy when all pass, Not Healthy when one short, and Slop below that, with the failing seeds' reasons in the detail line
    And the runtime override is accepted and ignored
    But a missing node, missing dependencies, an unreadable manifest, no runner it can randomize, a jest older than the version that accepts a seed, a run that times out, or a run whose suite never executed each returns a not-applicable naming that reason, rather than the misleading score of zero passes
