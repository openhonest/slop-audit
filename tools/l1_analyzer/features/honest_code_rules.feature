Feature: honest_code_rules — the nineteen clause checkers of L1.21
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  One function per Honest Code principle, in the Honest Framework's numbering. Every one
  of them is a pure function of a parsed source and returns the sites it found, so what a
  clause claims can be read at the site rather than taken on the score.

  Each names what it does NOT decide. That is the difference between a conformity number
  worth having and one that can be raised by looking away.

  Scenario: dispatch_chains finds an if/elif chain that selects behaviour by value
    Given a parsed source and the node vocabulary of the language it is written in
    When dispatch_chains reads its conditionals through that vocabulary
    Then a chain testing one name against two or more literals is a dispatch table written as control flow, in every language the vocabulary covers
    But a bounds check, a null guard and ordinary boolean logic are not, since flagging them would make the clause fire on every function that has a condition

  Scenario: data_classes finds a class whose whole job is holding data
    Given a parsed source
    When data_classes reads its class definitions
    Then a class whose body is an __init__ assigning parameters to self, plus accessors, is a dict with ceremony
    But a TypedDict, a Protocol, an Exception, an Enum and a class wrapping an external resource are not, because the rule allows exactly those

  Scenario: methods_wearing_a_class finds a method that only reads self
    Given a parsed source
    When methods_wearing_a_class reads each method's use of self
    Then a method that reaches self only for data it could have been passed is a function wearing a class
    But a method that writes self or calls another method is doing something a free function could not, so it is left alone

  Scenario: io_below_the_boundary finds I/O that has been pushed inward
    Given a parsed source
    When io_below_the_boundary reads the call graph and the effects of each function
    Then a function that performs I/O and is itself called by a sibling has put the I/O below the boundary
    And a declared boundary is reported as withheld rather than dropped, so the count of real suppressions is a fact rather than a guess made from the presence of a decorator
    But an entry point that performs I/O is the boundary, which is where the I/O is supposed to be

  Scenario: inheritance_for_reuse finds a class inheriting to share code
    Given a parsed source and the node vocabulary of the language it is written in
    When inheritance_for_reuse reads the base classes through that vocabulary
    Then a base that is not a declared shape or a framework requirement hides where behaviour comes from, in every language the vocabulary covers
    And an exception hierarchy is followed to its root, since a class deriving from one this file defines is exceptions all the way down
    But TypedDict, Protocol, Exception, Enum, NamedTuple and ABC declare a shape rather than share an implementation

  Scenario: client_side_state finds a second source of truth in the browser
    Given a parsed source in a browser language
    When client_side_state reads its imports and its storage calls
    Then a store library or localStorage holding a copy of server state is the second source of truth
    But the clause is not applicable to a file in a language with no DOM, which is a different answer from finding nothing

  Scenario: imperative_dom finds the DOM being driven by hand
    Given a parsed source in a browser language
    When imperative_dom reads its calls
    Then addEventListener, querySelector and innerHTML describe how, in a place the reader has to go and find
    But the clause is not applicable to a file with no DOM to drive

  Scenario: swallowed_exceptions finds an error going somewhere to be forgotten
    Given a parsed source
    When swallowed_exceptions reads its handlers
    Then a handler whose body only passes, or returns a stand-in, reports success for work that failed
    But a handler that re-raises, or that maps the error to a response at a boundary, is doing the thing the rule asks for

  Scenario: unmeasured_caches finds a cache standing in for a query
    Given a parsed source
    When unmeasured_caches reads its imports and its decorators
    Then a cache client or a memoising decorator is a second source of truth with an invalidation bug waiting
    But whether anyone profiled the query first is not readable from any file, so the clause reports the cache and says the measurement is what it cannot see

  Scenario: mock_heavy_tests finds a test carrying the function's hidden dependencies
    Given a parsed test file
    When mock_heavy_tests counts the mocks in each test
    Then three or more in one test means the function under test has three hidden dependencies
    But one or two is ordinary isolation, and the count is a readout on the code rather than on the test

  Scenario: imperative_validation finds a check the type already made
    Given a parsed source
    When imperative_validation reads its guards
    Then an isinstance check on a parameter the signature already types is distrust of your own contract
    But a check at a boundary, on a value that arrived untyped from outside, is where validation belongs

  Scenario: unscoped_resources finds a resource with a manual lifecycle
    Given a parsed source
    When unscoped_resources reads what is stored on self
    Then a connection or a handle assigned to self, in a class with no __enter__, is a leak waiting for an exception
    But a class that is a context manager has scoped the resource, which is the whole point of the rule

  Scenario: hidden_configuration finds behaviour depending on something no caller can see
    Given a parsed source
    When hidden_configuration reads what each function reaches for
    Then a module-level setting read inside a function makes its behaviour depend on something invisible at the call site
    But a constant that no code can change is not configuration, since nothing about it can differ between two calls

  Scenario: implicit_defaults finds a default that absorbs the caller's omission
    Given a parsed source
    When implicit_defaults reads each signature
    Then a literal default cannot be told from a caller who chose that value, and it manufactures an input region no call site exercises
    But a default that binds a collaborator is a dependency made visible in the signature, which is the opposite failure and is what rule 13 asks for

  Scenario: heavy_step_definitions finds a step carrying the architecture's hidden dependencies
    Given a parsed step-definition file
    When heavy_step_definitions measures each step's body
    Then a step needing thirty lines of setup is a readout on the code under test rather than on the test
    But a step that calls the function and checks the result is what a pure function makes possible

  Scenario: lifecycle_hooks finds behaviour parked where the reader does not look
    Given a parsed source
    When lifecycle_hooks reads its registrations
    Then an exit handler, a signal handler, an ORM callback or a mount effect puts behaviour somewhere nobody reads
    But a call at the place it happens is not a hook, however much work it does

  Scenario: strangler_migration records that nothing checked the migration
    Given any parsed source
    When strangler_migration is asked about it
    Then it reports that the clause was not decided, and why
    But it never returns a pass, because a rule nobody checked is not a rule that passed and this is the one clause no reader will ever decide

  Scenario: open_dispatch finds a table whose default re-opens the input space
    Given a parsed source
    When open_dispatch reads its lookups
    Then a get with a default files an input nobody wrote a rule for under an answer written for a different input
    But a subscript lets an unknown key raise, which records the gap in the table instead of hiding it

  Scenario: check_then_act finds a guard that is not a guard
    Given a parsed source
    When check_then_act reads each function's reads and writes of shared values
    Then a read of a shared value followed by a write to it lets two callers both believe they hold the thing
    But an await between the two makes the race certain rather than occasional, and the finding says which it found

  Scenario: _io_calls names the I/O one function performs
    Given a function definition
    When _io_calls reads its calls
    Then an unambiguous name counts on its own and an ambiguous one counts only with a receiver that names a client
    But reading the bare name reported this tool's own suffix table as I/O, because a dict lookup and an HTTP fetch are both spelled get

  Scenario: _line_of finds the first line holding a piece of text
    Given the file text and the string to find
    When _line_of scans the lines
    Then the first line carrying it comes back
    But a browser clause has no tree to read, so a line number found this way is the best locator available and the finding says what it names

  Scenario: _swallows says whether a handler body throws the error away
    Given the statements of one except handler
    When _swallows reads them
    Then a bare pass or a single return of a falsy stand-in is indistinguishable from a successful empty result
    But a returned message names the failure and hands it to a caller that discloses it, which is the opposite of a swallow

  Scenario: _bare_name names what a call is calling, without its receiver
    Given a call node
    When _bare_name reads it
    Then the last segment of the dotted name comes back
    But the receiver is dropped, so a caller that needs to tell two receivers apart has to read them separately

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

  Scenario: _is_literal says whether a default is a value or a bound collaborator
    Given the default expression of one parameter
    When _is_literal reads it
    Then a constant, a negated constant and an empty container are values that absorb the caller's omission
    But a name is a bound collaborator, which makes a dependency visible and is what rule 13 asks for

  Scenario: _turned_names names the module-level values some function writes
    Given a parsed source
    When _turned_names reads every function's writes
    Then a value somebody turns is configuration, since two callers can get different behaviour for a reason neither can see
    But a table nobody writes is a fact about the world, and flagging it would make clause 13 demand the opposite of clauses 1 and 18

  Scenario: _written_in names what one function reassigns or mutates
    Given a function definition
    When _written_in walks its assignments, its globals and its mutating calls
    Then a subscript assignment and an append are both writes to the container
    But a read is not, however deeply nested, because the clause is about who turns the knob

  Scenario: _turns_any says whether a function is one doing the turning
    Given a function and the names some function writes
    When _turns_any compares them
    Then the writer is not reported as a reader surprised by the write
    But it is still the reason every other function is reported, which is why the two are separated here

  Scenario: _first_line finds where a name is first read or written in a function
    Given a function, a name and the context to look for
    When _first_line walks the tree
    Then a write through a subscript counts as a write to the container
    But the line order is what the clause reasons about, and a tree walk is not source order, so only the first of each is taken

  Scenario: _mentions says whether a default was built from the key it stands in for
    Given the default expression of a lookup and the key expression beside it
    When _mentions compares them
    Then a default carrying the key records the gap, since the unknown key comes back visible as itself
    But a default that is a shared constant files the unknown input under an answer written for a different one, which is the whole of rule 18

  Scenario: _caught_names names the exceptions one handler catches
    Given an except handler, which may name one type, a tuple of them, or nothing
    When _caught_names reads it
    Then each name comes back without its module
    But a bare except names none, which is a different fact from naming a type this clause has no opinion about

  Scenario: _asserts_a_raise says whether a try body is asserting that its call raised
    Given the statements of one try block
    When _asserts_a_raise reads the last of them
    Then a statement that records a failure makes the handler beneath the success condition, since it runs only when the call did not raise
    But it cannot decide whether the recorded failure is the one the author meant, because a try ending in an unrelated append reads the same way

  Scenario: _local_exceptions names the classes this file defines that are exceptions
    Given the classes one file declares and the bases each names
    When _local_exceptions follows those bases to their root
    Then a class three levels down from Exception is still an exception
    But a base defined in another module cannot be followed, so a class deriving from one stays reported, which sends a reader to look rather than hiding it

  Scenario: _declares_a_boundary says whether a function is one of the project's own edges
    Given a function definition and its decorators
    When _declares_a_boundary reads what each decorator NAMES
    Then a declared edge is conforming rather than violating, since the rule is that I/O belongs at the boundary
    But a decorator merely carrying the word as data is not a declaration, which is the lesson clause 16 learned from a parametrize holding an exit handler

  @undecidable @not-implemented
  Scenario: undecidable whether a structure the clause allows was the right choice
    Given a class the rules permit because it wraps an external resource
    When someone asks whether it needed to be a class at all
    Then the clause records that the structure is permitted
    But nothing here reads intent, so whether the permission was earned stays a question for a reader

  Scenario: local_exception_roots names the classes this file derives from an exception
    Given a file defining an exception and three classes descending from it in turn
    When local_exception_roots follows each chain of bases to its root
    Then all four names come back, so a second-level exception is exceptions all the way down
    But a base defined in another module cannot be followed and is not counted a root

  Scenario: _calls_a_resource says whether a constructor opens something
    Given one constructor storing its parameters and one calling connect
    When _calls_a_resource reads the calls through the language's call vocabulary
    Then only the second is wrapping a resource, which the rule permits
    But a call this list does not name is not read as opening anything
