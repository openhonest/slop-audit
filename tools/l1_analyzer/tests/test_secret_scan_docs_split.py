"""A credential in prose is not a credential in production code (L1.14).

Found by running the full panel over this repository, which the pre-commit gate does not
do: it runs three checks, not twenty. The report said "2 of the secret(s) are in
production code", and both sat in `spec/dimensions/07-configuration-secrets.md`, inside a
fenced block showing a Flask `config.py` as an EXAMPLE OF THE ANTIPATTERN. The scanner
was right to count them, because a credential committed to a repository is committed.
The sentence was wrong, because a specification is not production code.

The scope helper has a documentation bucket, but it fires only on a directory literally
named `docs`, and this specification lives in `spec/`. Rather than widen that helper,
which would move god-files, dead code and every other indicator that reads it, the split
is made three-way HERE: this is the only indicator that scans files which are not code.

The count does not change. Only who is told what about it.
"""

import pathlib
import tempfile

from l1_analyzer import secret_scan

# A value with enough entropy to clear the scanner's own screen. My first fixture,
# "hunter2-not-a-real-credential-9xQ", was rejected by it and every test failed with a
# total of zero, which measured the screen rather than the split.
_CRED = 'password = "' + "xK7pQ2mZ8vR4tY" + "6wB1nL3jH5" + '"\n'


def _analyze(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        for name, body in files.items():
            (p / name).parent.mkdir(parents=True, exist_ok=True)
            (p / name).write_text(body)
        return secret_scan.analyze(p, "python")


def test_a_credential_in_a_markdown_file_is_reported_as_documentation():
    r = _analyze({"spec/secrets.md": "Example of the antipattern:\n\n```\n" + _CRED + "```\n"})
    assert r["counts"]["total"] == 1
    assert r["counts"]["in_docs"] == 1
    assert r["counts"]["in_production"] == 0
    assert "in documentation" in r["details"]


def test_a_credential_in_source_is_still_production():
    r = _analyze({"app.py": _CRED})
    assert r["counts"]["total"] == 1
    assert r["counts"]["in_production"] == 1
    assert r["counts"]["in_docs"] == 0


def test_the_total_and_the_band_do_not_move():
    """The count is what the canon bands. Splitting who holds a credential must not change
    how many were found, or the fix would be a way of scoring better by relabelling."""
    docs = _analyze({"spec/secrets.md": _CRED})
    code = _analyze({"app.py": _CRED})
    assert docs["value"] == code["value"] == 1
    assert docs["band"] == code["band"]
