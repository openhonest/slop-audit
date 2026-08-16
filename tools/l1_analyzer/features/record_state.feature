Feature: record_state — the state a record declares inside itself, which no reference-following rule can reach
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _descend collects the descendants of a node without entering a nested record
    Given a node, the node types worth collecting, and the node types that end the walk
    When _descend walks the node's whole subtree
    Then it returns every descendant whose type is on the wanted list, in the order the walk met them
    And the walk turns back at any node whose type is on the stop list, so a record nested inside another keeps its own fields instead of having them charged to the outer record
    But the starting node itself is never stopped at, which is what lets a caller ask a record for its own fields while still stopping at its children

  Scenario: _by_attr indexes member accesses by the name they reach for
    Given the member-access nodes of one scope and the name of the field carrying the accessed name
    When _by_attr groups them
    Then it returns a lookup from each accessed name to every node that reaches for it
    And the index is built once per scope on purpose, because a header declaring a thousand fields would otherwise be rescanned once per field name, decoding the same text a million times

  Scenario: _py_class_body_bindings finds the names bound at the top level of a class body
    Given a class node
    When _py_class_body_bindings reads the class body's own statements
    Then it returns each bound name together with the identifier that binds it
    And a name bound inside a method is a local and never reaches here, because only the body's own statements are read
    But a bare annotation is kept alongside a name given a value, because the parser spells both the same way, and dropping annotations to exclude a shape declaration would also drop a data-class field that is a real slot

  Scenario: _py_receivers names the ways a class attribute can be reached inside its own class
    Given a class node
    When _py_receivers works out what a use of the attribute can be written through
    Then it returns the two conventional receiver names together with the class's own name
    And reaching an attribute through the class name is exactly the spelling that makes a class-body binding shared mutable state rather than a per-instance default
    But a class whose name cannot be read yields the two receivers alone

  Scenario: _python_class_body reports class-body state, minus what the receiver rule already claims
    Given a parse tree, the language spec, and a way to ask which state keys another rule already claimed for a record
    When _python_class_body walks each class, reads its body bindings, and matches them against the same-class member accesses
    Then it returns one slot per binding that something references, each carrying the declaration first in its reference list so a reader is sent to the declaration rather than to the first use
    And every binding walked is recorded as visited, including the ones handed over to the receiver rule and the ones nothing references, because a declaration read and declined is not a declaration nobody looked at
    But a binding the receiver rule already claimed produces no slot here, which is what stops one piece of state being published twice and inflating every count computed over findings

  Scenario: _c_field_name reads the identifier a C field declarator binds
    Given a declarator node, or nothing
    When _c_field_name unwraps the declarator layer by layer
    Then it returns the bare field name, so an array, a pointer and a function-pointer field each yield the one name they declare
    And only known declarator wrappers are unwrapped, rather than blindly taking the first named child, which would walk into an anonymous member's body and return a field of the wrong record
    But a node that is neither a field name nor a known wrapper yields nothing at all

  Scenario: _c_struct_field reports struct and union fields with the same-file uses that name them
    Given a parse tree, the language spec, and a way to ask which state keys another rule already claimed
    When _c_struct_field walks every struct and union, reads each field name off its declarator, and looks the name up among the file's member accesses
    Then it returns one slot per field name that something in the same file uses, and records every field declaration it walked as visited
    And a field name declared by two records in one file is reported once, against the record that declared it first, carrying both records' references, because a use says nothing about which record it belongs to and resolving that needs type inference this analyzer does not do
    But references are collected one file at a time, so a struct declared in a header and used in another translation unit yields no slot at all, which in C is the normal shape of a library rather than a corner case

  Scenario: field_decl_names lists the names one field declaration declares
    Given a field-declaration node
    When field_decl_names checks whether that kind of declaration names its slot directly
    Then a TypeScript field, a JavaScript field and a C-sharp property each give back the one name they carry
    And any other field declaration gives back one name per declarator nested inside it, because a single declaration can declare several slots at once
    But a declaration whose name cannot be read yields nothing rather than an invented name

  Scenario: _no_records stands for a language whose record fields need no rule of their own
    Given a parse tree, a language spec and the already-claimed lookup
    When _no_records is dispatched to
    Then it returns no slots and no visited declarations, and reads nothing at all
    And it exists so that a language whose fields are already reachable from a reference, or that has no record type, is named and dispatched to explicitly rather than falling through to a silent default
    But it ignores all three of its arguments, which is the whole of its behaviour

  Scenario: slots dispatches one file to the record rule its language asks for
    Given a parse tree, the language spec and a way to ask which state keys another rule already claimed
    When slots looks the language's record rule up and runs it
    Then it returns that rule's slots together with every record declaration the rule walked to find them
    And two outputs travel rather than one, because a declaration read and declined is not the same fact as a declaration nobody looked at, and the coverage number cannot tell them apart from a slot list alone
    But the rule is looked up strictly, so a language spec that names no record rule fails loudly instead of quietly reading no record fields for that language
