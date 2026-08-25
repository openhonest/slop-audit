"""The path on a finding has to be the same string however the caller spelled the repository.

`analyze` reported `tools/l1_analyzer/x.py` when handed `.` and `/Users/.../x.py` when
handed the same directory absolutely. Every consumer keys on that string, so one file read
as two, and anything tracking a finding across runs saw a rule move rather than persist.

Found by a peer hitting exactly this in their own trace: their diagnostic wrote rows with
one spelling while the hook wrote the other, one file counted twice, and a rule standing on
it read as standing on two. Their fix was to resolve the key. This is the same fix on the
side that produces the key in the first place.

Relative to the repository under audit, because that is the only spelling stable across
machines as well as across callers. An absolute path also names one file, and it names a
different one on the next machine.
"""

import pathlib

from l1_analyzer import honest_code

_REPO = pathlib.Path(__file__).parent.parent


def test_the_same_repository_spelled_two_ways_names_its_files_identically():
    relative = honest_code.analyze(pathlib.Path("."), "python")
    absolute = honest_code.analyze(pathlib.Path.cwd(), "python")
    assert {f["file"] for f in relative["findings"]} == {f["file"] for f in absolute["findings"]}


def test_no_finding_carries_an_absolute_path():
    """An absolute path names one file here and a different one on another machine, so a
    record carrying it cannot be compared across the two."""
    found = honest_code.analyze(_REPO, "python")["findings"]
    absolute = sorted({f["file"] for f in found if str(f["file"]).startswith("/")})
    assert absolute == [], absolute


def test_the_path_is_relative_to_the_repository_that_was_audited(tmp_path):
    """Over a fixture, not this repository. It read the live tree until this repository
    reached zero findings, at which point it asserted over an empty list and passed for the
    wrong reason before failing on its own guard."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text(
        "def send_email(d):\n    return post('/email', d)\n\n\n"
        "def send_sms(d):\n    return post('/sms', d)\n")
    found = honest_code.analyze(tmp_path, "python")["findings"]
    assert found, "the fixture has to produce a finding or this asserts nothing"
    for finding in found:
        assert finding["file"] == "pkg/m.py", finding["file"]
        assert (tmp_path / finding["file"]).is_file()
