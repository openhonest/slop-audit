Feature: state_sites — the shared name for one declaration site, so two independent walks can be compared
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: owner_name names the record a declaration sits in
    Given a record node, or nothing at all
    When owner_name is asked what to call it
    Then it gives back the declared name when the record has one
    And nothing at all is module scope, spelled as the empty string
    But a record with no name gets its byte offset, which only a walk already holding that node can produce, so an anonymous record can never be matched from a distance

  Scenario: enclosing_owner finds the nearest enclosing record of the kinds it was given
    Given a node somewhere in a parse tree and the list of node types that count as records
    When enclosing_owner climbs the parents
    Then it stops at the first ancestor whose type is on the list and returns that record's owner name
    And a node with no such ancestor is module scope, the empty string
    But it stops at the nearest record and not the outermost, so a class nested in a class keeps its own fields instead of handing them to the outer one

  Scenario: rust_impl_owner names the struct an impl block belongs to
    Given the impl node the classifier is standing on
    When rust_impl_owner reads the impl's type and peels the wrappers off it
    Then it returns the bare struct name, so that impl Store, impl<T> Store<T> and impl a::Store all agree with the struct's own declaration of Store
    And a wrapper it cannot unwrap by field falls back to the wrapper's first named child, which stops the peeling from stalling
    But an impl whose type is missing yields the empty string, and a struct whose impl lives in another file is never reached from here at all
