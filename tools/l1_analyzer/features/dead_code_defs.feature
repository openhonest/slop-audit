Feature: dead_code_defs — the per-language definition collectors that route every name a scan cannot settle to undecidable
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. This module has an honest channel already - the undecidable status, with a
  # named reason - and uses it well for a decorator, an export or an external linkage. It has no
  # channel at all for a node whose type reaches no branch of a collector's dispatch. Every
  # collector is handed src bytes it never reads and facts it mostly ignores, _ruby never reads
  # ruby_metaprogramming, and a name the chain does not name is collected as nothing: not a
  # candidate, not undecidable, not excluded, and absent from the disclosure that counts them.
  @undecidable @not-implemented
  Scenario: undecidable a top-level declaration whose node type reaches no branch of the collector
    Given a source file declaring a name through a construct no collector's dispatch chain names, such as a Ruby define_method call at the top level or a C declarator whose wrappers yield no identifier
    When the collector for that language walks the top-level children and the node matches no branch
    Then it is recorded as unread rather than dropped from the definition list, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _text reads the source text of one syntax node
    Given a syntax node, or nothing at all
    When _text decodes the node's bytes
    Then it returns the text as written in the source
    But a missing node, and a node carrying no text, both return an empty string instead of failing

  Scenario: _named_child_of_type finds the first child of a wanted kind
    Given a node and the child types wanted
    When _named_child_of_type scans the node's named children in order
    Then it returns the first child whose type is one of them
    But it looks exactly one level deep, and returns nothing when no child matches

  Scenario: _mk assembles one definition record with everything the classifier needs
    Given the name node, the whole item, its kind, its status and the reason for that status
    When _mk builds the record
    Then it returns the name, the kind, the first and last line counted from one, and the item's byte span
    And it records the byte offset of the name token itself, which is what lets the reference scan skip a definition's own site and not count it as a use

  Scenario: _python_all_exports reads a module's declared public surface
    Given a parsed Python module
    When _python_all_exports looks through the top-level statements for an __all__ assignment
    Then it returns the names listed there with their quotes stripped, because a published name is reachable from outside the tree
    But it answers from the first __all__ it meets, and an assignment built any way other than a literal list of strings yields an empty set

  Scenario: _python collects a Python module's top-level definitions with the verdict the language forces
    Given a parsed Python module and the repository facts
    When _python walks the module's top-level functions, classes and simple constant assignments
    Then a dunder name or a test-runner name is excluded, a decorated definition or an __all__ export is undecidable, and everything else is a candidate
    And a decorated definition is undecidable because a decorator can register the name with a framework no scan follows
    But only top-level statements are collected, so a method inside a class is never judged here at all

  Scenario: _rust_attribute_before finds the attribute attached to a Rust item
    Given one Rust item inside its container
    When _rust_attribute_before looks back past any comments to the previous sibling
    Then it returns that attribute's text, because a Rust attribute is a sibling of the item it decorates and is invisible from the item itself
    But it returns an empty string when the preceding sibling is not an attribute, and it reads only the nearest one

  Scenario: _rust collects a Rust file's items and refuses to call a framework-reachable one dead
    Given a parsed Rust file and whether the crate is a library
    When _rust descends through the module tree, skipping any module marked cfg(test)
    Then main is excluded as the crate entry point, any item carrying an attribute is undecidable, a public item of a library crate is undecidable, and the rest are candidates
    And the reason names the exact attribute, so a reader can see why the item was not called dead

  Scenario: _go_package reads the package a Go file declares
    Given a parsed Go file
    When _go_package reads the package clause
    Then it returns the package name, which decides whether an exported identifier could be imported by another module
    But a file with no package clause returns an empty string, and every name in it is then judged as if it were in main

  Scenario: _go collects a Go file's top-level declarations
    Given a parsed Go file
    When _go collects its functions, types, vars and consts
    Then main, init, the blank identifier and a Test, Benchmark, Example or Fuzz name are excluded as runtime or test-runner entry points
    And a capitalised name in any package other than main is undecidable, because another module could import it
    But everything else is a candidate for the reference scan to settle

  Scenario: _is_extension_container spots the C# class whose name never appears at a call site
    Given a C# type declaration
    When _is_extension_container checks for a static class holding extension methods
    Then both spellings count: a first parameter modified with this, and the newer extension member block the grammar parses as a constructor
    And a class that is one is never reported dead, because an extension method is dispatched on the receiver and the class name is never written at the call
    But a class that is not static is refused at once, since an extension container has to be static

  Scenario: _modifier_text reads a declaration's modifiers in either grammar's spelling
    Given a Java or C# declaration
    When _modifier_text joins its modifier nodes into one string
    Then Java's single grouped node and C#'s one node per keyword both read the same, so one rule can ask whether a member is public or private
    But a declaration with no modifier at all returns an empty string

  Scenario: _annotation_on finds the annotation that makes a member framework-reachable
    Given a declaration and the annotation node types for its language
    When _annotation_on scans the declaration's children and inside a Java modifiers group
    Then it returns the first line of the first annotation or attribute it finds
    But an unannotated declaration returns an empty string, which is what sends it on to the ordinary visibility rules

  Scenario: _member_language builds the collector Java and C# both use
    Given one language's node types, member kinds, body types and annotation spellings
    When _member_language closes over that configuration
    Then it returns a collector, which is how a single traversal serves two languages that differ only in spelling
    And the returned collector recurses into nested types and judges a member only when it sits inside a type

  Scenario: _js collects a TypeScript or JavaScript file's top-level declarations
    Given a parsed file and the set of files the package declares as entry points
    When _js walks the top-level statements and the export form of each
    Then a default export is undecidable, because an importer binds it under any name it likes
    And a named export from a file the package declares as an entry point is undecidable too
    But everything else, exported or not, is a candidate

  Scenario: _c_declarator_name digs the identifier out of a C declarator
    Given a C declarator, which may be wrapped in pointer, array or function syntax
    When _c_declarator_name descends through the wrappers
    Then it returns the identifier the declaration names
    But it returns nothing when the chain runs out without one, and that declaration is then collected not at all

  Scenario: _c collects a C file's definitions and treats external linkage as unreadable
    Given a parsed C file
    When _c collects its top-level function definitions and initialised declarations
    Then main is excluded, a static name is a candidate, and anything with external linkage is undecidable, since a translation unit outside the repository could call it
    But a declaration with no initialiser is not collected at all, so it is neither judged nor disclosed

  Scenario: _ruby collects only a Ruby file's top-level names
    Given a parsed Ruby file
    When _ruby collects its top-level methods, classes, modules and constants
    Then an interpreter hook such as initialize or method_missing is excluded, and everything else is a candidate
    But a method defined inside a class is deliberately not collected, because Ruby dispatches on a receiver whose type no reading can pin down, so an unreferenced name there is evidence of nothing
