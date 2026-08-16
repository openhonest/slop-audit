"""The absolute-path check: flag machine-specific filesystem paths hardcoded in source, and
never flag an HTTP route, an XPath, or a JSON pointer that merely starts with `/`. Pure
assertions against a temp repo, no mocks."""

import pathlib
import tempfile

import pytest
from l1_analyzer import absolute_paths
from l1_analyzer.incomplete import IncompleteCode


def _scan(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return absolute_paths.scan(root, "python")


# --- flagged: machine-specific roots ---------------------------------------

def test_flags_a_home_directory_path():
    r = _scan({"a.py": 'LOG = "/home/debian/turso/report.md"\n'})
    assert r["verdict"] == "flagged" and r["value"] == 1 and r["band"] == "Slop"
    assert r["findings"][0]["path"] == "/home/debian/turso/report.md"
    assert r["findings"][0]["line"] == 1


def test_flags_users_temp_and_windows_roots():
    r = _scan({"a.py": 'p = "/Users/adam/x"\n',
               "b.rs": 'let t = "/tmp/scratch/out.json";\n',
               "c.py": 'w = "C:\\\\Users\\\\adam\\\\app"\n'})
    hit = {f["file"] for f in r["findings"]}
    assert hit == {"a.py", "b.rs", "c.py"} and r["value"] == 3


def test_flags_mac_scratch_roots():
    r = _scan({"a.py": 'D = "/private/tmp/claude/scratch"\n',
               "b.py": 'T = "/var/folders/qr/xyz/T/run"\n'})
    assert r["value"] == 2


# --- clean: paths that only look absolute ----------------------------------

def test_does_not_flag_an_http_route_or_url():
    r = _scan({"a.py": 'route = "/api/users/{id}"\nhealth = "/healthz"\n'
                        'url = "https://example.com/home/page"\n'})
    assert r["verdict"] == "clean" and r["value"] == 0 and r["band"] == "Healthy"


def test_does_not_flag_a_relative_path_or_xpath():
    r = _scan({"a.py": 'rel = "src/main.rs"\nxp = "/root_element/child"\nptr = "/data/0/name"\n'})
    # `/root_element` is not the `/root/` machine root; `/data` is a JSON pointer, not a path.
    assert r["value"] == 0


def test_ignores_non_source_files():
    """Docs are not scanned; only source extensions are. The tree carries one source file so
    the scan really runs, which is what makes the zero a reading of the code rather than a
    reading of nothing. The README-only tree, which used to prove this, proved instead that
    an unscanned repository and a clean one give the same answer - see the test below."""
    r = _scan({"README.md": "see /home/adam/notes for details\n", "a.py": "x = 1\n"})
    assert r["value"] == 0 and r["verdict"] == "clean"


def test_refuses_when_no_file_carried_a_scanned_extension():
    """A count of zero over zero files read is not a clean bill, it is no reading at all.
    The refusal names the scan, so a reader can tell which measure declined and why."""
    with pytest.raises(IncompleteCode, match="absolute-path scan"):
        _scan({"README.md": "see /home/adam/notes for details\n"})


def test_does_not_flag_an_escape_sequence_as_a_windows_path():
    """`"x:\\n"` is a colon and a newline escape, not drive X. This fired 21 times on the
    analyzer's own tests: any source writing a single letter, a colon and `\\n` was read as a
    hardcoded Windows path. Two characters after the drive backslash separate the two."""
    r = _scan({"a.py": 'label = "x:\\n"\nother = "M:\\n"\n',
               "b.rs": 'let s = "C:\\t";\n'})
    assert r["verdict"] == "clean" and r["value"] == 0


def test_still_flags_a_short_windows_path():
    """The escape-sequence rule must not cost a real drive path its finding."""
    r = _scan({"a.py": 'p = "C:\\\\temp"\n'})
    assert r["value"] == 1


def test_does_not_flag_a_bare_root():
    """A root with nothing after it names a convention, not a machine. The only source that
    carries bare roots is a tool that lists them, this checker included."""
    r = _scan({"a.py": 'ROOTS = ("/home/", "/Users/", "/tmp/", "/var/folders/")\n'})
    assert r["verdict"] == "clean" and r["value"] == 0


def test_scopes_out_the_test_tree():
    """Production scope, the same exclusion L1.15, L1.17 and L1.19 use. A test that proves a
    path detector fires has to contain the path it detects."""
    r = _scan({"src/a.py": 'p = "/home/adam/x"\n',
               "tests/test_a.py": 'FIXTURE = "/home/adam/y"\n',
               # A test directory is believed only when its contents corroborate it, so
               # legacy.py carries the import a real one would.
               "test/legacy.py": 'import unittest\nFIXTURE = "/home/adam/z"\n'})
    assert r["value"] == 1
    assert r["findings"][0]["file"] == "src/a.py"


def test_scopes_out_a_dotted_csharp_test_project():
    """C# names a test project `<Project>.Tests`, so the exact component match never caught
    it: JamesNK/Newtonsoft.Json reported 31 absolute paths, every one of them stack-trace
    fixture data under Src/Newtonsoft.Json.Tests/."""
    r = _scan({"Src/Newtonsoft.Json/Serializer.cs": 'var p = "/home/adam/x";\n',
               "Src/Newtonsoft.Json.Tests/Schema/PersonTests.cs": 'var f = @"c:\\schema\\Person.json";\n',
               "Src/Newtonsoft.Json.Test/Legacy.cs": 'using Xunit;\nvar f = @"c:\\schema\\Old.json";\n'})
    assert r["value"] == 1
    assert r["findings"][0]["file"] == "Src/Newtonsoft.Json/Serializer.cs"


def test_reports_every_occurrence_and_counts_files():
    r = _scan({"a.py": 'x = "/home/a/one"\ny = "/tmp/two"\n', "b.go": 'z := "/mnt/data/three"\n'})
    assert r["value"] == 3
    assert "3 hardcoded machine-specific absolute path(s) across 2 file(s)" in r["details"]
