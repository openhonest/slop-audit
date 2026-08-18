Feature: state_refs — which references actually denote a piece of state
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  @undecidable @not-implemented
  Scenario: undecidable a name re-exported under an alias
    Given a module that binds a name and a sibling that imports it under a different name with an as-clause
    When bound_to decides which references denote the state
    Then the aliased references are recorded as unread rather than silently excluded, because the alias is neither an import path nor a type nor a parameter and no rule here covers it
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: under_import_path recognises an identifier that names a package rather than a value
    Given an identifier node
    When _under_import_path walks up looking for an import or package construct
    Then it is true when the name binds nothing here, so an import of a package is not read as a reference to same-named state
    But the match is on the construct type containing the marker word, not on an exact type, so it catches each grammar's spelling

  Scenario: shadowing_scope finds the nearer function that binds the same name
    Given a reference, the state key and the language spec
    When _shadowing_scope walks up looking for a function whose parameters declare that name
    Then it returns that function, and the reference is then known to belong to the parameter rather than the state
    And only the parameter list is consulted, because a local assignment shadows by rules that diverge per language while a parameter is unambiguous everywhere

  Scenario: in_type_position tells a type name from a reference to state
    Given an identifier whose text matches a piece of state
    When _in_type_position asks whether it fills the grammar's own type field, walking out through any wrapping type expression
    Then it answers yes for the type half of `private static readonly Encoding Encoding = null`, so the declaration's type is not collected as a use of the field
    And it reads the `type` field rather than a per-language spelling, because that field name is the convention across every grammar in the table
    But it stops at the first ancestor that is not itself a type, so a name on the value side of a member access is left alone

  Scenario: bound_to keeps only the references that really denote the state
    Given a list of name matches, the state key and the language spec
    When _bound_to drops the ones under an import path and the ones a nearer parameter binds
    Then it returns the references that actually denote the state
    And both collection routes go through it, because a filter applied to one used to miss the other silently
