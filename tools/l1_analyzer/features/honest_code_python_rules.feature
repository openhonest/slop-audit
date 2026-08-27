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

  Scenario: imperative_validation finds a check the type already made
    Given a parsed source
    When imperative_validation reads its guards
    Then an isinstance check on a parameter the signature already types is distrust of your own contract
    But a check at a boundary, on a value that arrived untyped from outside, is where validation belongs

  Scenario: lifecycle_hooks finds behaviour parked where the reader does not look
    Given a parsed source
    When lifecycle_hooks reads its registrations
    Then an exit handler, a signal handler, an ORM callback or a mount effect puts behaviour somewhere nobody reads
    But a call at the place it happens is not a hook, however much work it does

  Scenario: mock_heavy_tests finds a test carrying the function's hidden dependencies
    Given a parsed test file
    When mock_heavy_tests counts the mocks in each test
    Then three or more in one test means the function under test has three hidden dependencies
    But one or two is ordinary isolation, and the count is a readout on the code rather than on the test

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

  Scenario: unscoped_resources finds a resource with a manual lifecycle
    Given a parsed source
    When unscoped_resources reads what is stored on self
    Then a connection or a handle assigned to self, in a class with no __enter__, is a leak waiting for an exception
    But a class that is a context manager has scoped the resource, which is the whole point of the rule

  # The reserved case. This module is a way station: its whole purpose is to hold clauses
  # until they can read every language, and no reading of any file decides when that is.
  @undecidable @not-implemented
  Scenario: undecidable when a clause here is ready to read the shared vocabulary
    Given a clause written against one language's parser
    When someone asks whether the shared vocabulary can carry it yet
    Then the answer is in the grammars of eight other languages, not in this file
    But nothing here can read those grammars to find out

