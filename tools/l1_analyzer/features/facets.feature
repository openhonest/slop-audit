Feature: facets — closeable facets and the Silence index for one module and its tests
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Umbra's core measurement, in Slop Audit. A repository panel cannot say which function in
  which module carries an unasserted branch; this takes the pair Umbra takes, the module
  and the test file that is supposed to hold evidence about it.

  Coverage records what RAN. Silence records evidence the suite LACKS. A branch that
  executed and was never asserted on is covered and silent at once, and only the second
  number says so.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A region reached only through a computed value is the standing one. `band(random.randint(1, 9))`
  # supplies some region and the source cannot say which, so the facet stays silent while the
  # suite may well be covering it. Watching the arguments at runtime would settle it and would
  # mean instrumenting every call the suite makes.
  @undecidable @not-implemented
  Scenario: undecidable which region a computed argument lands in
    Given a test that calls the audited function with a value assembled at runtime
    When the regions are attributed from the source
    Then that call closes nothing, because the value cannot be read
    And the facet stays silent, which understates the suite rather than overstating it
    But nothing here can tell a genuinely missing region from one covered by a computed value, so a silent region is a question and not a verdict

  Scenario: _annotation reads the bare name of a declared type
    Given a parameter or return annotation, or nothing at all
    When _annotation reads it
    Then a plain name, a subscripted generic and a string forward reference all yield the bare name
    But an undeclared position yields the empty string, which is what separates a domain from a silence

  Scenario: asserted_calls finds the functions whose result a test asserts on
    Given the parse tree of a test file
    When asserted_calls walks it
    Then a call inside an assert, or bound to a name the test later asserts about, counts as evidence
    But a bare call statement does not, since it proves the function runs and nothing about what it returns

  Scenario: expected_exceptions finds the functions a test expects to raise
    Given the parse tree of a test file
    When expected_exceptions looks for calls inside a raises block
    Then those functions have evidence about their exception paths
    But a call outside such a block does not, because only the block fails when nothing is raised

  Scenario: supplied_regions reads which boundary regions a test's literal arguments land in
    Given the parse tree of a test file
    When supplied_regions reads each call's literal arguments
    Then each is attributed to the region of its value, keyed by function and argument position
    But a computed argument is attributed to nothing, because guessing its region would count evidence nobody produced

  Scenario: _region_of names the boundary region one literal lands in
    Given a literal argument
    When _region_of reads it
    Then a number is zero, negative or positive, a string or container is empty or non-empty, and a bool is true or false
    But anything that is not a literal names no region

  Scenario: _called_name names the function a call invokes
    Given a call node
    When _called_name reads its callee
    Then a plain name and an attribute access both yield the name being called
    But a more complex callee yields nothing rather than a guess

  Scenario: _functions lists the functions of a parsed module
    Given a parsed module
    When _functions walks it
    Then every function definition is returned, nested ones included

  Scenario: _branch_facets records every reachable branch and whether coverage entered it
    Given a function and the lines coverage never reached
    When _branch_facets walks the function
    Then each branch is one facet, silent when its body-entry line was never executed

  Scenario: _region_facets records the boundary regions of each declared parameter
    Given a function and the regions the suite supplied
    When _region_facets reads its parameters
    Then each declared parameter contributes one facet per region of its type, silent unless the suite supplied a value there
    But an undeclared parameter contributes an undeclared domain instead, because that is closed by declaring a type and not by adding a test

  Scenario: _return_facet records a declared return contract the suite does not assert
    Given a function and the calls a test asserts on
    When _return_facet reads its return annotation
    Then a declared return type is one facet, silent when no test asserts the result
    But a function returning None declares no contract and contributes nothing

  Scenario: _exception_facets records every explicit raise
    Given a function and the calls a test expects to raise
    When _exception_facets walks the function
    Then each explicit raise is one facet, silent when no test expects it
    But a bare re-raise contributes nothing, since it is the same path as its cause

  Scenario: import_root finds the directory the module is importable from
    Given the path to a module
    When import_root walks up while a package marker is present
    Then it returns the directory the package itself sits in
    But running the suite from the module's own directory instead is what produced a null coverage reading on every real package, because the test's import could not resolve

  Scenario: _coverage runs the suite and reports what it reached
    Given a module and its test file
    When _coverage runs the suite under a branch-coverage run in a temporary data directory
    Then it returns the lines never reached, the percentage, and whether the suite succeeded
    But it returns no percentage when the run produced no data, which is a different absence from a suite that ran and covered nothing

  Scenario: audit reports every closeable facet and how many the suite leaves silent
    Given a module and the test file that should hold evidence about it
    When audit enumerates the facets and reads the coverage run
    Then it reports the facets, the silence index, and the coverage percentage beside each other
    But a module with no enumerable facet reports no index at all, because zero is the CLEAN end of this scale and a module nobody could read must not report as fully evidenced

  Scenario: bound_regions reads the literals a test file binds to names
    Given the parse tree of a test file
    When bound_regions reads its parametrize decorators and its plain assignments
    Then each name carries every region the literals bound to it land in, since a parametrised case list is a set of values for one name and every one is evidence
    But reading call sites alone reported a region silent on functions whose own tests pass it repeatedly, which pointed a reader at regions already covered

  Scenario: _parametrized reads the parameter names and regions one decorator supplies
    Given a decorator that may be a parametrize call
    When _parametrized reads its names and its case list
    Then both spellings are read, one name as a string and several as a comma-separated string or a tuple
    But a case whose value is not a literal contributes nothing rather than a guess

  Scenario: is_declared answers whether a parameter has a type at all
    Given the annotation node of a parameter, which may be absent
    When is_declared reads it
    Then only an absent annotation is undeclared, however the present one is spelled
    But _annotation used to answer this question as well as which type it was, and returned the empty string for each, so a dotted name or a union was filed as an undeclared domain and blamed the author for a gap in the reader

  Scenario: _names reads every name an assignment target binds
    Given an assignment target, which may be a name, a tuple, a list or neither
    When _names reads it
    Then a tuple target yields every name nested inside it
    But a target that binds no name, such as an attribute or a subscript, yields none

  Scenario: regions_of reads the regions one argument expression carries
    Given an argument expression and the table of names the test file binds
    When regions_of reads it
    Then a literal carries its own region and a bound name carries every region bound to it
    But it is module level rather than a closure, because a nested function cannot be called by a test and its own return contract was unassertable by construction

  Scenario: returned_regions reads the literals a test file hands back
    Given the parse tree of a test file
    When returned_regions reads what each of its functions returns or yields
    Then a function handing back a literal lends that region to whoever calls it
    But a factory returning something unreadable lends nothing, since a guess about where a computed value lands is not evidence

  Scenario: _fixtures names the functions pytest will inject by parameter name
    Given the parse tree of a test file
    When _fixtures reads the decorators
    Then only a decorated fixture lends its regions to a test parameter of the same name
    But a plain helper whose name collides with a parameter did not produce the parameter, so the collision is not evidence

