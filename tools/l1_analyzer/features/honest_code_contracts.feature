Feature: Three clauses about what a signature promises and what a caller may assume

  A mock stands in for a dependency the signature does not name. A runtime type test
  distrusts a type the signature already fixed. A resource on instance state hides a
  lifetime the signature never states.

  Split out of honest_code_rules when that file crossed a thousand lines and this tool's
  own god-file rule said so on the commit that pushed it over.

  Scenario: undecidable whether a contract the reader cannot see was actually kept
    Given a function whose receiver is named something other than the language's own word for it, a test named by an annotation rather than a prefix, or a mock built by a library this table does not name
    When one of these three clauses reads the file
    Then it records what it could read and states the bound in its own docstring, so a reader knows which cases the count passed over
    And the parse-tree shape around the case is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: imperative_validation finds a runtime type test on a parameter the signature already types
    Given a parsed source and its language's node vocabulary
    When imperative_validation collects each function's typed parameters and every runtime type test inside it
    Then it reports a test whose value is a parameter and whose type is the one that parameter declares, because re-checking a value the signature promised is distrust of your own contract
    And a parameter declaring one of the language's own scalars counts as fixed however the test spells the type it wants
    And a test on a value the signature left open, an Object, an any, an object or an empty interface, is left alone, because that is the check the declaration deliberately left to run
    And a language with no parameter type or no runtime type test is answered with nothing decided rather than an empty list, since an empty list would claim the file was read against this clause and found clean
    But a test for a type the parameter cannot hold is not counted, because an unreachable branch is a different defect from a redundant check and nothing here measures it

  Scenario: _declared_type_of gives the type a parameter declares, without the grammar's punctuation
    Given a parameter node, its language's vocabulary, and the source bytes
    When _declared_type_of reads the field naming the declared type
    Then it strips a leading colon and the space after it, because TypeScript hangs the annotation on the type and Python does not
    But it invents nothing when the field is absent, returning the empty string, which no declaration can equal

  Scenario: _parameter_name gives the name a typed parameter binds
    Given a parameter node, its language's vocabulary, and the source bytes
    When _parameter_name reads the field the vocabulary names
    Then it falls back to the first child where the vocabulary names no field, because Python's typed parameter hangs the name there with no field at all
    But it names no language, so the fallback is a fact recorded in the table rather than a special case in the reader

  Scenario: _type_tests_in collects every runtime type test inside one function
    Given a function node, its language's vocabulary, and the source bytes
    When _type_tests_in walks the function looking for both spellings of a type test
    Then it reports the value tested, the type tested for, and the line, for an operator form such as instanceof, is, or a type assertion
    And it reports the same three for a call form, whose first argument is the value and whose second is the type, which is how Python spells it
    But an operator form is counted only where the operator itself is one the vocabulary names, so an ordinary comparison sharing the same node type is not read as a type test

  Scenario: _call_arguments gives the argument nodes of a call
    Given a call node
    When _call_arguments reads the field holding its arguments
    Then it returns that node's children
    But it returns nothing when the call has no such field, rather than raising, because a grammar that hangs arguments elsewhere is a gap in the vocabulary and not a crash

  Scenario: unscoped_resources finds a resource held on instance state that the class never releases
    Given a parsed source and its language's node vocabulary
    When unscoped_resources reads each class, asks whether it declares the language's own release hook, and looks for an acquisition assigned to instance state
    Then it reports the class that holds a resource and declares no release hook, because the path that returns closes it and the path that raises does not
    And a class declaring that hook is left alone, since declaring one is doing what the rule asks and reporting it would punish the remedy
    And an ordinary value on instance state is not reported, because the rule is about a thing with a lifecycle rather than about instance state as such
    And a site reached twice, where a grammar nests one class node inside another as Ruby's does, is reported once, because the site is the finding
    But a language with no class to hold the resource is answered with nothing decided rather than an empty list, since C has none and Go's struct has no release hook here, defer scoping at the call site instead

  Scenario: _resource_calls gives every name that counts as acquiring a resource in one language
    Given a language's node vocabulary
    When _resource_calls joins the shared list of acquisitions to the language's own spellings
    Then it returns both, because C# names the same operation Connect where the shared list says connect and Java says getConnection
    But neither half owns the other, so adding a language's convention does not edit the shared list and vice versa

  Scenario: _instance_member_written gives the name of the instance state an assignment writes
    Given an assignment node, its language's vocabulary, and the source bytes
    When _instance_member_written reads the target and asks which of the two shapes it is
    Then it returns the member name where the target is a member access whose object is one of the language's receiver words
    And it returns the whole name where the target is instance state on its own, which is how Ruby writes an at-sign variable and reaches for no receiver at all
    But it returns the empty string for anything else, so an ordinary local assignment is not read as instance state

  Scenario: _scopes_its_own_resource says whether a class declares the language's own release hook
    Given a class node, its language's vocabulary, and the source bytes
    When _scopes_its_own_resource reads the name of each method the class declares
    Then it answers yes on the first one the vocabulary names as a release hook, whether that is Python's enter, Java's close or C#'s Dispose
    But it reads the names the table holds rather than any it knows, so adding a language means adding a row and not a branch

  Scenario: mock_heavy_tests finds a test standing on three or more mocks
    Given a parsed source, its file name, and its language's node vocabulary
    When mock_heavy_tests finds each test in the file and counts the mocks inside it
    Then it reports a test holding three or more, because the count is a readout on the code and three mocks means the function under test has three hidden dependencies
    And a test holding one or two is left alone, since that is ordinary isolation and firing there would report the practice the rule asks for
    And a file that is not a test is answered with nothing decided, because the count means nothing outside a test and an empty list would say the file was read and found clean
    And what a test file is called is asked of the scope module, the one place in this package that decides it, so a second copy here cannot drift from the first
    But a language this table gives no mock vocabulary, which is Go, Rust and C, is answered with nothing decided, and a test named by an annotation rather than a prefix is not found, since Java's Test and C#'s Fact sit on functions with any name at all

  Scenario: _test_bodies gives every test in a file, with the node holding its body
    Given a parsed source and its language's vocabulary
    When _test_bodies looks for both shapes a test takes
    Then it yields a named function whose name begins with one of the language's test prefixes, which is how Python, Java and C# write a test
    And it yields the call that takes the body as an argument, which is how JavaScript and Ruby write one, where the test has no name of its own
    But the block form yields the call and not the anonymous function inside it, so one body is not counted twice under two names

  Scenario: copied_constraints finds a hand-written check spelling out a bound the file already declares
    Given a parsed source and its language's node vocabulary
    When copied_constraints collects the bounds the file declares and looks for the same bound written out in a comparison
    Then it reports the comparison, because one half is enforced by the machinery and the other by a programmer and nothing keeps them equal
    And a bound only declared is left alone, since that is what the rule asks for and nobody wrote it twice
    And a bound only checked is left alone, because there is nothing for it to drift from and this rule is about copies
    And each copy is its own finding, since each can drift on its own
    And a bound declared somewhere this reader cannot see, a database column or a form field, is not read, which is the narrowest of the cases the principle covers
    But a language this table gives nowhere to declare a bound is answered with nothing decided, which is JavaScript, Ruby, Go, Rust and C

  Scenario: declared_bounds gives every bound this file declares for the machinery to enforce
    Given a parsed source and its language's vocabulary
    When declared_bounds reads the numbers inside each type annotation, Java annotation or C# attribute
    Then it returns those bounds, which are the ones the runtime, the type checker, the database or the browser enforces
    But the programmer only writes them down, which is the whole of the principle: they declare and the machinery enforces

  Scenario: _literals_under gives every literal in a subtree that could be a bound
    Given a node, its language's vocabulary, and the source bytes
    When _literals_under collects the literals the vocabulary names as able to carry a constraint
    Then it returns the numbers and the strings
    But it returns no boolean and no null, because counting those would read a test against nothing beside a nullable declaration as a copy of it
