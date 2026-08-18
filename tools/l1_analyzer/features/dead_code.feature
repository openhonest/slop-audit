Feature: dead_code — finding unreachable statements and unreferenced definitions from syntax alone, and disclosing everything it cannot decide
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. This module names its four refusals plainly in prose - an unwired language,
  # no production source, Ruby metaprogramming, and a grammar under four-fifths - but it names
  # them in a shape that drops a field. _na omits the unreadable count the measured result
  # carries, so a consumer asking how many files went unread gets nothing from a run that read
  # nothing at all, and reads that as none.
  @undecidable @not-implemented
  Scenario: undecidable how many files a refusal could not read
    Given a repository the module refuses outright, because no grammar is wired for the language or the grammar parsed under four-fifths of its production files
    When analyze builds the not-applicable result through _na and a consumer reads its unreadable count
    Then it is recorded as unread rather than absent from the shape, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _parser builds one parser per grammar and keeps it for the rest of the run
    Given the name of one of the ten grammars this module parses
    When _parser is asked for that grammar's parser
    Then it builds the parser on first use and returns the same one on every later call
    And the cache is held by the caching decorator rather than by a dictionary a function writes into, because this package's own external-state indicator counts a written module global as hidden state and caught the dictionary version of exactly this
    But a name that is not one of the ten raises rather than returning a default parser

  Scenario: _conditionally_compiled marks a block that a preprocessor cuts across
    Given a syntax node
    When _conditionally_compiled looks at its named children for a preprocessor directive
    Then it answers yes when one is there
    And a block that answers yes is not scanned for unreachable statements at all, because a directive sitting between a condition and its body detaches them in the parse and makes everything below read as dead
    But that refusal costs real findings and never invents one, which is the trade this module takes deliberately

  Scenario: _skip_in_unreachable_scan passes over anything that carries no execution
    Given the type name of a syntax node
    When _skip_in_unreachable_scan checks whether the word comment appears in it
    Then it answers yes for every grammar's spelling of a comment, whether line, block or plain
    And a comment following a return is therefore never charged as an unreachable statement, which it was before this existed

  Scenario: _is_terminator recognises a statement that ends the flow of its block
    Given a syntax node and the terminator types for its language
    When _is_terminator checks the node's own type and then, failing that, the type of the first child of an expression statement
    Then it answers yes in either shape, which is what catches a language that wraps its return in an expression statement
    But a jump to a label is deliberately not a terminator in any language that has one, because the label may sit anywhere below, including inside a loop, and a scan of sibling statements cannot see where the jump lands

  Scenario: _unreachable_statements finds every statement that follows a terminator in the same block
    Given a parsed tree and its language
    When _unreachable_statements walks every block, stops at the first terminator, and records each statement after it
    Then it returns the start and end line of each such statement, at full confidence, since no reference, type or framework knowledge is involved
    And scanning of a block stops at the first node that stays reachable after a terminator: a hoisted declaration in any language, a label only where a goto can jump forward into it, and a switch case only in C, the one grammar that spells a switch body with the same node it uses for every other block
    But a block a preprocessor cuts across is skipped entirely, and comments are passed over

  Scenario: _is_identifier_leaf recognises a name used as a name
    Given a syntax node
    When _is_identifier_leaf checks that it has no children and that its type is an identifier or a constant, in any grammar's spelling
    Then it answers yes
    And only these count as a real use of a name, which is what separates a genuine reference from the same word appearing in a string or a comment

  Scenario: _island_files names the production modules nothing else imports
    Given the reference corpus and the production file set
    When _island_files asks, for each Python module, whether any OTHER production file names its stem
    Then it returns the modules no sibling names, because a module nothing imports cannot vouch for what it contains
    And a package initialiser and a __main__ module are never islands, since one re-exports for its package and the other is invoked rather than imported
    But a reference from the test tree does not rescue a module, because a subsystem certified by its own tests plus itself is the same island one importer wider

  Scenario: _runnable_islands decides whether an island's module level ever executes
    Given a repository, its islands and its production file set
    When _runnable_islands looks for a main guard, a declared console script, a module-level call statement, or a one-file repository
    Then it returns the islands that can actually be run, so only those seed roots from their module level
    And a module holding only declarations is not runnable, which is what stops a dispatch table naming forty functions from certifying all forty
    But a file it cannot open is called runnable, so an unreadable file is never accused on evidence nobody read

  Scenario: _has_module_level_call separates a script doing work from a module declaring values
    Given the source text of one module
    When _has_module_level_call parses it and looks for a bare call statement at module level
    Then it answers yes for `main()` and no for a table or a compiled pattern bound to a name, because the statement kind is the signal and not whether a call appears
    But a file it cannot parse answers yes, which under-accuses rather than over-accuses

  Scenario: _owner_at names the definition a reference sits inside
    Given the definition spans of one file and a byte offset in it
    When _owner_at finds the innermost span holding that offset
    Then it returns that definition's name, or nothing when the offset is at module level
    But nothing is the answer that carries the rule: module-level code runs when the file runs, while a reference inside a definition runs only if that definition does

  Scenario: _sees answers whether one file can see the module another is defined in
    Given a reference site, the file a definition lives in, and the reference corpus
    When _sees asks whether the site names that module's stem, or is that module
    Then it answers yes only for a file that can actually reach the definition, so a same-named symbol in an unrelated module rescues nothing
    And it reads the same hard-reference map every other rule here reads, rather than parsing imports a second way, so the two readings cannot drift apart
    But it is asked only about islands, because everywhere else the name-pooled behaviour stands and under-accuses rather than over-accusing

  Scenario: _island_live_names decides which island definitions are actually reachable
    Given every definition, the reference corpus, the production files, the islands and which of them are runnable
    When _island_live_names seeds from the roots and closes over references sitting inside a live definition
    Then it returns the reachable names, so a helper called by a live function stays live and one called only by a dead function does not
    And reference is not reachability, which is the whole defect: two functions in a module nothing imports prove each other alive under a reference test
    But names are pooled across files rather than resolved per module, so two island modules holding a same-named function rescue each other, which over-excuses

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

  Scenario: _referenced_from decides whether a definition is really used from a given set of files
    Given a definition, the file it lives in, the corpus, and a set of files to count as reference sites
    When _referenced_from looks for a hard use of the name in one of those files, outside the definition's own byte span
    Then it answers yes on the first such use
    And excluding the definition's own span is what stops a self-recursive call, or the name token in the definition itself, from proving the definition alive
    But it matches on the name alone and resolves no types, so two same-named symbols cannot be told apart, and the error is always in the direction of sparing a definition

  Scenario: _soft_reason names the doubt that keeps an unreferenced definition out of the numerator
    Given a name and the corpus
    When _soft_reason checks the configuration, string and documentation buckets in that fixed order
    Then it returns the reason for the first bucket the name appears in: wired by name in configuration, referenced dynamically from a literal or comment, or published as a documented surface
    But it returns nothing when the name appears in none of them, and only then is the definition called dead

  Scenario: _band_for turns the flagged-line ratio into the canon's three bands
    Given a percentage
    When _band_for applies the canon's thresholds, with a lower number being better
    Then it returns Healthy below one percent, Not Healthy from one to five, and Slop above five

  Scenario: _na builds the not-applicable result, keeping every field a consumer reads
    Given a reason
    When _na assembles a result from it
    Then it returns a result whose value and band are not-applicable, whose detail line is the reason, and whose finding lists, counts and line totals are all empty or zero
    And keeping the full shape means a consumer reading the findings need not special-case a refusal
    But it carries no unreadable-file count, which the measured result does, so that one field is present on one shape and absent on the other

  Scenario: _classify_files splits the repository's files into production reference sites and test reference sites
    Given a repository
    When _classify_files asks the scope rule for the reason each file is set aside and sorts the file by whether that reason is a test directory
    Then it returns the two sets of paths
    And a definition reached only from the test tree is reported in its own list, since the tests do call it but it is not load-bearing production code either
    But every file that is not in a test directory lands in the production set, including documentation and tooling, because here they are reference sites rather than measured code

  # The docstring says analyze returns "the ratio". tests/bdd/features/l1_external.feature says
  # the opposite in its own header: "a finding COUNT for dead code and secrets ... An earlier
  # draft asserted a dead-code density; the analyzer is count-based". The code returns the
  # ratio: flagged lines divided by production lines, as a percentage. Recorded, not fixed.
  Scenario: analyze reports one repository's flagged-line ratio as an explicit lower bound
    Given a repository and a language
    When analyze reads the production source, parses each file, collects the unreachable statements and the definitions, and checks each definition against the reference corpus
    Then it returns the flagged lines as a percentage of production lines, the band, the dead findings, the undecidable disclosure, the definitions only the tests reach, and the counts behind all of them
    And every definition a language or a framework can reach by a route a syntactic scan cannot follow is called undecidable, listed with its reason, and left out of the numerator, which is what makes the published number a lower bound rather than a claim
    And a file the grammar could not parse is not analyzed and its lines are removed from the analyzed total, while its identifiers still count as references, so an unparsed file can spare a definition and never condemn one
    But an unwired language, no production source, a repository using runtime metaprogramming, or a grammar that parsed under four-fifths of the production files each returns a not-applicable naming the reason, and a repository with zero production lines still returns a ratio of zero and the Healthy band rather than refusing
