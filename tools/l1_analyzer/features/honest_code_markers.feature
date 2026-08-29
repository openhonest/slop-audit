Feature: Three clauses that read what is attached to a declaration

  A lifecycle hook, a cache and a step definition are each announced by a marker sitting on
  a function or a class, and two of them by a call that stands in for one. Reading the
  marker is the whole job, so the helpers that read one serve all three.

  Scenario: undecidable whether a marker this table does not name parks behaviour
    Given a decorator, annotation or attribute the vocabulary holds no name for
    When one of these three clauses reads the declaration it sits on
    Then the clause passes over it and states in its own docstring which names it holds, so a reader knows the list is a list rather than a judgment
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: lifecycle_hooks finds work parked where the reader does not look
    Given a parsed source and its language's node vocabulary
    When lifecycle_hooks looks for both shapes a hook takes, a call that registers a callback and a marker on a declaration
    Then it reports either one, because the call site says nothing and the sequence lives in the registration instead
    And a call at the place it happens is left alone, however much work it does
    And a marker is matched as a node and never as text, since reading the unparsed source found a test whose data was the words of a registration and reported it as one
    But a language this table gives no hook vocabulary is answered with nothing decided, which is Go, Rust, C, and Ruby, whose Rails callback is a bare call in a class body that needs more than this table holds to tell from an ordinary call

  Scenario: _marker_names gives the names a marker on a declaration is built from
    Given a marker node and the source bytes
    When _marker_names strips the punctuation each language wraps it in and splits the rest on dots
    Then Python's at-sign dotted decorator, Java's at-sign annotation and C#'s bracketed attribute all reduce to names a table can hold
    But it returns every part rather than only the last, so a name matches whether it was written bare or dotted

  Scenario: _declaration_named gives what the declaration under a marker is called
    Given a marker node, its language's vocabulary, and the source bytes
    When _declaration_named walks up to the first function or class holding the marker
    Then it returns that name, so the finding points at the thing that runs rather than at the marker
    But it falls back to the marker's own text where no named declaration holds it, rather than reporting an empty name

  Scenario: unmeasured_caches finds a cache library or a memoising marker
    Given a parsed source and its language's node vocabulary
    When unmeasured_caches reads each dependency the file brings in and each marker on a declaration
    Then it reports a cache library, because a cache is a second source of truth with an invalidation bug waiting
    And it reports a memoising marker and names the declaration it caches, rather than naming the marker
    And every finding carries the half it could not decide, since whether anyone profiled the query first is in no file and a silent finding would claim the whole rule was checked
    But a language this table gives no cache vocabulary is answered with nothing decided, which is C, whose dependency arrives as a header this rule cannot tell from any other

  Scenario: _dependency_names gives the identifiers a dependency declaration mentions
    Given a node bringing in a dependency and the source bytes
    When _dependency_names splits the node's text on everything that cannot be part of a name
    Then a library is found however the language spells the path around it, whether that is a dotted Java package, a quoted Go URL or a double-colon Rust path
    But it returns every identifier rather than choosing one, so the caller decides which of them it was looking for

  Scenario: _brings_in_a_dependency says whether a node pulls a library into the file
    Given a node, its language's vocabulary, and the source bytes
    When _brings_in_a_dependency checks the node against the declarations the vocabulary names and then against the calls that do the same job
    Then it answers yes for a declaration in every language that has one
    And it answers yes for a call the vocabulary names, which is how Ruby writes require, where a reader looking only for declarations finds no dependencies at all
    But it answers no for an ordinary call, because the call form is matched by name and not by shape

  Scenario: heavy_step_definitions finds a step carrying the setup the code should not need
    Given a parsed source and its language's node vocabulary
    When heavy_step_definitions measures the lines each step definition spans
    Then it reports a step longer than thirty lines, because step length is a readout on the architecture and a step needing that much setup means the code under test has hidden dependencies
    And a step of one or two lines is left alone, since calling the thing and checking the result is the shape the rule asks for
    And a file holding no step definitions is answered with nothing decided, because it was not measured against a rule about step definitions and saying it passed would be a claim nobody made
    But it reads the secondary signal only, the length, and never the rule itself, which is a bijection between functions and scenarios and needs the feature files as well as the source

  Scenario: _step_definitions gives every step in a file, with the node holding its body
    Given a parsed source and its language's vocabulary
    When _step_definitions looks for both shapes a step takes
    Then it yields the declaration a marker sits on, which is how Python, Java and C# write a step
    And it yields the call that takes the body as an argument, which is how JavaScript and Ruby write one, where the step has no declaration to mark at all
    But the call form yields the call and not the anonymous function inside it, so the span measured is the step a reader sees

  Scenario: _never_runs says whether a step is handed back to the runner unstarted
    Given a step definition node and its language's vocabulary
    When _never_runs asks whether the step is asynchronous in a language whose runner throws away what a step returns
    Then it answers yes, because the runner calls the step, gets a coroutine back and drops it, so the body never executes
    And the language decides it, since every other runner waits for what a step returns and reporting an async step there would ask an author to break working tests
    But it says nothing about length, because a step that never runs is not a step that is too long, and two findings on one site would send a reader to shorten a function that does nothing

  Scenario: _declaration_marked gives the declaration a marker sits on, as a node
    Given a marker node and its language's vocabulary
    When _declaration_marked looks beside the marker as well as above it
    Then it returns the function or class the marker belongs to, so two markers on one declaration lead to the same node
    And it looks at siblings because Python wraps a decorator and its function together and makes them siblings, where walking up alone finds the wrapper and never the function
    And it walks upward as well because Java and C# nest the marker inside the declaration, where that is the only thing that works
    But it returns nothing where no declaration holds the marker, rather than naming something that is not one

  Scenario: _binds_scenarios says whether a file is bound to the scenarios its steps serve
    Given a parsed source, its language's vocabulary, and the source bytes
    When _binds_scenarios looks for the call or the marker that binds a file to a feature
    Then it answers yes for either spelling, since both bind and a rule knowing one would go quiet on half of them
    And this is what tells a step file from a file that merely carries a decorator of the same name, because a property-based testing library spells its decorator the same way and awaits what it calls
    And an adopter reported that false positive and found, writing it up, that their own gate avoided it only by looking in one directory
    But a directory name is a convention where a binding is the thing itself, which is why this reads the binding

  Scenario: statements_in gives how much a step actually does, in statements rather than lines
    Given a step definition node and its language's vocabulary
    When statements_in counts what each block holds, passing over comments and a bare string standing alone
    Then it returns the work the step does, which is what setup means
    And a docstring does not count, because an adopter measured eight of their sites and six were already under the threshold in code alone, one of them eighteen statements carrying a sixteen-line docstring that recorded a defect their suite had paid for
    And the number told them to delete that explanation, which is the opposite of what this family of rules asks for
    But a call spread over four lines counts once, so a number that used to move when somebody reformatted was measuring the formatter
