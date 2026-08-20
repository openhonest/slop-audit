Feature: prove — turning a located concurrency hazard into a demonstrated one
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the loop is already honest per hazard: a hazard nothing was generated
  # for is not-generated and one no toolchain ran is not-run, neither of them not-demonstrated.
  # What collapses them is retention, which drops all three alike and leaves an empty proof list.
  @undecidable @not-implemented
  Scenario: undecidable a hazard nothing was generated for and nothing was run against
    Given a sweep whose outcomes are all not-generated or not-run, so no hazard was ever put under contention
    When retained filters those outcomes for the report
    Then it is recorded as unread rather than returned as the empty proof list a fully run sweep returns, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: proof_request packages one located hazard with the code around it
    Given a thread-surface finding naming a kind, a file, a line and a symbol, plus the source window that surrounds it
    When proof_request copies those five fields across
    Then it returns the one hazard the generator is allowed to see
    But it reads nothing else from the finding, so the model never learns what else the repository contains

  Scenario: prove claims a hazard only when a generated test genuinely fired a race
    Given one proof request, a way to ask a model for a test, and a way to run that test under contention
    When prove asks for the test and, if it got one, runs it
    Then it returns demonstrated only when the runner reports an observed race, and carries the generated test with it
    And a run that finished clean returns not-demonstrated, worded as bounded by the run rather than as proof of safety
    But a model that returned nothing returns not-generated with no test attached, and any other runner verdict returns not-run, so a hazard nobody demonstrated is never claimed

  Scenario: retained keeps only the demonstrated proofs for the report
    Given the outcomes of every hazard the loop attempted
    When retained filters them
    Then it returns only the outcomes whose verdict is demonstrated
    But not-demonstrated, not-generated and not-run outcomes are dropped, so nothing reaches the report that was not run and seen to fire

  Scenario: model_available says whether a generation model can be called at all
    Given the environment the analyzer is running in
    When model_available looks for an Anthropic key
    Then it answers yes when the key is set and no when it is missing or empty
    But it never contacts the vendor, so a key that is present and invalid still reads as available here and fails later at generation

  Scenario: _strip_fences removes the markdown fencing a model wraps code in
    Given the text a model returned, which may open with a fence line and close with another
    When _strip_fences trims the text and deletes the fence markers
    Then it returns the bare source the compiler can accept
    But an unfenced answer passes through unchanged apart from surrounding whitespace

  Scenario: generate asks the model for one failing race reproduction, or gives up quietly
    Given a proof request carrying the hazard's code context
    When generate checks for a key, imports the vendor package, and asks the model for a single self-contained Rust test that fails only because of the race
    Then it returns the fenced-out source of that test
    And a missing key, a missing vendor package, or any error during the call returns nothing at all, which the loop reports as not-generated
    But it never inspects the answer for correctness, because the execution gate, not this call, decides whether the proof stands

  Scenario: write_crate_and_stress builds the generated test into a throwaway crate and runs it under contention
    Given the generated test source, a working directory, a run count and a timeout
    When write_crate_and_stress writes a fresh manifest and library file into that directory and hands the crate to the stress runner
    Then it returns the runner's verdict together with the runner's own detail text
    And the manifest pins the small set of concurrency crates the reproduction may reach for, so the build is stable
    But an absent build toolchain returns the runner's not-applicable verdict, which the loop reads as not-run, never as a clean result

  # The docstring says "retain iff it fires"; the body returns one outcome of any of the four
  # verdicts and does no retaining. Retention is the separate job of `retained`.
  Scenario: prove_hazard runs the whole loop for one hazard, with both collaborators handed in
    Given a located hazard, a model call and a runner
    When prove_hazard passes all three to the honesty gate
    Then the verdict is whatever that gate decides, and this wrapper adds nothing to it
    But neither collaborator has a default, because defaulting them put a paid API call and a real crate build one forgotten argument away from any test, and the boundary that means to spend money names them instead
