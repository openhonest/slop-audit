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
