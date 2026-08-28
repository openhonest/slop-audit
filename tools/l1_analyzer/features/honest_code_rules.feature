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

  Scenario: open_dispatch finds a table whose default re-opens the input space
    Given a parsed source
    When open_dispatch reads its lookups
    Then a get with a default files an input nobody wrote a rule for under an answer written for a different input
    But a subscript lets an unknown key raise, which records the gap in the table instead of hiding it

  Scenario: _line_of finds the first line holding a piece of text
    Given the file text and the string to find
    When _line_of scans the lines
    Then the first line carrying it comes back
    But a browser clause has no tree to read, so a line number found this way is the best locator available and the finding says what it names

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

  Scenario: _default_of names the value a parameter falls back to
    Given one parameter carrying a default and one declaring none
    When _default_of takes the named child after the = token
    Then the default comes back for the first and nothing for the second
    But a grammar using one node type for every parameter is told apart by the token alone

  Scenario: _is_literal_node says whether a default is a value or a bound collaborator
    Given a default of 30, one of [], and one calling default_clock()
    When _is_literal_node reads it through the language's literal and container types
    Then the first two are values nobody chose
    But the third is a dependency made visible in the signature, which rule 13 asks for

  Scenario: _is_table says whether a module-level binding holds a dispatch table
    Given one name bound to a map literal and one bound to a number
    When _is_table reads the value through the language's container literal types
    Then only the map is a table whose rules this file wrote
    But a table built by a call rather than written as a literal is not read here

  Scenario: _fallback_lookup names the table, key and fallback of one lookup
    Given a lookup passing the fallback as an argument and one putting it to the right
    When _fallback_lookup reads both spellings through the language's vocabulary
    Then each yields the same three things, and the clause itself names neither spelling
    But an ordinary subscript supplies no fallback and yields nothing

  Scenario: functions_of_one_shape finds functions that are one function with other words
    Given two generators differing only in a table name and a keyword
    When functions_of_one_shape erases every name and quoted string and compares what is left
    Then both leave the same shape and the pair is reported at the earlier of the two
    But two functions doing genuinely different work leave different shapes and stay quiet

  Scenario: check_then_act finds a guard that is not a guard
    Given a parsed source
    When check_then_act reads each function's reads and writes of shared values
    Then a read of a shared value followed by a write to it lets two callers both believe they hold the thing
    But an await between the two makes the race certain rather than occasional, and the finding says which it found

  Scenario: _first_plain_read names the line a function first reads a shared name
    Given a function that checks a shared table and then writes a key of it
    When _first_plain_read looks for the name without a subscript on the left of an assignment
    Then the line of the check comes back
    But the write's own subscript is not counted, or every write would be its own race

  Scenario: _first_keyed_write names the line a function first writes a key
    Given the same function
    When _first_keyed_write looks for the name being subscripted on the left of an assignment
    Then the line of the write comes back
    But a read of a key is not a write, however it is spelled

  Scenario: _is_keyed_write_target says whether a name is being written through a key
    Given a name inside a subscript
    When _is_keyed_write_target checks whether that subscript is the assignment's left side
    Then only a write reports true
    But the comparison is by equality, because the same node comes back from an accessor as a distinct object


  Scenario: _switch_tables finds a match or switch selecting behaviour by literal
    Given a match on three literal cases and a match that destructures a mapping
    When _switch_tables reads both through the language's switch vocabulary
    Then the first is a table written as syntax and is reported
    But the second is doing what no dict lookup can, and reporting it would ask an author to throw away the construct

  Scenario: _tests_a_literal says whether one case matches a value or pulls a shape apart
    Given a case naming a string and a case binding the parts of a mapping
    When _tests_a_literal reads each pattern for a literal and for destructuring
    Then only the first tests a value
    But a default arm counts as a literal case, because it names no shape and a table has the same thing in its lookup failing
