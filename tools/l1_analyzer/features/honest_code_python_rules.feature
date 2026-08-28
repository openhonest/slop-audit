Feature: Clauses this reader still reads through Python's own parser

  Every clause here is one the port has not reached. It reads the parsed Python tree, so it
  reports unreadable on every other language and says why. A clause moves out of this file
  when it learns to read the shared node vocabulary, and this file disappears when the last
  one has.

  Scenario: _bare_name names what a call is calling, without its receiver
    Given a call node
    When _bare_name reads it
    Then the last segment of the dotted name comes back
    But the receiver is dropped, so a caller that needs to tell two receivers apart has to read them separately

  Scenario: _first_line finds where a name is first read or written in a function
    Given a function, a name and the context to look for
    When _first_line walks the tree
    Then a write through a subscript counts as a write to the container
    But the line order is what the clause reasons about, and a tree walk is not source order, so only the first of each is taken

  Scenario: _is_test_file says whether a path holds tests
    Given a file path
    When _is_test_file reads its name and its directory
    Then the two test-scoped clauses know whether they have anything to read
    But a project naming its tests some other way is not recognised, and the clause then reports itself not applicable rather than clean

  Scenario: _module_level names what a module assigns at its top level
    Given a parsed source
    When _module_level reads its body
    Then each module-level name comes back with what it was assigned
    But an assignment inside a conditional at module level is read the same way, since a reader of the file sees one name either way

  Scenario: heavy_step_definitions finds a step carrying the architecture's hidden dependencies
    Given a parsed step-definition file
    When heavy_step_definitions measures each step's body
    Then a step needing thirty lines of setup is a readout on the code under test rather than on the test
    But a step that calls the function and checks the result is what a pure function makes possible

  Scenario: strangler_migration records that nothing checked the migration
    Given any parsed source
    When strangler_migration is asked about it
    Then it reports that the clause was not decided, and why
    But it never returns a pass, because a rule nobody checked is not a rule that passed and this is the one clause no reader will ever decide

  Scenario: unmeasured_caches finds a cache standing in for a query
    Given a parsed source
    When unmeasured_caches reads its imports and its decorators
    Then a cache client or a memoising decorator is a second source of truth with an invalidation bug waiting
    But whether anyone profiled the query first is not readable from any file, so the clause reports the cache and says the measurement is what it cannot see

  Scenario: undecidable when a clause here is ready to read the shared vocabulary
    Given a clause written against one language's parser
    When someone asks whether the shared vocabulary can carry it yet
    Then the answer is in the grammars of eight other languages, not in this file
    But nothing here can read those grammars to find out

