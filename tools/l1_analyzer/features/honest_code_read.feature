Feature: honest_code_read — how L1.21 reads one source, and what it reads it through
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Every clause needs a source in front of it, and there are two ways to have one. A clause
  ported to the shared per-language node vocabulary reads a tree-sitter tree and can be
  decided for any language that vocabulary covers. A clause still written against Python's
  own parser reads an ast module and can be decided for Python alone.

  This module holds both, so a clause holds neither. It is a seam rather than a way to get
  a file under a line count: eighteen clauses are still to be ported and every one of them
  will read from here.

  Scenario: read_tree parses one source by the grammar for its language
    Given the text of a file and the language it is written in
    When read_tree parses it and picks up that language's node vocabulary
    Then a clause reads node types from the vocabulary rather than naming them, which is what lets one implementation serve every language it covers
    But an unknown language is refused rather than parsed as something else, since a tree read with the wrong grammar produces findings about a file nobody read

  Scenario: node_text gives back the source one node covers
    Given a node and the bytes it was parsed from
    When node_text reads the span
    Then the text between the node's start and end comes back
    But an absent node reads as nothing, which is what an optional field yields when the grammar did not fill it

  Scenario: walk lists every node under one node
    Given a node
    When walk descends through its children
    Then the node itself and everything beneath it come back
    But nothing about order is promised, because a clause that depends on tree-walk order is reading the walk rather than the code


  Scenario: _finding records one site a clause found
    Given the clause, the symbol, the line, what is wrong, what to do instead and what was not decided
    When _finding assembles them
    Then every field is stated by the caller
    But undecided is required rather than defaulted, because this module's own clause 14 flagged the default and was right


  Scenario: _functions lists every function in a source
    Given a parsed source
    When _functions walks the tree
    Then both plain and async definitions come back
    But a nested definition comes back too, since a closure that violates a clause violates it wherever it sits


  Scenario: _classes lists every class in a source
    Given a parsed source
    When _classes walks the tree
    Then each class definition comes back
    But nothing about whether a class was the right choice, which no reading of the source decides


  Scenario: _methods lists the functions defined directly in one class
    Given a class definition
    When _methods reads its body
    Then only the functions of that class body come back
    But a function nested inside one of them does not, since it belongs to the method rather than to the class


  Scenario: _called names every function a node calls
    Given any tree node
    When _called walks its calls
    Then each called name comes back once
    But a call on a computed target names nothing, because there is no name a clause could report


  Scenario: _base_names names the classes a definition inherits from
    Given a class definition
    When _base_names reads its bases
    Then a dotted or subscripted base comes back as its bare name
    But nothing here says whether the base belongs to a framework, which is the half clause 5 cannot decide

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # Whether a tree is the RIGHT reading of a file is not decidable here. A grammar accepts what it
  # accepts, and a file that parses cleanly under the wrong one produces a tree nobody should trust.
  # This module refuses a language it has no grammar for, which is a different guarantee.
  @undecidable @not-implemented
  Scenario: undecidable whether a tree that parsed is the right reading of the file
    Given a source that parsed without error under the grammar for its declared language
    When someone asks whether that grammar was the right one for this file
    Then the tree is handed on with the language it was read as
    But nothing here can tell a correct parse from a clean parse under the wrong grammar, since both produce a tree and neither complains

  Scenario: is_chain_arm says whether a branch is the continuation of another
    Given a branch node and the chain it may sit inside
    When _is_chain_arm looks at what encloses it
    Then only the head of a chain is read as a chain
    But without it a three-armed chain reports three times, once from each arm it is also the head of

  Scenario: chain_subjects names what each arm of one if chain compares
    Given the head of an if chain and the vocabulary of its language
    When chain_subjects walks the arms through the else branch
    Then a chain comparing one name against literals yields that name once per arm
    But an arm testing anything else yields nothing at all, since a chain with one ordinary condition in it is not a dispatch table

  Scenario: _chain_arms lists every arm of one if chain, whichever way the grammar spells it
    Given the head of an if chain and the vocabulary of its language
    When _chain_arms follows the arms
    Then the two shapes are read from structure rather than from a language name, since Python hangs its elif arms off the head and JavaScript nests each else-if inside the previous one's alternative
    But a reader keyed to either shape alone sees a one-armed chain in the other language and reports nothing

  Scenario: _equality_subject names the value one arm compares against a literal
    Given the test expression of one arm and the vocabulary of its language
    When _equality_subject reads the two sides
    Then an equality test between a name and a literal yields that name, in either order
    But anything else yields nothing, since a bounds check and a null guard are ordinary conditionals and flagging them would fire this clause on every function with a condition

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # Every clause here reads structure. None of them reads intent, and several rules turn on it:
  # whether a class wrapping a resource genuinely needed to be a class, whether a cache was
  # added after someone profiled the query, whether a conditional that dispatches on a value
  # has an axis of variation worth naming. The checkers report the shape and leave the intent
  # to a reader, rather than guessing at it and calling the guess a measurement.

  Scenario: base_names names the classes one definition inherits from
    Given a class definition and the vocabulary of its language
    When base_names reads the node the grammar puts the bases in
    Then Python's parenthesised argument list and JavaScript's heritage clause both yield the bare names
    But a base defined in another module is only a name here, which is the half this clause cannot decide

  Scenario: first_name reads a class's own name where the grammar does not field it
    Given a definition in a grammar that exposes no "name" field on the node
    When first_name walks the children for the first identifier
    Then the class's own name comes back
    But a definition whose name the grammar hides behind another node type yields nothing

  Scenario: class_nodes finds every class in the tree by this language's node types
    Given a file holding two class definitions
    When class_nodes reads the tree through the language's class types
    Then both come back, in Python's class_definition and JavaScript's class_declaration alike
    But a function that merely returns an object is not a class in either

  Scenario: method_nodes takes the definitions directly in a class body
    Given a class holding one method, which itself holds a closure
    When method_nodes reads the body's own children rather than walking
    Then one method comes back, because a function inside a method is not a method
    But Java's constructor is its own node type and is collected here alongside the rest

  Scenario: is_constructor says whether a definition runs when the class is instantiated
    Given a definition in a language that names its constructor and one that types it
    When is_constructor asks the vocabulary rather than spelling either
    Then Python's __init__ and Java's constructor_declaration both answer yes
    But a language with no constructor shape answers no for every definition it holds

  Scenario: reaches_receiver says whether anything inside reads self or this
    Given a method returning a field of the receiver
    When reaches_receiver walks it for a member access on this language's receiver
    Then the read is found
    But a method touching only its parameters reaches no receiver at all

  Scenario: writes_receiver says whether anything inside assigns the receiver or calls it
    Given one method assigning a field and one calling a sibling method
    When writes_receiver reads assignments and calls through the vocabulary
    Then both are work a free function taking the data could not do
    But reading a field is not, because the value could have been a parameter

  Scenario: _receiver_of names the member access whose object is this language's receiver
    Given a member access on self, one on this, and one on an ordinary name
    When _receiver_of checks the object against the language's receiver identifiers
    Then the first two are named and the third is not
    But a language with no receiver identifier names none of them

  Scenario: function_nodes finds every function in the tree by this language's node types
    Given a file holding a free function and a class holding one method
    When function_nodes reads the tree through the language's function types
    Then both come back, because a method is a function that sits in a class body
    But a call to a function is not a definition of one

  Scenario: module_level_bindings names what the top of the file binds
    Given a file binding one name by plain assignment and one through a declarator
    When module_level_bindings reads both shapes through the language's vocabulary
    Then each name comes back with the value it was bound to
    But a name bound inside a function is that function's own and is not top level

  Scenario: names_written_in names what a function rebinds, subscripts, or mutates
    Given one function rebinding a module name and one writing a key of a module table
    When names_written_in reads assignments, subscript writes, and mutating method calls
    Then both names come back, and a declaration of enclosing scope counts as a write
    But a function that only reads those names writes nothing

  Scenario: _written_name names the thing a write lands on
    Given a write to a plain name and a write to one key of a table
    When _written_name reaches through the subscript to the thing subscripted
    Then both report the name another function could mention
    But a write to something that is not a name at all reports nothing

  Scenario: _walk_own_scope visits what belongs to one scope and stops at the next
    Given a top-level function holding a local variable
    When _walk_own_scope records the definition and refuses to descend into its body
    Then the local stays the function's own
    But exempting the starting node would defeat the rule, because that node is the function

  Scenario: handler_body names the node holding one handler's own statements
    Given a handler in a grammar that fields its body and one in a grammar that does not
    When handler_body asks for the field and falls back to the language's block types
    Then both yield the statements the handler runs
    But this is the one shape these five grammars disagree about, so neither reading covers all

  Scenario: sends_failure_onward says whether anything under a node raises or re-raises
    Given one handler re-raising and one whose language spells raise as an ordinary call
    When sends_failure_onward reads the raise node types and the raise names together
    Then both are disclosing the failure rather than discarding it
    But reading only the node types would make every Ruby re-raise look like a swallow

  Scenario: is_absent_value says whether a value can be told from a successful empty result
    Given a return of nothing, a return of an empty list, and a return of a reason
    When is_absent_value reads it through the language's absent, container and literal types
    Then the first two are stand-ins a caller cannot tell from success
    But a truthy constant names the failure and hands it to a caller that discloses it

  Scenario: names_a_table_holds finds every name used as a value in a map literal
    Given a file declaring a dispatch table whose values are function names
    When names_a_table_holds reads the map literals through the language's vocabulary
    Then each function the table names comes back, because a function a table names is that table's row
    But a table built inside a function counts too, since scoping this to the top would exempt only some of them for a reason nobody could see

  Scenario: declares_only_signatures says whether a class lists signatures rather than code
    Given a class deriving from Protocol and an ordinary class beside it
    When declares_only_signatures reads the bases
    Then only the first is a list of signatures, where every method has the shape of every other by construction
    But the exemption is the Protocol and not the class, so two identical methods on a real class are still two methods somebody wrote twice

  Scenario: io_calls_in names the I/O one node performs
    Given a call by an unambiguous name, one on a receiver that only reaches outside, and one named a call at a time
    When io_calls_in reads all three through the language's vocabulary
    Then each is I/O and reports the name it was reached by
    But a call on a module whose other calls are pure is read one at a time, or os.getenv and os.path.join count too

  Scenario: called_names_in names every function one node calls
    Given a function calling two others by name
    When called_names_in takes the bare name at each call site
    Then both come back
    But a method on a receiver is named by its last segment, because that is what the call site says

  Scenario: names_handed_on names every bare name handed to a call
    Given a function passed to map by name rather than called
    When names_handed_on reads the arguments of each call
    Then that function is reached, because passing it by name calls it for every element
    But a literal argument names no function, so only a bare identifier counts

  Scenario: declares_a_boundary says whether a function calls itself one of the project's edges
    Given a decorated function and one whose name carries the prefix instead
    When declares_a_boundary reads the decorator's name and the function's own
    Then both declare, because a decorator is Python's spelling and most languages have none
    But the bare marker is not a prefix, or every project's own boundary decorator declares itself an edge

  Scenario: called_spelling gives what a call is called, reduced to one word
    Given a call node, its language's vocabulary, and the source bytes
    When called_spelling takes the text naming the function, drops any type arguments, and keeps the tail after the last separator
    Then Python's Mock, JavaScript's jest dot fn, Java's Mockito dot mock and C#'s Substitute dot For of a type all reduce to one word a table can hold
    But it applies no list of its own, so what the word means is the caller's question and not this function's

  Scenario: in_a_test_module says whether a node sits in a module of tests kept in the file it tests
    Given a node, its language's vocabulary, and the source bytes
    When in_a_test_module walks up from the node looking for a marked module
    Then it answers yes where an ancestor is preceded by a marker the vocabulary names, which is how Rust keeps its tests in the file they test
    And it reads the marker as a preceding sibling rather than a parent, the same shape a decorator takes, since searching each ancestor's text found the marker in the whole file and excluded the file's own code with its tests
    But a language that keeps its tests elsewhere names no marker, so nothing is excluded for it and a marker invented here would start hiding code

  Scenario: keys_bound_to_io gives every record key in a file whose value performs input or output
    Given a parsed source, its language's vocabulary, and the source bytes
    When keys_bound_to_io reads each record literal and asks what each value does
    Then it returns the keys whose value reaches outside the process
    And this is how some code names its edges, with a record carrying connect and write as fields, where a reader looking for an attribute access sees a function that calls nothing
    And it is the reading the dispatch-table clause already needed, applied to what a field does rather than to its name
    But it reads one file, so a record built in another module is not followed, and that bound is real rather than a choice

  Scenario: subscript_keys_called_in gives every literal key a node reads out of a record and calls
    Given a node, its language's vocabulary, and the source bytes
    When subscript_keys_called_in looks for a call whose target is a subscript
    Then it returns the literal key, which is the only thing naming what was reached
    But a subscript read without being called is left out, because reading a row is not doing what the row does
