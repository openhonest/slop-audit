"""The clause check reads the files the scope table gives it, like every other indicator.

`scope.py` is the single owner of which indicator reads which files, and it names fourteen.
L1.21 was not one of them: `honest_code.analyze` reached for `scope.PRODUCTION` directly, so
the table could say a directory is not production and the clause check would read it anyway.

A conformance directory is the case that showed it. The table already excludes conformance
from the god-file count and both state meters, and gives the reason: it holds law and spec
scaffolding and test doubles, fault-injection markers and deliberately failing connections.
Those are exactly the shapes the clause check flags. A test double that subclasses a
connection to inject a fault IS inheritance, and it is also the right way to write a test
double.

Found on 2026-09-05 measuring the Honest Framework. Every one of its seventeen inheritance
findings and all sixty-three of its method findings were in conformance suites and in
example files that exist to demonstrate Django and Pydantic, which are the alternatives the
framework argues against. Its module source has none of either. The count read 449 and the
number that means anything is 186.
"""


from l1_analyzer import honest_code, scope


def test_the_scope_table_names_the_clause_check():
    """Every other indicator is in that table. One reaching past it is the second owner of
    a fact the table exists to hold."""
    named = {i for s in scope.SCOPES.values() for i in s["indicators"]}
    assert "L1.21" in named, "the clause check is not in any scope's indicator list"


def test_the_clause_check_does_not_read_a_conformance_directory(tmp_path):
    """The table says a conformance directory is not production, and gives the reason. The
    clause check has to hear it."""
    src = tmp_path / "pkg"
    src.mkdir()
    (src / "clean.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    conformance = tmp_path / "conformance"
    conformance.mkdir()
    (conformance / "doubles.py").write_text(
        "class Conn:\n"
        "    def run(self) -> int:\n"
        "        return 1\n"
        "\n"
        "\n"
        "class FailingConn(Conn):\n"
        "    def run(self) -> int:\n"
        "        raise RuntimeError('injected')\n")
    row = honest_code.analyze(tmp_path, "python")
    files = [f["file"] for f in row.get("findings", [])]
    assert not any("conformance" in f for f in files), files


def test_a_test_double_outside_conformance_is_still_read(tmp_path):
    """The exclusion is the directory the table names, not any file that looks like a
    double. Widening it would let anyone move code out of the count by naming it well."""
    (tmp_path / "engine.py").write_text("class Engine:\n    def run(self) -> int:\n        return 1\n")
    (tmp_path / "car.py").write_text(
        "from engine import Engine\n\n\nclass Car(Engine):\n"
        "    def go(self) -> int:\n        return self.run()\n")
    row = honest_code.analyze(tmp_path, "python")
    assert row.get("findings"), "a plain subclass outside conformance is still a finding"
