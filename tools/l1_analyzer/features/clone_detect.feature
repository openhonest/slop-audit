Feature: clone_detect — L1.13 near-duplicate code, measured rather than delegated
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  The canon asks for the percentage of production LOC in a Type-2 or Type-3 clone class of
  at least fifty tokens, identifiers and literals normalized. This package shelled out to
  jscpd, which was installed on no machine that ever ran the panel, so L1.13 reported n/a
  on every repository this instrument has measured, both validation controls included. An
  indicator that has never produced a number is a column nobody has read, and since n/a is
  excluded from both halves of the slop fraction, the panel measured nineteen things while
  saying twenty.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A Type-3 clone with an insertion in the middle is the standing one. A window of the
  # required length still has to match on one side of the gap, so a copy with a line added
  # every few lines is invisible to this rule. Catching those needs suffix trees or a
  # similarity threshold, and the canon's own reference tool does not do it either: it runs
  # a minimum token run over an identifier-and-literal-normalized stream, which is this.
  @undecidable @not-implemented
  Scenario: undecidable whether a copy broken up by insertions is a clone
    Given a block copied and then edited so no fifty-token run survives intact
    When the windows are hashed
    Then no window repeats and the copy is not counted
    And the measure says how it counted rather than claiming to have found every clone
    But nothing here can distinguish that copy from code that was written once, so a zero is read-and-found-none and never looked-and-could-not-tell

  Scenario: literal_types names the node types a language spells a literal with
    Given a supported language
    When literal_types is asked for its vocabulary
    Then it returns the node types that language uses for literals
    But it raises for a language nobody wrote a row for, since defaulting to none would compare unnormalized text and report near-zero duplication on a codebase full of it

  Scenario: normalized_tokens turns a parse tree into the shape of its code
    Given a parsed file and its language
    When normalized_tokens walks every leaf
    Then each identifier becomes one symbol and each literal becomes one symbol, so a block copied and renamed still matches
    And keywords, operators and punctuation keep their text, so the structure is what is compared
    But comments are dropped rather than normalized, and a large data table is skipped whole, the way L1.17 already discounts one

  Scenario: _window_hash gives a run of symbols its identity
    Given a window of consecutive symbols
    When _window_hash digests them
    Then equal windows get equal digests
    But the digest is stored rather than the symbols, so a large repository holds one short value per window instead of fifty strings

  Scenario: duplicated_lines finds the lines inside a window that repeats
    Given the token stream of every file and the minimum window length
    When duplicated_lines hashes every window and collects the repeats
    Then every line a repeated window touches is duplicated, in the first occurrence as well as the copy
    But a window overlapping itself inside one long run is one clone and not a hundred, which the start position is what settles

  Scenario: analyze reports the share of production lines that repeat
    Given a repository and its language
    When analyze tokenizes every production file and measures the repeats
    Then it returns that share, banded against the canon's three and ten percent
    But a tree with no production source refuses, because a share of no lines is absent and not zero, and reporting zero would band Healthy for a repository nobody read

  Scenario: _declares_only_fields says whether a node is a record declaration and nothing else
    Given a node and its language
    When _declares_only_fields reads the class body for anything that is not a named field or the class's own description
    Then it answers yes for a record, which is a list of names carrying types
    And that is why a record is discounted: this check erases identifiers so two functions doing one thing with different names read alike, and a record IS its field names, so erasing them leaves the shape every record ever written has
    And four types in this package are called Finding and hold different facts, which the check reported as duplicated code because after normalising nothing was left to tell them apart
    And a name with no type does not count, so a class of constants is still read as code
    But one method makes it code and this answers no, because a rule that skipped any class would let anyone hide duplication behind a keyword
