Feature: References Resolve Statically

  Every identifier a rendered artifact names is a reference across a boundary. Asserting
  the artifact contains the string proves it was written, not that it resolves, so two
  green tests can describe a button and a menu that never connect.

  Scenario: undecidable whether a route a page names exists
    Given a page naming a route in an attribute
    When this clause reads the page
    Then the route is passed over, because where a project declares its routes is a convention this reader does not know and a guess would report every link in every repository whose framework we guessed wrong
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: unresolved_references reports every reference it can resolve that resolves to nothing
    Given a repository
    When unresolved_references reads each page for the templates and classes it names, and resolves them against the files and stylesheets present
    Then it reports a template that is not there and a class no stylesheet defines
    And it takes the repository rather than one parsed source, because a reference and the thing it names are in different files and a page alone cannot say whether the rule it names exists
    And a repository with no rendered artifact is answered with nothing decided, since it was not measured against a rule about rendered artifacts
    And no class is decided at all where no stylesheet exists, because there is nothing to resolve against and reporting every class would be a finding about this reader
    But a route is never resolved, and this is stated in the clause rather than left for a reader to infer from silence

  Scenario: ours says whether a file is this repository's own
    Given a path
    When ours checks its components against the directories holding somebody else's code
    Then it answers no for a dependency, a cache or a build directory
    But it matches components rather than text, so the answer is the same however the path was spelled

  Scenario: pages_and_stylesheets gives the rendered artifacts and what they resolve against
    Given a repository
    When pages_and_stylesheets walks it for pages and for stylesheets
    Then it returns both lists
    But it returns them together, because neither is a finding alone: a page with no stylesheet anywhere has nothing to resolve a class against

  Scenario: rules_defined_in gives every class name a set of stylesheets defines
    Given the text of each stylesheet
    When rules_defined_in reads the rules out of them
    Then it returns the class names they define
    But it takes the text and not the paths, because reading them here put a disk under the decision and this package's own rule about input and output said so on the first run

  Scenario: boundary_in_text_of reads a list of files and decides nothing
    Given a list of paths
    When boundary_in_text_of reads each one
    Then it returns their text
    But one unreadable file contributes nothing rather than stopping the rest, so a single locked file does not silence the whole clause

  Scenario: templates_named_in gives every template one template names
    Given the text of a page
    When templates_named_in looks for the directives that name another template
    Then it returns each named template in the order it appears
    But it reads the quoted name only, so a directive naming a template through a variable is not read as naming a file

  Scenario: classes_named_in gives every class name a page writes out
    Given the text of a page
    When classes_named_in reads the class attributes
    Then it returns each name in each attribute, since one attribute holds several and each is its own reference
    And an attribute the template computes is refused whole, because what it renders to depends on values this reader does not have
    And dropping only the fragments carrying a brace left the pieces between them standing as class names, which is how the first run on this package reported thirty-two of them
    But an attribute beside a computed one is still read, so refusing one does not silence the rest of the file

  Scenario: a_template_exists says whether a named template is somewhere an engine would find it
    Given a template name, the page naming it, and the repository
    When a_template_exists looks beside the page and then in each directory up to the root
    Then it answers yes where the file is in any of them
    And it accepts any of them because where an engine looks is configuration this reader does not have
    But it errs toward yes, since a false yes leaves one reference unchecked and a false no reports a template that is there and sends a reader to fix nothing
