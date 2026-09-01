Feature: honest_code — L1.21, mechanical conformity with the Honest Code principles
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Twenty-two principles, twenty-two subclauses, L1.21.1 through L1.21.22. The numbering is
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

  Scenario: repository_shapes names every record, protocol and exception root the whole repository declares
    Given every file the audit reads, production and tests alike
    When repository_shapes follows each class's bases and repeats until nothing new is admitted
    Then a base written in one file is a declared shape to every other file, so a chain split across three files is followed the same as a chain inside one
    And a file whose suffix names no grammar is passed over rather than counted, because there is no vocabulary to read its classes with
    But only the whole-repository run can call this: behind a write hook there is one file and no tree to search, and that run reports what it cannot follow rather than guessing about a file it never opened

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

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # Clause 17, the strangler pattern, is a property of how a migration is sequenced over weeks.
  Scenario: undecidable whether a migration followed the strangler pattern
    Given a repository holding both an old implementation and a new one
    When someone asks whether the migration was sequenced correctly
    Then the clause records that nothing checked it
    But no file, and no set of files, carries the sequence of the work that produced them

  Scenario: _findings_in runs the clauses on one embedded block
    Given a block of another language inside a readable file
    When _findings_in reads it through that language's own vocabulary and runs every clause that can
    Then the findings travel with the block, at the block's own lines
    But a block nobody could name has no vocabulary to read it through and yields nothing

  Scenario: _named_under names one file the same way however the repository was spelled
    Given a file inside the repository being audited
    When _named_under takes its path relative to that repository
    Then the same file gets the same name whether the caller said "." or the absolute path
    But a path outside the repository keeps the spelling it arrived with, because inventing a name for it would be worse than saying what was read

  Scenario: clause_named gives one row of the clause table by its code
    Given the code of a clause
    When clause_named looks for the row carrying it
    Then it returns that row, so a caller reading a clause's own words reads the table rather than a copy of it
    But a code nobody wrote down raises rather than returning a blank row, since a caller handed an empty clause would report a rule that does not exist as one that holds
  Scenario: shapes_around gathers the records the tree around one file declares
    Given a file on disk and its text
    When shapes_around is asked what that file's tree declares as a record, a protocol or an exception root
    Then a base written in the next file along is the same declaration as one written here, so the write hook and the commit gate read the file the same way
    But a file with no base it cannot already account for gets nothing back and no search at all, because this runs on every write and a tree walk costs about a second

  Scenario: _bases_from_elsewhere says whether any base sends the reader outside this file
    Given the text of one file
    When _bases_from_elsewhere reads its classes against the declared shapes and this file's own hierarchy
    Then only a base neither of those accounts for is one written somewhere else
    And a file it cannot parse counts as having one, since a file that cannot be read cannot be excused
    But "declares a class with a base" is not the test, because every typed record is written that way and it matched forty-three of this package's seventy-six modules

  Scenario: _tree_root finds the directory a file's tree starts at
    Given the path of one file
    When _tree_root walks up from it
    Then a repository marker wins over a package one, because a base can be declared in a sibling package
    But a file with neither above it has only its own directory, since one file with no tree around it is one file

