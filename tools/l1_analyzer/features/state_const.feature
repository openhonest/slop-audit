Feature: state_const — whether a declaration settles a state at one value
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  @undecidable @not-implemented
  Scenario: undecidable a constant whose initialiser is another constant
    Given a declaration marked immutable whose right-hand side names a second declared constant rather than a literal
    When declared_constant asks whether the value is a literal
    Then the chain is recorded as unread rather than settled, because following one constant to another is a walk this module does not do and answering no here calls a settled state unsettled
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: declared_constant asks whether the declaration settles the state at one value
    Given every reference to a state and the language's immutability modifiers
    When _declared_constant looks for a modifier on the declaration and a literal on the right of it
    Then it answers yes only when BOTH hold, because a modifier alone buys binding immutability and not value immutability
    And it reads a modifier that is a grandchild as well as a child, since Java gathers its modifiers into their own node and C# does not
    But a language declaring no modifiers answers no for every state, which is the behaviour it had before the rule existed

  Scenario: literal_initialiser checks that every value a declaration binds is a literal
    Given a declaration node and the language's literal and binding vocabularies
    When _literal_initialiser collects the value bound to each name in it
    Then it answers yes only when there is at least one value and every one of them is a literal
    But a declaration binding no value at all answers no, because this rule reads what was written and nothing was

  Scenario: rhs_is_immutable decides whether an assigned value can never change after it is built
    Given the right-hand side of an assignment and the names of the repository's immutable constructors
    When _rhs_is_immutable accepts a literal, a tuple, a known immutable wrapper, or a call to one of those constructors
    Then it is true for a value no callee can mutate
    But a missing right-hand side, and anything else at all, is not accepted

  Scenario: returns_immutable decides whether a function only ever hands back immutable values
    Given a function's parse tree
    When _returns_immutable requires every return in it to carry an immutable value
    Then it is true only when the function is a constructor of constants, which lets a declared table resolve on the evidence
    And a function with no return at all is not accepted, so the absence of returns is never read as a promise
    But a bare return with no value also fails, since there is no value to prove immutable

  Scenario: collect_immutable_ctors names the repository's constructors of immutable values
    Given the parse tree of one file
    When _collect_immutable_ctors keeps every function whose returns are all immutable
    Then it returns their names, which a one-level follow then uses to resolve a constant built by one of them
    But it matches Python's spelling of a function definition only, so no other language contributes names

  Scenario: reaches_decision decides whether any reference to the state is consumed at all
    Given every reference to one piece of state and the language spec
    When _reaches_decision skips the references that are returned and the ones that are written to
    Then it is true as soon as one reference is left, meaning the state is read somewhere that could turn on it
    But a state that is only bound and only returned reaches no decision, and an empty reference list reaches none either

  Scenario: immutable_const_verdict clears a state that is a constant with a one-value domain
    Given every reference, the repository's immutable constructors and the language spec
    When _immutable_const_verdict requires exactly one plain assignment from an immutable construction, with no rebinding, no keyed store, no call and no mutating method
    Then it returns neutral together with whether the constant reaches a decision
    But any one of the four disqualifiers, or a count of assignments other than one, returns nothing and the ordinary classification runs instead
