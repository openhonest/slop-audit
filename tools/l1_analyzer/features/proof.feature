Feature: proof — isolated proof requests, and the gate that decides whether one proved anything
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  The half of Umbra that turns a located silence into a demonstration. A silence says a
  test could exist; a retained proof says one does, and it FAILS.

  Two rules make this worth having rather than a way to let a model write tests. The
  CALLER writes the test, so a request carries one signature and one gap and no source.
  And nothing is believed: only a test that runs and fails, or makes the audited function
  raise, is retained, which is why the gate executes rather than reads.

  Scenario: signature_of reads one function's shape without its body
    Given the module source and the name of a function in it
    When signature_of reads the definition
    Then the parameters and the declared return come back as one line
    But the body does not, because a request carrying it would send the code under audit out of the machine and a caller does not need it to supply an argument

  Scenario: model_ready keeps the silences a failing test could demonstrate
    Given an audit's facets
    When model_ready filters them
    Then an unexercised branch, an untried input region and an unasserted exception path survive
    But an unasserted return contract does not, since no input makes "nobody checked the result" throw, and a runtime property does not, since it is shown by watching the suite run

  Scenario: requests builds one isolated request per model-ready silence
    Given an audit and the caller's cap
    When requests reads the model-ready silences
    Then each carries an index, the signature, the gap and what would count as a demonstration
    But a cap of zero or less asks for nothing, because a request is what gets sent to a model and slicing with a negative turned the strongest possible limit into an almost unlimited ask

  Scenario: malformed says why a proposal cannot be rendered, and names the field
    Given a proposal's concrete input, expected property and plain explanation
    When malformed reads them
    Then the field at fault is named, so a caller corrects that one and resubmits rather than guesses
    But both code fields must parse as expressions, since the gate executes what it renders and a statement in an argument list runs something other than the function under audit

  Scenario: _reaches_out refuses an expression that runs code or touches the disk
    Given a parsed expression from a proposal
    When _reaches_out walks it
    Then a call to import, exec, eval, open, compile, input or getattr is refused
    But an ordinary call to the audited function is not, because that is the whole point of the proposal

  Scenario: render turns one proposal into one runnable test file
    Given a request and a well-formed proposal
    When render writes the test
    Then it imports the module, calls the function with the proposed input and asserts the proposed property
    But it reads nothing from the existing suite, so a red suite elsewhere cannot make this look retained and a green one cannot hide it

  Scenario: read_outcome says what running the rendered test showed
    Given the exit code and the output of the run
    When read_outcome reads the lines pytest prefixes with E
    Then an assertion is a failure, a frame inside the audited module is the function erroring, and anything else is the proposal itself not running
    But reading the whole output matched the echoed source line, so a NameError in the proposal was filed as a demonstration and the tool's own failure counted as a finding

  Scenario: verify runs one proposal through the gate and keeps only a demonstration
    Given a module, a request and a proposal
    When verify renders it and runs it alone
    Then a test that fails or makes the function raise is retained
    But a passing test asserts behaviour the function already has and demonstrates no defect, and nothing is ever written into the caller's test file

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A discarded passing proposal may be a perfectly good test: it exercises a region the suite
  # never tried. Whether it is worth adopting is a judgement about the value of coverage, and
  # nothing here reads that.
  @undecidable @not-implemented
  Scenario: undecidable whether a discarded passing test is worth adopting
    Given a proposal the gate ran and discarded because it passed
    When someone asks whether to put it in the suite
    Then the gate reports that it demonstrates no defect
    But it cannot say whether the coverage is worth having, so adopting it stays the reader's decision
