Feature: dead_code_corpus — what the repository says about a name, gathered from every file
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _is_identifier_leaf recognises a name used as a name
    Given a syntax node
    When _is_identifier_leaf checks that it has no children and that its type is an identifier or a constant, in any grammar's spelling
    Then it answers yes
    And only these count as a real use of a name, which is what separates a genuine reference from the same word appearing in a string or a comment

  Scenario: _string_reference_names keeps the names a string could be resolving, not every word it holds
    Given a string literal node from any of the nine grammars
    When _string_reference_names reads the string's content
    Then it yields the content as one name when the whole string is a single identifier, which is what a getattr or a registry key looks like
    And it yields nothing for a string carrying the name among other words, so prose about a symbol no longer exempts it from the dead-code count
    But a comment never reaches here at all, because a comment carries no execution and so can never be the dynamic reference the exemption exists for

  Scenario: _harvest_source records every name a source file uses and every word it merely mentions
    Given a parsed tree, the file's path relative to the repository, and the corpus being built
    When _harvest_source walks the tree
    Then it records each identifier leaf as a hard use, with its file and its byte offset, so a use inside a definition's own span can later be told apart from a use outside it
    And it records the words inside every string and every comment in the soft string bucket instead, because a name mentioned there is a reason to doubt rather than a reference

  Scenario: _read_corpus reads the whole repository, because any file can be a reference site
    Given a repository
    When _read_corpus walks every file outside a vendored or ignored directory, parsing the ones in a supported language and taking the words from the rest
    Then it returns the hard uses keyed by name, the soft words split into strings, configuration and documentation, and a count of the files it could not read
    And a file with no supported extension goes to the documentation bucket by its suffix and to the configuration bucket otherwise, since a workflow file naming an entry point is a real reason not to call that entry point dead
    But a file over one megabyte or one that cannot be opened is counted and disclosed rather than dropped in silence, and a binary file is skipped entirely

  Scenario: _repo_facts answers the three questions about the repository that no single file can
    Given a repository and a language
    When _repo_facts looks for a Rust library root, reads the entry points every package manifest names, and searches Ruby sources for a runtime metaprogramming marker
    Then it returns whether the crate is a library, the set of declared entry files, and the first metaprogramming marker it found
    And the metaprogramming marker stops the whole measurement, because in a repository that builds methods at runtime an unreferenced name is not evidence of dead code
    But a manifest that cannot be read or parsed contributes nothing rather than failing the run

  Scenario: classify_into decides what one file contributes from its bytes and its suffix
    Given the bytes of a file and the suffix that names its kind
    When classify_into reads it without touching the filesystem
    Then a language this package can parse contributes names, and anything else contributes words
    But a file holding a null byte in its first 8 KiB is binary and contributes nothing

  Scenario: entry_paths_in reads the entry points a package manifest declares
    Given the parsed data of a package.json and the directory holding it
    When entry_paths_in reads the five single-path keys and the bin map
    Then each declared path comes back relative to the repository
    But a bin that is a bare string is legal npm and is not a map, so its characters are not iterated

  Scenario: metaprogramming_in names the first metaprogramming marker a Ruby source uses
    Given the text of a Ruby file
    When metaprogramming_in looks for the markers that make a dead-code reading unsafe
    Then the first one found comes back
    But one marker is enough, because the gate it feeds is repository-wide rather than per file


  Scenario: dotted_path_in reads the module path a string holds, or nothing
    Given the text of one string literal
    When dotted_path_in reads it
    Then two or more segments, each an identifier, give back the path, and the colon form is cut at the colon because what follows names a symbol inside the module rather than part of the path
    But whether the path means anything is settled by resolving it against the repository's own files, since a version number and a filename are dotted strings too

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. This module counts a file it cannot parse, and the count reaches the
  # reader; what it cannot do is say which names that file held.
  @undecidable @not-implemented
  Scenario: undecidable a file this reader has no grammar for, whose names are read as words
    Given a source file in a language no grammar in the table covers, holding a call to a function defined elsewhere in the tree
    When classify_into finds no grammar for the suffix and falls through to splitting the bytes into words
    Then the call is recorded as a word rather than as a reference, so it excuses the definition instead of proving it alive, and the reader says which languages it parsed rather than implying it parsed them all
    And the suffixes it could not parse are offered for collection: the extension and the file count, no path and no content
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
