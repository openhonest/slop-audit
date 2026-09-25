Feature: proof_outcomes — what a finished proof run meant
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it. Here it
  # is a run that printed nothing a reader recognises: no test line, no compiler error, no
  # panic. Something happened and this module cannot say what, so it is filed as unrun rather
  # than as a compile error, which is the bucket it used to be counted in. A sweep on
  # 2026-09-07 filed 181 of those as compile errors while sampling found zero cargo and zero
  # rustc processes across the whole module loop.
  @undecidable @not-implemented
  Scenario: undecidable a run whose output names neither a test nor a compiler
    Given the combined output of a run that printed no test line, no error code and no panic
    When _classify_run looks for each of the three and finds none
    Then it answers unrun, which is a fact about this tool's ability to run rather than about the generated test
    And the bucket is kept apart from a compile error, because the two send a reader to different places
    But nothing here records what the run did instead, so the reason it printed nothing is not collected

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

  Scenario: body_asserts decides whether a proof body will evaluate an assertion
    Given the body a model proposed for one gap
    When body_asserts parses it
    Then a body whose assertion runs is usable, including one inside a loop, a branch or a with-block, since those execute what they hold
    But a body whose only assertion sits inside a nested function nobody calls is not, because that function is defined and never entered, so the proof passes having measured nothing
