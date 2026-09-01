Feature: honest_code_embedded — source of another language held whole inside a string
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: unexamined_blocks names content inside a readable file that no clause looked at
    Given a file that parsed, and the string constants it holds
    When unexamined_blocks tries each substantial one against the grammars of the other languages
    Then a block that parses with no error node is reported with its language, its line and its size, and it is not graded
    But nothing is guessed from resemblance, since a block is only named when a real grammar accepts the whole of it, and 355 of this package's own long strings produced eleven hits and every one was genuine source

  Scenario: _docstrings names the strings a file declares as documentation
    Given a parsed file
    When _docstrings reads the first statement of the module, each class and each function
    Then those strings are skipped, since a docstring IS declared documentation and source inside one is an example rather than shipped content
    But a template genuinely held in a docstring is missed, and that limit is stated because its failure mode is silence

  Scenario: _accepted_by lists every grammar that takes a block whole
    Given the text of a string constant and the language of the file holding it
    When _accepted_by tries the grammars of every language but the file's own
    Then a parse with no error node and some named structure in it names that language
    But tree-sitter accepts almost anything and reports trouble as error nodes rather than as failure, so the absence of them is the test and resemblance is never enough

  Scenario: _markup_parts finds the script and style content inside a block of markup
    Given a block that the markup grammar accepts whole
    When _markup_parts reads its script and style elements by node type
    Then the text inside each is handed back to the same whole-grammar test, one grammar deeper
    But nothing is stripped and nothing is matched by pattern, since a wrapper removed by hand is the guess this test exists to avoid, and page content is the case that made the depth necessary

  Scenario: _accepts_whole says whether a grammar took the whole text without complaint
    Given a block of text and a language to try it as
    When _accepts_whole parses it and looks for error nodes
    Then a tree with no error and nothing missing is an acceptance
    But tree-sitter reports trouble as error nodes rather than as failure, so the absence of them is the whole test and a partial parse is never an acceptance

  Scenario: _grammar_root parses one block by whichever grammar owns its language
    Given a block of text and a language
    When _grammar_root picks the grammar for it
    Then the clause vocabulary is asked first, and markup and stylesheets are parsed by grammars kept outside it
    But they are kept outside on purpose, since that table is what tells a clause it can read a language and no clause reads these

  Scenario: _blocks_in finds each foreign block a run of text holds
    Given a string holding both a style element and a script element
    When _blocks_in reads it through the markup grammar and then each part
    Then one block comes back per element, each with its own line and its own size
    But a run that only parses as its own language is not a foreign block at all

  # No reading of any file at any moment decides it, and it is the one clause here that is
  # excluded by its nature rather than by the reach of this reader.
  @undecidable @not-implemented

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. A block is named here only when a whole grammar accepts the whole of it,
  # and the language nobody has a grammar for is the case that goes unrecorded today.
  @undecidable @not-implemented
  Scenario: undecidable a string holding source in a language this reader has no grammar for
    Given a long string constant holding real source in a language outside the five grammars this module loads
    When no grammar accepts the whole of it and the block is passed over
    Then the pass-over is recorded rather than read as prose, so a file holding a SQL procedure nobody examined does not report the same as a file holding a paragraph
    And the shape of what went unaccepted is offered for collection: the block's length and the marks it holds, with no content
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
