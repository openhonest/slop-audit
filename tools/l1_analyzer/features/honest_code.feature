Feature: honest_code — L1.21, mechanical conformity with the Honest Code principles
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Nineteen principles, nineteen subclauses, L1.21.1 through L1.21.19. The numbering is
  the Honest Framework's, so a clause number means one thing across every Open Honest
  artifact.

  The measure is mechanical, and the value of it is that it says which clauses it
  decided. Fifteen are decidable from a Python syntax tree. Two are questions about a
  browser and are not applicable to a Python file at all. One is decidable only in part:
  a cache is readable, and whether it was added before anyone profiled the query is not.
  One is not decidable by anything, ever, because it is a property of how work is
  sequenced rather than of code.

  A clause nobody could check stays outside the numerator AND the denominator, carrying
  its reason. It is never reported as passing. That is the same rule the Silence index
  follows and it is the whole reason to trust a conformity number: the score is over the
  clauses actually decided, so it cannot be raised by looking away.

  Scenario: read_source reads one file into what every clause needs
    Given the path to a source file
    When read_source parses it
    Then the tree, the text, the language and the functions and classes come back together
    But a file that does not parse comes back unreadable rather than empty, since a file nobody could read is not a file with no violations

  Scenario: applies_to says whether a clause can be decided for this file at all
    Given a clause and the source it would be run against
    When applies_to compares the clause's languages with the file's
    Then a browser clause is not applicable to a Python file
    But not applicable is a third answer beside pass and fail, because a clause nobody ran is not a clause that passed

  Scenario: assess runs every applicable clause over one file
    Given a parsed source
    When assess walks the clause table
    Then each clause comes back with its findings and the reason it could not be decided when it could not
    But an undecidable clause is never given a verdict, since the whole worth of the number is that it says what it decided

  Scenario: conformity is the share of decided clauses that hold
    Given the assessed clauses
    When conformity counts them
    Then only clauses that were actually decided are in the denominator
    But a file where nothing could be decided has no conformity rather than a perfect one, because a share of nothing is not a hundred percent

  Scenario: band_of turns a conformity share into the panel's verdict
    Given a conformity share, which may be absent
    When band_of reads it
    Then the bands are the panel's own
    But an absent share is n/a rather than the worst band, since unmeasured is not the same as bad

  Scenario: assess_file reads one file and assesses it
    Given a path
    When assess_file reads and assesses it
    Then the assessment names the file, the clauses and the conformity
    But it is the only function here that touches the filesystem, so every clause below it stays a pure function of a tree

  Scenario: analyze measures a whole repository against every clause
    Given a repository and the language to read it as
    When analyze walks the production files
    Then the panel entry carries the share, the band and which clauses were undecidable
    But it is optional in the full audit, because nineteen clauses over a large tree is a cost a caller chooses rather than one imposed on every run

  Scenario: report writes the per-clause result a person reads
    Given an assessment
    When report renders it
    Then each clause is named with its number, its verdict and its findings
    But the clauses nobody could decide are listed apart from the score, with the reason for each

  Scenario: hook_report writes the one thing an agent needs mid-edit
    Given an assessment of the file just written
    When hook_report renders it
    Then each finding is one line naming the file, the line, the clause and what to do instead
    But nothing else is printed, because a hook that fires on every write has to be read in a glance rather than studied

  Scenario: _clause assembles one subclause of the measure
    Given the rule number, its name, what decides it and who checks it
    When _clause assembles them
    Then the code is the Honest Framework's number rather than this file's position
    But the languages default to every language this reader knows, since most clauses ask about code rather than about a browser

  Scenario: read_source_text parses one file's text into what every clause needs
    Given the text of a file and its path
    When read_source_text reads it
    Then the language comes from the suffix and the tree from the parser
    But a file that does not parse comes back unreadable rather than empty, since a file nobody could read is not a file with no violations

  Scenario: _skip_reason says which KIND of undecided a clause is, and the sentence for it
    Given a clause and a source
    When _skip_reason compares them
    Then the kind is one of never, not applicable or unreadable, which is what a consumer buckets on, and only unreadable is a failure
    But the sentence used to be the only thing separating those three, so a reader had to parse English to tell a rule nothing decides from a file the audit could not read

  Scenario: assess_file_text measures one file's text against every clause
    Given the text of a file and its path
    When assess_file_text reads and assesses it
    Then the assessment carries the clauses, the share and the band
    But it touches no filesystem, which is what lets the hook path run on the buffer an agent just wrote

  Scenario: allowances reads the exceptions a file declares, with their reasons
    Given the text of a file
    When allowances reads its honest-code-allow comments
    Then each names one clause and carries the reason it does not apply here
    But an allowance with no reason is not honoured, since a suppression nobody justified is the silent skip this whole instrument exists to name

  Scenario: allowed_reason says whether one finding was declared an exception
    Given a finding and the allowances its file declares
    When allowed_reason compares the clause and the line
    Then a finding the author declared, with a reason, is set apart from the violations
    But it is never dropped, because an exception nobody can see is indistinguishable from a rule nobody checked

  Scenario: _withheld records one finding and what kept it off the violation list
    Given a finding and the reason it was withheld
    When _withheld records it
    Then the file, the symbol, the line and the reason travel together, so a reader can go and argue with the decision at the site
    But it is never dropped, since a suppression nobody can see is indistinguishable from a rule nobody checked

  Scenario: _split_withheld separates the violations from everything that withheld one
    Given a clause's findings and the allowances its file declares
    When _split_withheld reads what withheld each one
    Then a site an allow comment excused and a site a boundary decorator excused are both set apart, and each says which withheld it
    But a declaration that withheld nothing produces no record, since a marker on a function the clause would never have spoken about suppressed nothing and counting it punishes the declaration it was added to encourage

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

  Scenario: _parses_cleanly_as names the language whose grammar accepts a block whole
    Given the text of a string constant and the language of the file holding it
    When _parses_cleanly_as tries the grammars of the other languages
    Then a parse with no error node and some named structure in it names that language
    But tree-sitter accepts almost anything and reports trouble as error nodes rather than as failure, so the absence of them is the test and resemblance is never enough

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # Clause 17, the strangler pattern, is a property of how a migration is sequenced over weeks.
  # No reading of any file at any moment decides it, and it is the one clause here that is
  # excluded by its nature rather than by the reach of this reader.
  @undecidable @not-implemented
  Scenario: undecidable whether a migration followed the strangler pattern
    Given a repository holding both an old implementation and a new one
    When someone asks whether the migration was sequenced correctly
    Then the clause records that nothing checked it
    But no file, and no set of files, carries the sequence of the work that produced them
