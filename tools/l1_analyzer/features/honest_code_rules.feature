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

  Scenario: swallowed_exceptions finds an error going somewhere to be forgotten
    Given a parsed source
    When swallowed_exceptions reads its handlers
    Then a handler whose body only passes, or returns a stand-in, reports success for work that failed
    But a handler that re-raises, or that maps the error to a response at a boundary, is doing the thing the rule asks for

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

  Scenario: _throws_it_away says whether a handler discards the failure
    Given one empty handler and one returning the message of the error it caught
    When _throws_it_away reads the body through the language's vocabulary
    Then only the first discards the failure
    But a body mentioning the caught error is disclosing it rather than hiding it

  Scenario: _guarded_body_asserts_a_raise says when the handler is the success condition
    Given a try body ending in a statement that records a failure
    When _guarded_body_asserts_a_raise reads the body the handler guards
    Then reaching the recorder is the defect and the handler beneath is correct
    But whether the recorded failure is the one the author meant is not readable here

  Scenario: _caught_text says what one handler catches
    Given a handler naming one exception type and one naming none
    When _caught_text reads the handler's children other than its body
    Then the first names its type and the second names nothing
    But a handler catching everything is the one this clause is least able to excuse

  Scenario: _caught_variable names what the handler binds the error to
    Given a handler binding the error and one binding nothing
    When _caught_variable takes the last identifier before the body
    Then the bound name comes back for the first and nothing for the second
    But all five grammars put it there whether they field it or not
