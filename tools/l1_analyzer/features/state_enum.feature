Feature: state_enum — which declarations the classifier's reader walks, and what it makes of each one
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today every module rule here enumerates from the same closed list of
  # top-level declaration kinds, so a name bound inside a function body yields no site at all,
  # neither keyed nor declined, and this walk cannot tell it apart from a file that declares nothing.
  @undecidable @not-implemented
  Scenario: undecidable a name bound inside a function body
    Given a parsed file whose state is bound below the top level, inside a function body the candidate list never descends into
    When module_cands runs that language's module rule over the candidates
    Then it is recorded as unread rather than left absent from the site map, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _put records one site the walk reached, keeping position and the stronger answer
    Given the map being built, one declaration site and the key that site yields
    When _put records the visit
    Then it keeps the position the site was first seen at and the strongest answer given for it, so an admitting visit overwrites an earlier declining one
    And a site reached twice, as when one binding is written twice, makes one entry rather than two findings
    But a declining visit never overwrites an admission already recorded, because that would lose a finding the classifier did make

  Scenario: keys_of lists the state keys the walk admitted
    Given a map of declaration sites to the keys they yield
    When keys_of collects the non-empty keys
    Then it returns them in source order, each one once
    But two declarations yielding the same key are two spellings of one slot, so they collapse to a single key the classifier judges once

  Scenario: sites_of finds every declaration that yielded one key
    Given the map of sites to keys, and one state key
    When sites_of gathers every site whose key matches
    Then it returns all of them, because one verdict covers every declaration that yielded that key
    And crediting only one of them would report the others as unread
    But a key nothing yielded returns an empty set rather than raising


  # The candidate list comes from the shared shallow walk, so anything bound below a root child and one level under it is never enumerated here.
  Scenario: _py_module records every Python module binding the mutability rule was run over
    Given a parsed Python file and its configuration
    When _py_module asks the mutable-state rule which names it admits, then walks the same candidate list
    Then it returns one site per top-level binding, keyed for the admitted ones and left empty for the declined
    And this is the only place that can still say a type alias, an upper-case constant or a metadata name was read and ruled out rather than missed
    But a binding whose target is not a plain identifier, such as a subscript or a tuple, is skipped outright and reads as though nothing looked at it

  Scenario: _js_module declines a constant on the merits and admits the rest
    Given a parsed JavaScript or TypeScript file
    When _js_module reads each top-level declaration and its declarators
    Then it returns one site per declarator, keyed for a reassignable binding and declined for a constant
    And the constant is declined rather than skipped, having been read and ruled out because the binding cannot be reassigned
    But it can still hold a mutable object, which is why the census counts it and this walk does not

  Scenario: _rust_module admits only a mutable static
    Given a parsed Rust file
    When _rust_module reads the file's own static items and checks each for the mutability keyword
    Then it returns one site per static, keyed when it is mutable and declined when it is not
    But a constant is not a static item, so it never enters the candidate list and this walk cannot report having read it

  Scenario: _go_module admits every package-level variable
    Given a parsed Go file
    When _go_module reads the package-level variable declarations and their specifications
    Then it returns one site per named specification, every one of them keyed, since a package-level variable is reassignable by definition
    But a package-level constant is a different declaration kind, so it never becomes a candidate and the census does not count it either

  Scenario: _c_module admits every file-scope variable declaration
    Given a parsed C file
    When _c_module reads the file's own declarations, skipping type definitions
    Then it returns one site per declared variable, all of them keyed
    And nothing here reads the immutability qualifier, so a file-scope constant is admitted alongside the rest
    But a function declaration and a typedef declare no slot and never become candidates

  Scenario: _no_module declines a module scope three languages do not use here
    Given a parsed Java, C# or Ruby file
    When _no_module is asked for that language's module-scope candidates
    Then it returns nothing, those three relying on class scope in this prototype
    And it is named and dispatched to explicitly, so a specification that forgot to say which rule it wants raises instead of silently enumerating nothing

  Scenario: module_cands dispatches to the module rule the language specification names
    Given a parsed file, its language specification and its configuration
    When module_cands looks up the module rule named in the specification and runs it
    Then it returns every top-level binding that language's reader walks, with the key each one yields
    But the rule is subscripted rather than looked up with a fallback, so a specification nobody finished raises here

  Scenario: _field_decl_cands enumerates the slots one record declares for itself
    Given one record node and its language specification
    When _field_decl_cands finds the field declarations belonging to that record itself and reads the names each one declares
    Then it returns one site per declared slot, keyed by the language's receiver prefix joined to the field name
    And it never descends into a nested record, whose fields are enumerated against their own owner instead
    But one declaration naming several slots yields several sites, which is why the names come from the declarators and not from the declaration

  Scenario: _member_cands enumerates receiver-assigned attributes alongside declared fields
    Given one class node and its language specification
    When _member_cands finds the assignments whose target is an attribute of the receiver, then adds whatever fields the language also declares
    Then it returns both kinds of site, the receiver attributes keyed by the whole receiver expression, which is the text the reference walk sees
    But an assignment through anything other than the language's receiver names is not this class's state and is skipped

  Scenario: _self_usage_cands enumerates Rust state from its use rather than its declaration
    Given one implementation block and its language specification
    When _self_usage_cands collects every receiver-qualified field access inside it, reads and writes alike
    Then it returns one site per field touched, owned by the type the implementation block names
    And the fields are read from use because the declaration sits on a struct elsewhere, so the owner names agree only when struct and implementation share a file
    But a struct whose implementation lives in another file is honestly unvisited from here, and a field no method touches is never enumerated at all

  Scenario: _ivar_cands counts every mention of a Ruby instance variable as a visit
    Given one Ruby class or module node and its specification
    When _ivar_cands collects every instance variable mentioned inside it
    Then it returns one site per instance variable, a read counting as a visit exactly as a write does
    But the census counts only the ones this file assigns, so an instance variable this file merely reads drops out of the comparison rather than charging this file with another file's slot

  Scenario: _no_instance declines a class scope C and Go do not have
    Given a node in C or Go
    When _no_instance is asked for its instance-scope candidates
    Then it returns nothing, C keeping its state at file scope and in struct fields, and Go grouping its state by receiver type
    And both are read elsewhere in this module, so the empty answer is a routing decision rather than a gap in the reader

  Scenario: instance_cands dispatches to the instance rule the language specification names
    Given one record node and its language specification
    When instance_cands looks up the instance rule named in the specification and runs it
    Then it returns every declaration inside that record which the language's reader walks
    But the rule is subscripted, so a specification naming no instance rule raises rather than returning an empty reading that would read as a clean record

  Scenario: instance_keys gives the callers that need names only the admitted keys
    Given one record node and its language specification
    When instance_keys runs the full instance enumeration and keeps only the keys it admitted
    Then it returns the state keys that record yields, dropping the declined sites and the site positions with them
    And it exists for reference collection and for the record rules asking what another enumerator has already claimed

  Scenario: _go_type_name names the struct type behind a Go receiver
    Given the type node of a Go method receiver
    When _go_type_name unwraps a pointer receiver to the type behind it
    Then it returns the struct type's name
    But anything that is neither a pointer nor a plain type name returns the empty string, as does a missing node, and the method is then dropped

  Scenario: _go_receiver reads the type and the variable name off a Go method
    Given a Go method declaration
    When _go_receiver reads the single parameter of the receiver list
    Then it returns the receiver's type name and the variable name that method calls it by
    But a method whose receiver carries no parameter returns two empty strings and the caller skips it

  # A field the type never touches in any method is not enumerated at all, and reads as unvisited, which is the truth.
  Scenario: go_slots groups Go state by receiver type across all of that type's methods
    Given a parsed Go file
    When go_slots groups every method by its receiver type and collects the field selections each method makes through its own receiver variable
    Then it returns one slot per field touched, keyed by type name and field name so the key is stable across methods whose receivers are named differently
    And every slot is marked as having enumerable writers, unconditionally
    But a field no method of that type ever touches is never enumerated, and a method whose receiver type or variable could not be read is dropped before any of its fields are seen
