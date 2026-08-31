"""Which Maven a Java repository is measured with, and when it cannot be measured at all.

A project that ships its own `./mvnw` pins the Maven version it expects, and running the
system `mvn` instead measures a different build than the one the project describes. This is
what makes the audit directory-insensitive: the wrapper in the target repository wins over
whatever happens to be on the machine that launched the analyzer.

Neither decision was held by a test. Java is the least reached of the nine harnesses, and
these are the two lines in it that decide anything without running a subprocess.

The refusals matter as much as the choice. A Gradle project is named as not-yet-supported
rather than measured wrong, and a directory with no build at all is told what it needs. A
zero for either would read as a project whose tests were measured and found wanting.
"""

from l1_analyzer import java_trace


def test_a_repository_shipping_its_own_wrapper_is_measured_with_that_wrapper(tmp_path):
    """The wrapper pins the Maven version the project expects, so it wins over the machine's."""
    (tmp_path / "mvnw").write_text("#!/bin/sh\nexec mvn \"$@\"\n")
    assert java_trace._maven(tmp_path) == str(tmp_path / "mvnw")


def test_a_repository_with_no_wrapper_falls_back_to_the_machine(tmp_path):
    """Whatever `which mvn` answers, including nothing. The fallback is the machine's Maven
    and the test asserts only that the wrapper is not invented."""
    assert java_trace._maven(tmp_path) != str(tmp_path / "mvnw")


def test_a_gradle_project_is_named_as_unsupported_rather_than_measured_wrong(tmp_path):
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }\n")
    reason = java_trace._unsupported_reason(tmp_path, "mvn")
    assert reason is not None and "Gradle" in reason


def test_a_kotlin_gradle_project_is_recognised_too(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("plugins { java }\n")
    reason = java_trace._unsupported_reason(tmp_path, "mvn")
    assert reason is not None and "Gradle" in reason


def test_a_directory_with_no_build_at_all_is_told_what_it_needs(tmp_path):
    reason = java_trace._unsupported_reason(tmp_path, "mvn")
    assert reason is not None and "pom.xml" in reason


def test_a_maven_project_with_no_maven_available_says_so(tmp_path):
    """The pom is there and the tool is not. The reason names both ways to supply it, so a
    reader knows they can add a wrapper as well as install Maven."""
    (tmp_path / "pom.xml").write_text("<project/>\n")
    reason = java_trace._unsupported_reason(tmp_path, None)
    assert reason is not None
    assert "mvn" in reason and "mvnw" in reason


def test_a_maven_project_with_maven_available_is_measurable(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>\n")
    assert java_trace._unsupported_reason(tmp_path, "/usr/bin/mvn") is None


def test_the_command_it_judges_is_the_one_it_is_handed(tmp_path):
    """The reason function does not look the tool up itself. It used to, while its caller
    looked it up again and a comment carried the promise that the two calls agreed. Two
    reads of the filesystem are two answers."""
    import inspect

    source = inspect.getsource(java_trace._unsupported_reason)
    assert "_maven(" not in source
