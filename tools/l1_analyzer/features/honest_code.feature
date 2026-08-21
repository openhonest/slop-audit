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

  Scenario: _skip_reason says why a clause was not run
    Given a clause and a source
    When _skip_reason compares them
    Then a clause nothing decides, an unreadable file and a language mismatch each give their own sentence
    But a clause that can be run gives no reason at all, which is what marks it decided

  Scenario: assess_file_text measures one file's text against every clause
    Given the text of a file and its path
    When assess_file_text reads and assesses it
    Then the assessment carries the clauses, the share and the band
    But it touches no filesystem, which is what lets the hook path run on the buffer an agent just wrote

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
