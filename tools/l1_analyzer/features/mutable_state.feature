Feature: mutable_state — L1.18, the share of functions that reference unbounded external mutable state
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the candidate walk reads a root child and one level below it, so a
  # binding made inside a function body never becomes a name, and the closure that mutates it
  # is counted in the denominator as a function that touched no state at all.
  @undecidable @not-implemented
  Scenario: undecidable a mutable binding declared inside a function and captured by a closure
    Given a file whose only mutable state is a function-local accumulator that a nested closure rebinds, holds captured, or carries as a default argument
    When analyze_mutable_state parses the file and looks for its module mutable names
    Then it is recorded as unread rather than scored zero percent under the healthy band, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _py_is_type_expression recognises a right-hand side that is nothing but a type
    Given the right-hand side of a Python module-level binding
    When _py_is_type_expression asks whether it names a type and nothing else
    Then it answers yes for a bare name, a dotted name, a subscripted name, and a union of those, recursing into both sides of a union
    But a call, a container literal or anything else answers no

  # It cannot tell a type alias from an alias of a value, so binding one name to another is dropped as though it were a type.
  Scenario: _py_is_type_alias drops a binding that only names a type
    Given a Python module-level binding and its right-hand side
    When _py_is_type_alias checks the annotation for the alias marker and then the right-hand side for a pure type expression
    Then it answers yes for either, and the binding leaves the mutable set
    But binding one name to another name, or to a dotted attribute, satisfies the same test, so aliasing a value at module scope is silently excused as a type alias

  Scenario: _py_is_empty_container recognises an accumulator seed
    Given the right-hand side of a Python binding
    When _py_is_empty_container looks for the empty form of a mutable container
    Then it answers yes for an empty dictionary or list literal, and for a no-argument call to one of the eight named mutable container constructors
    But an immutable container answers no, because it cannot accumulate, and so does a container seeded with contents already in it

  # An upper-case name is a constant unless it is seeded EMPTY, so a pre-filled upper-case dictionary that later grows is never counted.
  Scenario: _module_mutables_python decides which Python module bindings are state
    Given the candidate module-level bindings of one Python file and the language's receiver keyword
    When _module_mutables_python reads each binding's name from the assignment's own left-hand field
    Then it returns every lower-case binding as mutable state, and an upper-case one only when it is seeded with an empty container
    But it skips a target that is not a plain identifier, skips the double-underscore metadata names, skips type aliases, and never reads a string literal or an annotation tail as though it were source

  Scenario: _module_mutables_by_specifier keeps only the declarations that say they are mutable
    Given the candidate top-level declarations of one Rust file
    When _module_mutables_by_specifier looks for the mutability keyword among each declaration's own children
    Then it returns the names of only those declarations, read from the declaration's identifier child so the type token is never mistaken for the name
    But a constant and a plain immutable static are excluded on the merits, and a declaration carrying the keyword with no identifier child yields nothing

  Scenario: _text reads the source text one node spans
    Given any parse-tree node
    When _text decodes the bytes that node covers
    Then it returns that node's source text, replacing anything that will not decode rather than failing on it
    But a node carrying no text at all returns the empty string

  Scenario: _deep_nodes collects nodes of given kinds at any depth
    Given a parse-tree root and the node kinds wanted
    When _deep_nodes walks the whole tree in source order
    Then it returns every node of those kinds however deeply it sits
    But it is used for record fields only, because running it over a language's whole assignment vocabulary would harvest function locals and report them as module state

  Scenario: _declared_modifiers reads the modifier words on one field declaration
    Given one field declaration from Java or C#
    When _declared_modifiers collects the modifier children and splits their text on whitespace
    Then it returns the set of modifier words on that declaration, reading both the language that groups them into one node and the language that repeats a node per word
    But a property expressed as an annotation rather than a keyword is not among them

  # The C# configuration lists field declarations only, so an auto-property, which holds state as surely as a field does, is invisible here.
  Scenario: _module_mutables_class_fields treats a non-final field as the state of a Java or C# file
    Given a parsed Java or C# file and its language configuration
    When _module_mutables_class_fields walks to any depth for field declarations only and reads each one's declared modifiers
    Then it returns the names of the fields not declared immutable, taken from the declarators so one declaration of several slots yields several names
    And mutability is read from the keyword the source already carries, never guessed from the name's casing
    But the walk never covers the wider assignment vocabulary, which is what keeps method locals out, and it never reaches a C# property, so state written with accessors is not counted at all

  # A declaration with no initialiser is invisible: the line must contain an equals sign, so an uninitialised package-level variable never enters the set.
  Scenario: _module_mutables_text guesses the mutable bindings of the five text-scanned languages
    Given a parsed file in one of the text-scanned languages and that language's own immutability keywords
    When _module_mutables_text splits each candidate declaration's lines at the first equals sign and takes the last word before it
    Then it returns the names on lines that assign something and carry none of that language's immutability keywords
    And the keywords are read straight from the language with no shared default, which is what used to let one language's keyword immunise another's
    But a declaration written without an initialiser has no equals sign and is never seen at all, and an all-upper-case name is read as a constant whatever it holds

  # Candidates come from the shallow top-level walk only, so a function-local accumulator mutated by a nested closure never becomes a candidate.
  Scenario: _module_mutables_python_scan runs the Python rule over the top-level candidates
    Given a parsed Python file and its configuration
    When _module_mutables_python_scan collects the shallow candidates and applies the Python rule to them
    Then it returns the module-level names L1.18 treats as mutable state
    But it looks no deeper than a root child and one level below, so an accumulator declared inside a function and mutated by a closure beside it is never a candidate, contributes no name, and leaves that closure reading as though it touched no state at all

  Scenario: _module_mutables_specifier_scan runs the Rust rule over the top-level candidates
    Given a parsed Rust file and its configuration
    When _module_mutables_specifier_scan collects the shallow candidates and applies the mutability-keyword rule
    Then it returns the mutable statics of that file
    But it uses the same shallow candidate walk, so a mutable static declared inside a nested module block is out of its reach

  Scenario: shallow_candidates defines which declarations the module scan ever considers
    Given a parse-tree root and the declaration kinds that count as an assignment in this language
    When shallow_candidates reads the root's own children and one level below them
    Then it returns those declarations, the single wrapper level being what reaches a Python binding nested inside its own statement
    And the state enumeration imports the same list, so a declaration a rule read and declined can be told apart from one nobody walked
    But nothing inside a function, a class body or any deeper block is ever a candidate

  Scenario: _find_module_mutable_names dispatches to the scan its language declares
    Given a parsed file and its language configuration
    When _find_module_mutable_names looks up the scan that language names and runs it
    Then it returns that language's set of names L1.18 treats as external mutable state, with class fields standing in for module scope in Java and C#
    But a language whose configuration names no scan raises here, rather than falling through to a text heuristic nobody chose for it

  Scenario: _count_mutable_refs counts one function body's references to state it cannot bound
    Given a function body, the module-level mutable names, the names denoting the enclosing instance and the state the classifier managed to bound
    When _count_mutable_refs walks every node of the body against its four rules
    Then it returns how many references to unbounded outside state it saw, counting receiver-prefixed access, the instance and global variable node kinds, bare identifiers naming module state, and the raw text patterns
    And state the classifier bounded is subtracted, so a read keyed by a literal against a closed set no longer scores the same as an unbounded accumulator
    But one node can satisfy several rules and be charged several times, and the raw text patterns match any node whose text merely contains them, so a single such occurrence inside a body is charged once for every node enclosing it

  Scenario: _bounded_state_keys asks the classifier which state in this file has a countable reaching-set
    Given a parsed file, its repository-relative path, its language and the repository's immutable constructors
    When _bounded_state_keys runs the finite-testability classifier over the file and reads its findings
    Then it returns the keys whose verdict was neutral, which drive a decision, and whose partition was actually counted, all three conditions being required
    And state called neutral only because nothing branches on it is excluded, its partition being empty rather than finite
    But Go keys its state by type name while this walk sees the receiver name, so no Go reference is ever recognised as bounded and Go keeps its uncorrected, higher reading

  Scenario: _receiver_names works out what names the enclosing instance in this function
    Given one function node and its language configuration
    When _receiver_names asks whether the language has a fixed receiver keyword
    Then it returns that fixed keyword set where one exists, and otherwise parses the identifiers out of a Go method's receiver list
    But a Go plain function has no receiver list and gets an empty set, so nothing inside it can be read as instance access

  Scenario: _count_file_functions tallies one file's functions and its offenders
    Given a parsed file, the module mutable names and the bounded state
    When _count_file_functions walks the file for functions and counts the references inside each one's body
    Then it returns the total number of functions and how many of them touched unbounded outside state
    And no function is excluded from the denominator, the promised input and output boundary exclusion having been dropped rather than faked
    But a function whose body is not one of the recognised body node kinds is counted in the total and can never be counted as an offender

  Scenario: _parsed_roots reads and parses the production source once for every caller
    Given a repository, a language and its configuration
    When _parsed_roots reads every production file of that language and parses each one
    Then it returns the parse trees with their repository-relative paths, plus the number of files it could not read
    And one reader serves the ratio and both name listings, so the three cannot drift into scanning different file sets
    But test code, vendored code and everything else outside the production scope is never parsed here

  Scenario: _immutable_ctors_for gathers the constructors the classifier needs before it can resolve a constant
    Given a language and the already-parsed files of the repository
    When _immutable_ctors_for collects the repository's immutable constructors
    Then it returns them for Python and an empty set for every other language, which is what the classifier itself does
    And it takes the whole repository at once, because a constant built by a function defined in another file cannot be resolved from one file alone

  # With no function found anywhere, the ratio is zero and the band is Healthy: an empty denominator publishes the best score on the scale.
  Scenario: analyze_mutable_state publishes L1.18 over the whole repository
    Given a repository and a language
    When analyze_mutable_state parses the production source, finds each file's mutable names and bounded state, and counts the functions touching the rest
    Then it returns the percentage of functions referencing unbounded external mutable state, its band, and the two counts behind it
    And the figure is inflated by the whole input and output layer of every codebase it measures, because the boundary exclusion is gone and the canon row says so
    But a language with no configuration returns n/a, while a repository in which no function was found at all returns zero percent under the healthy band, over an empty denominator

  # The function's name is read from a name field, which a C function definition does not carry.
  Scenario: _file_mutable_names names the offending functions in one file
    Given a parsed file, the module mutable names and the bounded state
    When _file_mutable_names applies the same reference test as the count and keeps the names instead of a tally
    Then it returns the names of the functions in that file that touch unbounded outside state
    But it reads the name from the grammar's name field, and a C function definition binds its name through a declarator instead, so C reports a ratio with an empty list of culprits, and any function with no name field of its own, such as an anonymous arrow function, drops out the same way

  Scenario: mutable_function_names lists L1.18's culprits across the repository
    Given a repository and a language
    When mutable_function_names repeats the whole indicator walk and collects the names instead of the counts
    Then it returns the name of every function the indicator counts, in file order
    And it is additive and read-only, sharing the indicator's own reference test, so it can never move the value or the band
    But an unconfigured language returns an empty list, which reads exactly like a repository with no culprits

  Scenario: module_mutable_names lists the module bindings L1.18 calls mutable
    Given a repository and a language
    When module_mutable_names parses every production file and applies the module scan to each
    Then it returns the union of those names, a binding being a bound literal exactly when it is absent from the set
    But it discards the count of unreadable files rather than disclosing it, and an unconfigured language returns an empty set that reads exactly like a repository with no mutable bindings
