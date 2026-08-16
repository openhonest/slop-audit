Feature: state_census — the second, independent count of declaration sites, the denominator the classifier cannot supply for itself
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today a construct no extractor emits a site for has no kind, so no
  # capability entry can record it unreadable, unread_kinds stays empty and the refusal it feeds
  # never fires: the slot simply leaves the declared total and every coverage fraction measured
  # against that total comes out higher for it.
  @undecidable @not-implemented
  Scenario: undecidable a declaration none of the census extractors emit a site for
    Given a file declaring state through a construct no extractor here reaches, such as a module-scope binding made under a conditional
    When count walks the repository and tallies the sites
    Then it is recorded as unread rather than dropped from the declared total, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _of_type collects every node of the wanted kinds
    Given a parse tree and the node kinds wanted
    When _of_type walks the whole tree from that point down
    Then it returns every node of those kinds at any depth, in source order
    But it stops for nothing, so a record nested inside a record is reached on the same walk as the record around it

  Scenario: _own collects only the nodes one scope declares for itself
    Given a scope node, the node kinds wanted and the kinds the walk must stop at
    When _own walks the scope without descending into a nested record or a nested declaration
    Then it returns only the nodes belonging to that scope itself
    And a nested one is reached on its own turn and counted against its own owner, so no slot is counted twice

  Scenario: _bound_name unwraps a declaration down to the identifier it binds
    Given a name-carrying node from a declaration
    When _bound_name peels the declarator wrappers that an array, a pointer or a function pointer puts between a declaration and its name
    Then it returns the plain identifier the declaration binds
    And it must arrive at the same name the classifier arrives at, because the coverage number is measured by matching those names

  Scenario: _named_field reads the name off whichever field a declaration carries
    Given a declaration node and the name-carrying fields to try, in order
    When _named_field takes the first of those fields the node actually has
    Then it returns the name behind it, past any declarator wrappers
    But a node carrying none of them returns the empty string and the caller drops it

  # Python and Ruby declare no field kinds here, so this returns nothing for them and their state is counted by the other extractors.
  Scenario: _field_sites counts the slots declared inside record types
    Given a parsed file and its language
    When _field_sites finds every field declaration and names the record each one sits in
    Then it returns one site per declared slot, kinded by the node the parser produced, so a C# property and a C# field stay separate kinds rather than collapsing into one
    And each declaration is bounded at the next record or declaration, so an anonymous union's members are counted against the union and not also against the struct wrapping it
    But a field declaration with no record around it is discarded as parser recovery, which is what a macro-prefixed C prototype misparses into

  Scenario: _receiver_sites counts the attributes a method assigns through the receiver
    Given a parsed file and its language
    When _receiver_sites looks for assignments whose target is an attribute of one of that language's receiver names
    Then it returns one site per attribute assigned, for Python, JavaScript and TypeScript only, Python counting both of its receiver names
    But the other six languages carry no receiver rule and return nothing, and only a plain assignment counts, so a slot that is only ever updated in place is never a declaration site

  Scenario: _ruby_ivar_sites counts the instance variables one Ruby file writes
    Given a parsed Ruby file
    When _ruby_ivar_sites looks for assignments whose target is an instance variable
    Then it returns one site per instance variable this file assigns, owned by the class or module around it
    But an instance variable this file only reads is state declared elsewhere and is left out, so no file is charged for another file's slot

  Scenario: _py_toplevel counts Python's module bindings and class-body bindings as two kinds
    Given a parsed Python file
    When _py_toplevel reads the module's own statements and then each class body's own statements
    Then it returns the module bindings and the class-body bindings as separate kinds, both being state whose lifetime is the process
    But it reads only the statements sitting directly at those two levels, so a binding made under a conditional or any other wrapper at module scope is never a site

  Scenario: _js_toplevel counts every top-level declarator, constants included
    Given a parsed JavaScript or TypeScript file
    When _js_toplevel reads the top-level declarations and takes each declarator's name
    Then it returns one module-binding site for every one of them
    And a constant is counted here where the classifier declines it, because a constant name bound to a mutable object is still a declared slot and the census issues no verdicts

  Scenario: _rust_toplevel counts every static item, mutable or not
    Given a parsed Rust file
    When _rust_toplevel reads the file's own static items
    Then it returns one module-binding site for each, the immutable ones included
    And immutability is a verdict about the state, which the classifier issues and the census does not
    But a constant is a different node kind and never reaches here at all

  Scenario: _go_toplevel counts the package-level variable declarations
    Given a parsed Go file
    When _go_toplevel reads the package-level variable declarations and takes each specification's name
    Then it returns one module-binding site per specification
    But it takes the first name only, so a single specification naming several variables at once contributes one site instead of several, and a package-level constant is a different node kind and is not counted

  Scenario: _c_declarator_name unwraps a C declarator to the identifier it binds
    Given a child of a C file-scope declaration
    When _c_declarator_name peels the initialiser, array and pointer declarators
    Then it returns the identifier being declared
    And it is re-derived here rather than borrowed from the classifier, because the census is the second reading and a shared helper would be a shared blind spot
    But a function declarator declares no slot and returns the empty string

  Scenario: _c_toplevel counts C's file-scope variables
    Given a parsed C file
    When _c_toplevel reads the file's own declarations, skipping type definitions
    Then it returns one module-binding site per declared variable
    But a variable declared inside a function is never a root child and never reaches here

  Scenario: _no_toplevel declines to count a module scope three languages do not have
    Given a parsed Java, C# or Ruby file
    When _no_toplevel is asked for that language's top-level bindings
    Then it returns nothing, those three keeping their state in fields and instance variables that the other extractors already counted
    And it is dispatched to by name rather than defaulted to, so a language nobody wrote a rule for raises instead of quietly counting zero

  Scenario: _file_sites joins one file's declaration sites into a set
    Given a parsed file and its language
    When _file_sites joins the field sites, the receiver sites, the top-level bindings and, for Ruby, the instance variables
    Then it returns them as a set, so one slot spelled twice in one file counts once and opens no gap the code never had
    But two records of different names each holding a slot of the same name stay two sites, because the owning record is part of the site

  Scenario: kind_phrase names the unread constructs in prose a reader can act on
    Given the list of declaration kinds a refusal has to name
    When kind_phrase turns each kind into its reader-facing label and joins them
    Then it returns them as prose, so a refusal can say which construct went unread instead of quoting a bare count
    And nothing to name returns the honest admission that we did not record which, never an empty string that would leave the sentence dangling
    But a kind carrying no label raises, because a construct nobody named must not reach a reader as silence

  Scenario: _kinds lists the declaration kinds the census can count for one language
    Given a language
    When _kinds reads the capability table for the pairs naming that language
    Then it returns those declaration kinds in the table's own order
    And that order seeds the per-kind tally, so a kind this language can spell appears with a count even when the count is zero

  Scenario: _walk collects the declaration sites of every file in scope
    Given a repository and a language
    When _walk parses every file in the classifier's own scope and collects each one's declaration sites
    Then it returns the sites keyed by the same relative path the classifier reports its findings against
    And they stay per file rather than merged, because a site name is unique only within one file and merging would let a visit to one cover the other
    But the count of files it could not read is thrown away, so an unreadable file quietly shrinks the denominator with nothing said about it

  Scenario: uncounted refuses the census for a language it has no rules for
    Given the number of findings the classifier admitted
    When uncounted builds the census result for a language nothing here can read
    Then it returns every count as not-recorded rather than zero, which withholds the gap check instead of faking it
    And a confident zero is the exact failure this module exists to stop, because an unread repository would otherwise report a full denominator and pass

  # Every pair in the capability table is currently recorded readable, so the unread-kinds list is always empty and the refusal it feeds can no longer fire.
  Scenario: _tally rolls the per-file sites up into the counts a census reports
    Given the sites of every file and the language
    When _tally counts the sites by kind against the seeded capability list
    Then it returns the total declared, the per-kind counts, the file count, the reachable subset whose kind the classifier has a rule for, and the kinds declared here that it has no rule for
    And a kind the extractors emit with no capability entry raises, rather than going quietly missing from the denominator
    But no pair in the table is recorded unreadable today, so the reachable count equals the declared count for every language and the refusal is unexercised rather than wrong

  Scenario: count publishes the census over one repository
    Given a repository and a language
    When count walks the repository in the classifier's scope and tallies the sites
    Then it returns the declaration-site census for that language
    But a language with no field table, or no grammar, gets a not-recorded census carrying fewer keys than the refusal built for the comparison, so the two refusals are not the same shape

  Scenario: _hit counts how many declared sites the classifier's walk reached
    Given the declared sites per file and the sites the classifier's own walk reached
    When _hit intersects the two, file by file
    Then it returns how many declared sites were actually reached
    And a file the classifier never opened contributes nothing rather than raising, which errs towards a lower coverage figure and never a higher one

  Scenario: compare publishes the two coverage fractions in one unit
    Given a repository, a language, the classifier's finding count, and the sites its walk visited and judged
    When compare tallies the census and intersects it with each of those two sets
    Then it returns the census plus the visited and judged counts and their two fractions, every term of which is the same unit, the declaration site
    And the old admitted fraction, which divided conclusions by declarations and was quoted as coverage on every card, is deleted rather than repaired
    But each fraction is not-recorded when its denominator is empty, since nothing declared is not the same claim as nothing read
