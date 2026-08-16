Feature: interleaving_robustness — which of the flagged concurrency surface no model checker exercises
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _module_stem gives the module name a Rust file defines
    Given a path relative to the repository, such as storage/shared_wal_coordination.rs
    When _module_stem strips the directories and the extension
    Then it returns shared_wal_coordination, which is the word a mod or use line in a model test would name

  Scenario: classify splits the flagged surface by whether a model touches it
    Given the flagged surface files, the set of files that carry a model marker, and the concatenated text of every modelled file
    When classify sorts the surface and places each file in exactly one of three lists
    Then a file that carries a marker itself is modeled-in-file, a file whose module name appears anywhere in the modelled text is modeled-elsewhere, and everything left is unmodeled
    And the modeled-elsewhere test is a whole-word search over that one blob of text, so a common module name can match a mention that has nothing to do with the surface, which is why the class is called a weak signal rather than proof
    But nothing here reads a file, so the answer is fixed entirely by the three arguments

  Scenario: _na builds the refusal this meter hands back when it will not measure
    Given the reason it is declining
    When _na assembles the result
    Then every list comes back empty, the verdict, the value and the band all read n/a, and the reason is carried in the details

  Scenario: analyze reports how much exposed concurrency surface no loom or shuttle model touches
    Given a repository and a language name
    When analyze asks the thread-surface meter for the surface and then reads every Rust file for a loom or shuttle marker
    Then it returns the unmodeled files as the finding, with the modelled-elsewhere and modelled-in-file lists beside them and a verdict of unmodeled when any file is unmodeled
    And it refuses for any language but Rust, and refuses again when the surface meter itself read no source, passing that refusal through rather than inventing a reading of its own
    But a repository with no exposed surface returns clean, and the band is n/a on every path, so this meter never grades anything
