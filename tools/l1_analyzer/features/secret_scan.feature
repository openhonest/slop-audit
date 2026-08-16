Feature: secret_scan — counting the distinct credentials committed to a repository's current tree, without ever printing one
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the parse result is used without anyone asking whether it parsed:
  # _string_spans collects the string nodes that survived, the generic rule fires only inside
  # them, and the file is still counted in the denominator this module says was read end to end.
  @undecidable @not-implemented
  Scenario: undecidable a file in a supported language that the grammar could not parse
    Given a file whose suffix names one of the nine grammars but whose syntax that grammar rejects, so the parse yields error nodes where the string literals should be
    When analyze reads the file and _string_spans collects whatever string nodes survived
    Then it is recorded as unread rather than counted among the files scanned, so a count of zero secrets means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _rule assembles one credential pattern with the evidence standard it is judged by
    Given a rule name, a pattern, the number of the capture holding the credential, and a mode
    When _rule compiles the pattern and packages the four together
    Then it returns one rule, whose mode says what makes a match evidence: the issuer's own prefix and length, or merely a slot a credential could sit in
    And the capture number is what lets a finding report the credential's shape without reprinting the credential
    But a slot-only rule proves nothing on its own; its value must still clear the placeholder screen and the entropy floor

  Scenario: _has_env_syntax decides whether a file's lines are settings rather than prose or code
    Given a file name
    When _has_env_syntax checks its suffix against the settings suffixes and its name against the settings prefixes
    Then it answers yes for environment files, shell scripts, configuration and property files, YAML, infrastructure definitions, service units, container files and build files
    And only a yes lets the unquoted credential rule run, because in source that rule would charge an ordinary assignment to a variable and in prose it charged plain sentences

  Scenario: _entropy measures how random a value's characters are
    Given a string
    When _entropy counts each character and computes the Shannon entropy in bits per character
    Then it returns that number, which sits near the alphabet's maximum for a generated credential and well below it for an English phrase
    And it is the last of the three screens a slot-only match must pass

  Scenario: _is_placeholder recognises a value that instructs the reader rather than authenticates
    Given a candidate value
    When _is_placeholder looks for a placeholder word anywhere inside it, an interpolation marker, or a value built from at most two distinct characters
    Then it answers yes on any of the three
    And the placeholder words include the default service credentials, because a container-compose default was the single most common false positive across the validation repositories
    But the check on words is case-insensitive and substring-based, so a real credential that happens to contain one of those words is screened out too

  Scenario: _is_generic_secret applies the extra evidence a credential-shaped name alone cannot supply
    Given a candidate value
    When _is_generic_secret rejects anything containing a space or shaped like a universally unique identifier, rejects a placeholder, and then measures entropy
    Then it answers yes only for a value that clears all three and reaches the entropy floor
    And this is the whole difference between a scanner an auditor believes and one whose number gets ignored

  Scenario: _excerpt describes a finding's shape without copying the credential into the report
    Given a credential value
    When _excerpt takes its first four characters and its length
    Then it returns those two facts and nothing else
    And this is what stops the audit artefact becoming a second copy of the leak

  Scenario: _line_of turns a byte position in a file's text into a line number a reader can open
    Given the text of a file and a position within it
    When _line_of counts the newlines before that position
    Then it returns the one-based line number
    And every finding is located this way, so a reader can go straight to the line without the report ever quoting it

  Scenario: _string_spans finds where the string literals sit in a source file
    Given a file's bytes and its suffix
    When _string_spans parses the file with the grammar for that suffix and collects the span of every string literal, including heredocs and raw strings
    Then it returns those spans, and the generic rule then fires only inside them
    And this is what keeps a credential-shaped identifier, a type name, or a bare pattern from being charged as a committed credential
    But a suffix in none of the nine supported languages returns nothing at all, and the generic rule then runs over the whole file, which widens that rule and never silences the issuer-prefixed ones

  Scenario: _scan_text finds every credential in one file's text and says which rule caught it
    Given a file's text, its bytes, and its name
    When _scan_text runs each issuer-prefixed rule, then the private-key rule, then the generic rule inside the string literals, adding the unquoted variant only when the file's syntax is settings
    Then it returns the rule name, the line and the credential for each hit, with a hit already claimed at that line and value never counted twice
    And it is pure, touching no file system and no network, which is what makes the whole matching core testable without a repository
    But the private-key rule requires the encoded body to follow the header, so a document that merely warns against committing a key is not charged as a leak

  Scenario: _band_for turns the count of distinct credentials into the canon's band
    Given the number of distinct credentials found
    When _band_for applies the canon's thresholds
    Then it returns Healthy at zero, Not Healthy at one or two, and Slop at three or more
    But this is only the count arm of the canon's Slop band; the other arm, a credential confirmed live with its issuer, is never evaluated here and the result says so in words

  Scenario: _scannable rejects files whose content is machine-generated digests or third-party code
    Given a path
    When _scannable checks its name against the dependency lock files and its ending against the minified, source-map, vector and font suffixes
    Then it answers no for those and yes for everything else
    And without it a lock file's integrity digests would dominate the count, which is why the reference scanner allowlists the same shapes

  Scenario: _tracked_files asks the version control system which paths are actually committed
    Given a repository
    When _tracked_files runs the list-files command in it
    Then it returns the set of tracked paths, and the scan is then limited to those files, because the audit question is which credentials landed on the branch
    And this is a deliberate deviation from the reference scanner, which reads the file system, and the deviation is named in the result's detail line
    But a directory that is not a working copy, or a command that fails or is unavailable, returns nothing, and the scan then reads the whole tree instead of refusing, which widens the count rather than narrowing it and is disclosed in the same detail line

  Scenario: analyze counts the distinct credentials committed to the repository's current tree
    Given a repository and a language name
    When analyze reads every tracked, scannable, non-binary, in-scope file and groups the hits by rule and value
    Then it returns the number of distinct credentials, the band, the findings sorted by file and line, a split between the production tree and the test tree, and the occurrence count beside each finding
    And the language name is accepted and unused, since a committed credential is the same finding in any language
    And a credential appearing anywhere outside the test tree counts as a production finding, however many fixtures also carry it
    But when no file was opened at all it refuses in the value and the band rather than only in the prose, because a count of zero would be a clean bill of health on a repository this scanner never read, which is the worst answer a credential scanner can fabricate
