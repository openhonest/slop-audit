Feature: python_coverage_prove — the pytest coverage-gap prove loop, where an AssertionError is the only proof kept
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today _import_path takes repo and never reads it, so nothing bounds the
  # upward walk at the repository root. A module outside the package tree resolves to a dotted
  # name the repository does not own, the generated test imports whatever that name reaches on
  # the target's path, and the run reports the result as a setup error rather than as a path
  # the module could not resolve.
  @undecidable @not-implemented
  Scenario: undecidable a module whose dotted import path the repository root does not bound
    Given a module under test in a namespace package or a directory tree whose __init__.py files run past the repository root
    When _import_path walks upward without consulting the repo it was handed, and _prove_module hands the resulting name to the generated test
    Then it is recorded as unread rather than resolved to a name the repository does not own, so a setup error means the test was wrong and never that the import path was unresolvable
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  # The repo argument is accepted and never read. The walk stops at the first directory
  # without an __init__.py, wherever that lands, so the repository root does not bound it.
  Scenario: _import_path works out the dotted path a generated test will import
    Given a repository root and the file of the module under test
    When _import_path walks upward while each directory holds an __init__.py
    Then it returns the dotted module path, so a src-layout package resolves to its installed name rather than its folder
    But a module with no __init__.py beside it resolves to its bare file name

  Scenario: _signature writes the def line the model is shown
    Given one located gap's parameters, with annotations where the source had them
    When _signature joins them
    Then it returns the def line, and a parameter with no annotation appears as a bare name


  Scenario: propose asks for the first pytest test that exercises one uncovered branch
    Given one located gap and the module's dotted import path
    When propose sends the function source, the signature, whether it is a method, and the branch never exercised
    Then it returns a test body and a one-sentence explanation of the behaviour asserted
    But it returns nothing when the model is unavailable or its reply does not validate, and the gap is skipped rather than faked

  Scenario: repair rewrites a test that errored during setup rather than on its assertion
    Given the gap, the import path, the test that errored and the last 4,000 characters of the error
    When repair asks for the imports and the arrange step to be rebuilt
    Then it returns a corrected body and explanation, with the same intended assertion kept
    But an unusable reply returns nothing, which ends the repair rounds and leaves the setup error as the outcome

  Scenario: _indent shifts the model's statements into a function body
    Given statements the model returned with no indentation
    When _indent prefixes four spaces to each line
    Then a blank line is left blank rather than filled with trailing spaces, so the rendered function parses

  Scenario: render_test wraps one proof body in a collectable pytest function
    Given a proof body carrying its own imports and its own assert
    When render_test puts it in a function named for the proof
    Then a failing AssertionError is attributable to the test's own assertion and to nothing else
    But pytest collects the function only because the run overrides its function-name pattern, since the name does not begin with test

  Scenario: _classify reads one pytest run as pass, divergence, incidental or error
    Given the output of one pytest run and its exit code
    When _classify reads the short-summary line for the proof
    Then a failure whose exception is an AssertionError is a divergence, the test's own assert firing
    And any other exception, and a collection error, are incidental setup noise, while a timeout is an error rather than a verdict about the branch
    But output it cannot read at all falls to incidental, so an unrecognised run is never counted as a pass

  Scenario: _run executes one rendered proof under the target's own interpreter
    Given the repository, the interpreter to use and one rendered test
    When _run writes the test into a throwaway directory and runs pytest from the repository
    Then it returns the exit code and the combined output
    And the test file goes away with the temporary directory, so nothing is ever written into the user's test tree

  Scenario: _prove_one takes one gap through propose, run and repair
    Given one gap, its import path, a repair budget and a timeout
    When _prove_one proposes a test, runs it, and re-proposes from the error while the test keeps erroring on setup
    Then it returns the bucket, the last proposal and the test source
    And a model that declines to answer returns skipped
    But only a setup error triggers a repair round: a timeout is left alone, and a pass or a divergence is already settled

  Scenario: _prove_module proves every located gap in one module
    Given one module's gaps, its path, the interpreter, a repair budget and a timeout
    When _prove_module resolves the import path once and proves each gap in turn
    Then it returns the retained divergences and a count in each of the four outcome buckets
    And a retained proof carries the function, the location, the explanation and the runnable test source
    But a skipped gap is counted in no bucket, so the attempt total says nothing about the gaps the model never answered for

  Scenario: prove_coverage_repo sweeps a whole Python package and aggregates what execution settled
    Given a repository, a per-module cap, a repair budget, a timeout and an optional interpreter
    When prove_coverage_repo resolves the target's interpreter, measures branch coverage once, then proves every module with missing lines
    Then it returns the retained proofs, the attempts, the outcome counts and a sentence naming what each generated test became and which interpreter ran it
    But a missing API key, a target environment without pytest or coverage.py, and a coverage run that did not complete each return zero proofs with the reason named, never a clean result

  Scenario: _uncovered_lines measures the target's own suite and reports the lines it never reached
    Given the repository and the target's interpreter
    When _uncovered_lines runs the suite under branch coverage and reads the JSON report
    Then it returns the missing lines for each file, keyed by path relative to the repository root
    And files with no missing line, and files resolving outside the root, are left out
    But a timeout, a pytest exit outside pass-or-failures, a report that was never produced, and a report that will not parse each return not-measured with the reason, so nothing is ever scored over an absent measurement

  Scenario: body_asserts decides whether a proof body will evaluate an assertion
    Given the body a model proposed for one gap
    When body_asserts parses it
    Then a body whose assertion runs is usable, including one inside a loop, a branch or a with-block, since those execute what they hold
    But a body whose only assertion sits inside a nested function nobody calls is not, because that function is defined and never entered, so the proof passes having measured nothing
