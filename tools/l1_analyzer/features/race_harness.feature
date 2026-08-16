Feature: race_harness — running a repository's own tests under a race detector, and again under contention, to see whether a race actually fires
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today parse_tsan splits the output at the data-race banner alone, so every
  # other warning class the same detector emits leaves no finding, and a run that reported one
  # comes back with the no-race-in-tests verdict and the Healthy band.
  @undecidable @not-implemented
  Scenario: undecidable a race-detector warning that is not a data race
    Given a run whose output carries a lock-order inversion, a leaked thread, or a signal-unsafe call inside a signal handler, and no data-race banner at all
    When detect_races hands the combined output to parse_tsan, which splits it at the data-race banner
    Then it is recorded as unread rather than resolved to the no-race-in-tests verdict and the Healthy band, so a clean verdict means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: parse_tsan turns a race detector's output into one finding per reported race
    Given the text a run under the race detector produced
    When parse_tsan splits it at each race banner, reads the summary line for the file, line and symbol, and takes the first source frame under each access header
    Then it returns one finding per race, carrying the primary site and the two conflicting sites
    And it is pure and deterministic, which is what lets the whole parser be tested without running anything
    But a block with no summary line, such as one a timeout cut short, is dropped rather than reported as a partial race

  Scenario: _verdict turns a set of parsed findings into the verdict, band and value for a suite that ran
    Given the findings from a suite that did run to a result
    When _verdict counts them
    Then any finding at all gives the race-observed verdict, the Slop band, and a value naming how many races were seen
    And none gives the no-race-in-tests verdict, the Healthy band, and a value that says in words that the evidence is bounded by the test suite
    But it is only ever asked about a suite that ran, so it can never turn a suite that never started into a clean result

  Scenario: _na builds the explicit not-applicable result that stands in place of a fabricated clean
    Given a reason and the name of the tool that was to be used
    When _na assembles a result from them
    Then it returns a result whose verdict, value and band are all not-applicable, whose finding list is empty, and whose detail line is the reason
    And this is the shape every missing-toolchain, no-tests, build-failed and timed-out path returns, so absence is disclosed and never measured as safety

  Scenario: _rust_toolchain_reason says why the race detector cannot run, or nothing when it can
    Given the current search path and the installed toolchains
    When _rust_toolchain_reason checks for the build tool and the toolchain manager, then asks the manager for its toolchain list
    Then it returns a reason naming the missing tool when either program is absent, a reason when the toolchain list cannot be read, and a reason naming the install command when no nightly toolchain is present
    And it returns nothing only when all three checks pass, which is the one case that lets a measurement proceed
    But it never installs a toolchain, so a missing nightly always becomes a disclosed reason rather than a delay

  Scenario: _host_target reads the machine's own target triple, which the sanitizer needs named explicitly
    Given the installed Rust compiler
    When _host_target runs the compiler's verbose version probe and reads the host line
    Then it returns the triple
    But a compiler that is missing, fails, or prints no host line returns nothing, and the caller turns that into a not-applicable saying the host triple could not be determined

  Scenario: _rust_tsan_command builds the command that runs the tests under the race detector
    Given a target triple
    When _rust_tsan_command assembles the command
    Then it returns a test command on the nightly toolchain that rebuilds the standard library with the sanitizer and names the target explicitly, since naming the target is what makes the instrumentation apply
    And it caps the test threads at four, so the schedule is contended but bounded
    But it sets no sanitizer flag itself; the caller supplies that in the environment

  Scenario: detect_races runs the repository's tests under the race detector and reports the races it observed
    Given a repository, a language, and a time limit
    When detect_races checks the toolchain, resolves the host target, runs the tests under the sanitizer, and parses the combined output
    Then it returns the race-observed verdict with the parsed findings when any race fired, and the no-race-in-tests verdict when the suite ran and none did
    And a run that timed out after a race already fired still reports that race, marked as a partial run
    But a language other than Rust, a missing or incomplete toolchain, an undeterminable host target, a build that failed, or a timeout before any result each returns an explicit not-applicable naming the reason, because a clean result on a suite that never ran would be the false clean this harness exists to avoid

  Scenario: _first_error pulls the compiler's first error line out of a failed build
    Given the combined output of a build that failed
    When _first_error looks for the first line beginning with the word error
    Then it returns that line, trimmed to two hundred characters
    But when no line begins that way it returns the words "unknown build error", so the not-applicable still carries a reason

  Scenario: parse_panic turns test output into one finding per panic, both panic formats
    Given the text a stress run produced
    When parse_panic reads each panic line for the thread, file and line, and takes the message from the same line in the older format or the following line in the newer one
    Then it returns one finding per panic, with the message trimmed to two hundred characters
    And a panic during a stress run is the code's own invariant check firing, which is the oracle this runner relies on rather than any detector

  Scenario: _cargo_available says whether the stress runner's one tool is present
    Given the current search path
    When _cargo_available looks for the build tool on it
    Then it returns nothing when the tool is there, which is what lets the stress runner proceed
    But it returns a reason naming the missing tool otherwise, and the stress runner turns that into a not-applicable
    And it asks for nothing beyond the stable build tool, no toolchain manager and no nightly, which is the whole point of having this second runner

  Scenario: stress_races runs the suite under contention repeatedly and reports a failure that fires on some runs but not others
    Given a repository, a language, a number of runs, and a time limit
    When stress_races runs the tests with eight threads once per run and sorts the runs into passes and panics
    Then every run passing gives the no-race-in-stress verdict with the Healthy band, stated as bounded by the suite and the run count
    And a mix of passes and panics gives the race-observed verdict with the Slop band, listing the panics deduplicated by file and line, because a failure that appears on some schedules and not others is a proven nondeterministic failure
    But a language other than Rust, a missing build tool, a run that timed out, a build that failed, or every run failing the same way each returns a not-applicable naming the reason, since a failure that reproduces every time is deterministic and is not evidence of a race

  Scenario: confirmed_surface names the observed races that landed where the static meter said to look
    Given the observed race findings and the set of files the static thread-surface meter flagged
    When confirmed_surface compares each finding's primary site and both conflicting sites against those files, matching on either path ending in the other
    Then it returns the findings that match, which are the sites where the static warning and the runtime observation agree
    And it matches by file rather than by line on purpose, because a race lands on the access line while the static finding sits on the declaration line of the same file
