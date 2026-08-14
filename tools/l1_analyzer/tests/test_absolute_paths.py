"""The absolute-path check: flag machine-specific filesystem paths hardcoded in source, and
never flag an HTTP route, an XPath, or a JSON pointer that merely starts with `/`. Pure
assertions against a temp repo, no mocks."""

import pathlib
import tempfile

from l1_analyzer import absolute_paths


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
    r = _scan({"README.md": "see /home/adam/notes for details\n"})
    assert r["value"] == 0   # docs are not scanned; only source extensions are


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
               "test/legacy.py": 'FIXTURE = "/home/adam/z"\n'})
    assert r["value"] == 1
    assert r["findings"][0]["file"] == "src/a.py"


def test_reports_every_occurrence_and_counts_files():
    r = _scan({"a.py": 'x = "/home/a/one"\ny = "/tmp/two"\n', "b.go": 'z := "/mnt/data/three"\n'})
    assert r["value"] == 3
    assert "3 hardcoded machine-specific absolute path(s) across 2 file(s)" in r["details"]
