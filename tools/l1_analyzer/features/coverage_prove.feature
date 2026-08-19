Feature: coverage_prove — the Rust coverage-gap prove loop, where execution decides what counts as a proven bug
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today _refine_incidental has two branches for a two-way question and files
  # everything else under one of them: a permuted re-run whose bucket is anything other than
  # incidental_panic is returned as invalid_fixture, a divergence included, so a proof the
  # permutation itself surfaced is discarded as the tool's own noise and never reaches the card.
  @undecidable @not-implemented
  Scenario: undecidable a permuted re-run that failed in a way the permutation check has no branch for
    Given an incidental panic whose re-run with a valid aligned scalar fails again, but now on the test's own assertion rather than outside it
    When _refine_incidental reads the re-run's bucket and finds it is neither a pass nor another incidental panic
    Then it is recorded as unread rather than filed as an invalid fixture, so a discarded proof means the fixture was proven at fault and never that the refiner had no rule
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: model_available says whether a proposal can be asked for at all
    Given the process environment
    When model_available reads the API-key variable
    Then it is true only when the variable is set and not empty
    But nothing is contacted, so a key that is set and invalid still reads as available and fails later at the call

  Scenario: host_cfg reads the host target's cfg set so the gates can prove a branch is host-dead
    Given a machine that may or may not have a Rust toolchain on PATH
    When host_cfg runs rustc --print cfg beside the cargo it located
    Then it returns the host's cfg atoms
    But no cargo, or a non-zero exit from rustc, returns an empty set, which excludes no branch rather than guessing at the platform

  Scenario: _live_gaps drops the gaps this host could never reach
    Given the located gaps and the host's cfg set
    When _live_gaps asks the cfg gate about each gap's predicate
    Then only gaps a test on this machine could actually exercise survive
    And a gap with no cfg, or one the host cannot disprove, is kept, so the filter never removes a real gap on an unknown flag

  Scenario: _call_model makes one structured model call and refuses to return anything it cannot parse
    Given an instruction and a JSON payload
    When _call_model sends one message and strips a fenced code block off the reply
    Then it returns the parsed object
    But no API key, no anthropic package, a transport failure, unparseable JSON, or a reply that is not an object all return nothing, so an unusable reply never becomes a false proof

  Scenario: _signature writes the Rust signature line the model is shown
    Given one located gap's parameter names, parameter types and return type
    When _signature joins them
    Then it returns the fn line, which is the only shape information the proposal prompt carries beyond the source

  Scenario: _valid accepts a model reply only when it carries a usable test body
    Given whatever the model returned
    When _valid inspects it
    Then a non-blank string body comes back trimmed, with the explanation coerced to text
    But no reply, a body that is not a string, and a blank body are all rejected outright

  Scenario: propose asks for the first calling test that exercises one uncovered branch
    Given one located gap
    When propose sends the function source, the signature and the branch that was never exercised
    Then it returns a test body and a one-sentence explanation of the behaviour asserted
    But it returns nothing when the model is unavailable or its reply does not validate, and the gap is then skipped rather than faked

  Scenario: repair rewrites a test that did not compile, using rustc's own diagnostic
    Given a gap, the test source that failed to build, and the last 4,000 characters of the compiler error
    When repair asks for the arrange step to be rebuilt with real argument values
    Then it returns a corrected body and explanation
    But an unusable reply returns nothing, which ends the repair rounds and leaves the run standing as a build error

  Scenario: render_module wraps one test body in a proof module that can reach private functions
    Given a test body
    When render_module puts it in a cfg(test) module with use super::* in scope
    Then the proof compiles inside the module under test, so private and crate-internal functions are callable
    And no assertion is added here: the body carries its own, with the explanation as the panic message

  Scenario: _classify_run reads one cargo run as pass, fail or error, checking failure before build breakage
    Given the combined cargo output and the exit code
    When _classify_run tests the failure markers before the compile markers
    Then a failed assertion is a fail, even though cargo also prints its own error: test failed line
    And a non-zero exit after the harness started running is a fail rather than an error, so an abort with no panic message still reaches the gates
    But a zero exit with no test line at all is reported as a pass

  Scenario: _fail_bucket hands one failing run to the gates and returns their verdict
    Given one proof's output and label, its test body, and the function's return type
    When _fail_bucket parses that proof's panic and passes it to the failure classifier
    Then it returns the retention bucket for this failure
    And it decides nothing on its own, so the retention rule lives in one place and this is only the seam

  Scenario: _append_and_run runs a proof inside the real crate and always puts the file back
    Given a repository, the module path, a rendered proof and a test filter
    When _append_and_run appends the proof, runs cargo test with that filter, then restores the file
    Then it returns the exit code and the combined output
    And the module is written back byte for byte whether the run passed, failed, or raised partway through
    But with no cargo on PATH it returns a failure code and the words no cargo, without touching the file

  Scenario: _run_in_crate turns one rendered proof into a single in-crate verdict
    Given a repository, the module path and one rendered proof
    When _run_in_crate appends it, runs the filtered test and classifies the result
    Then it returns pass, fail or error together with the output
    But a timeout is reported as an error with a timed-out note appended, never as a branch that turned out correct

  Scenario: render_batch puts a whole module's proofs into one compile
    Given every accepted test body for one module
    When render_batch numbers them inside a single cfg(test) module
    Then a whole-codebase sweep costs about one build per module instead of one per gap
    But one body that will not compile poisons every proof in the batch, which is what the per-gap fallback exists for

  Scenario: _batch_status names the test the classifier never reported
    Given the batch classifier's verdicts and one test's index
    When _batch_status reads that index by subscript
    Then it returns the verdict for a test the runner reported
    And it returns `unreported` for one the runner never mentioned, which is a different fact from a compile error and gets its own bucket
    But it names the miss rather than raising, because the caller is a counting loop that has to finish the batch and one silent test does not justify abandoning the rest

  Scenario: _classify_batch reads each numbered proof's verdict out of one batched run
    Given the output of a batched run
    When _classify_batch reads every proof result line
    Then it returns each proof's index mapped to pass or fail
    But an output carrying no such line yields an empty mapping, and that emptiness is the caller's signal that the batch never compiled

  Scenario: _retained_entry assembles the record the card offers for adoption
    Given the module path, the gap, the accepted proposal and the rendered test source
    When _retained_entry builds the entry
    Then it returns the function name, the language, the file-and-line location, the explanation and the trimmed test source
    And nothing about the outcome is stored, because only a proven divergence is ever passed to it

  # The docstring says a panic that survives the permutation is "a real panic on valid
  # construction, kept for review". The body keeps it as an incidental panic ONLY when the
  # re-run is still incidental; every other re-run bucket, a divergence included, is returned
  # as invalid_fixture.
  Scenario: _refine_incidental re-runs an incidental panic with a valid scalar to see whether the fixture caused it
    Given a repository, a module path, a gap and the body of a test that panicked outside its own assertion
    When _refine_incidental rebuilds the fixture with a larger aligned scalar and runs it once more
    Then a re-run that no longer fails proves the scalar caused the panic, so the finding is an invalid fixture
    And a re-run that still panics outside the assertion stays an incidental panic, kept for human review
    But a body with no integer to permute cannot be checked at all and stays an incidental panic

  Scenario: _prove_one takes one gap through propose, run, repair and the gates
    Given one gap, a repair budget and a timeout
    When _prove_one proposes a test, runs it in-crate, and re-proposes from rustc's error while it will not compile
    Then it returns the bucket, the last proposal and its source, with only a divergence counting as a proven bug
    And an incidental panic is sent through the permutation check before the bucket is final
    But a model that declines to answer returns skipped, which the callers count in no bucket at all

  # The fallback loops over the original gaps rather than over the proposals already obtained,
  # so _prove_one asks the model for a fresh proposal for every gap in the module.
  Scenario: _prove_module proves all of one module's gaps, batched first and isolated only if that fails
    Given every located gap in one module, a repair budget and a timeout
    When _prove_module proposes each, compiles them as one batch, and gates every failing test
    Then it returns the retained divergences and a count in each named outcome bucket
    And a batch that does not compile falls back to proving each gap alone with compiler-feedback repair
    But that fallback discards the proposals the batch already paid for and asks the model again for every gap

  Scenario: prove_coverage_repo sweeps a whole crate and aggregates what execution settled
    Given a repository, a per-module cap, a repair budget and a timeout
    When prove_coverage_repo measures coverage once, then proves every module that has uncovered branches
    Then it returns the retained proofs across the codebase, the attempt count, the outcome buckets and a sentence naming what each attempt became
    And no cargo, no API key, and an unmeasured coverage run each return zero proofs with the reason spelled out
    But zero retained always carries the full breakdown, so an empty result can never be read as a clean bill

  Scenario: _outcome_detail writes out what each generated test became
    Given the outcome counts from a run
    When _outcome_detail turns them into one sentence
    Then every bucket is named, so a run that retained nothing still says what happened to the tests it wrote
    And only a behavioural divergence is described as a bug proven

  Scenario: prove_coverage proves the uncovered branches of one Rust module
    Given a repository, one module path, a cap, a timeout and a repair budget
    When prove_coverage locates the module's uncovered branches, drops the host-dead ones, caps the rest and proves each
    Then it returns the retained divergences, the attempts, the outcome buckets and the repair budget used
    But every path that runs nothing carries its own reason — no cargo, no API key, coverage not measured, or no proof-ready branch located — instead of an empty result that reads as success

  Scenario: ceiling_detail says what a truncated sweep did not attempt
    Given how many gaps were attempted, how many were located, and the ceiling
    When ceiling_detail compares them
    Then it names both numbers and the ceiling, so the gaps nobody measured are not read as clean
    But it says nothing when the ceiling did not bite, because saying so on every sweep would train a reader to skip the sentence on the one sweep where it matters

