"""Diff the ported secret scan against the reference, one raw match at a time.

    uv run validate_secrets.py <repo>
    uv run validate_secrets.py --specimens      # one planted credential per rule

The panel compares one number. This compares what stands behind it: every match each side
made, with the file, the rule that fired, the line, the credential's SHAPE, and whether the
site counts as a test or as documentation. Two scanners can reach the same count from
different matches, and a count that agrees by cancellation is the one an auditor cannot
check.

NO CREDENTIAL IS PRINTED, on either side. Both dump the excerpt the published finding
carries: the first four characters and a length. A harness that diffed the values would copy
every leak it found into a second place, which is the one thing this indicator's own findings
never do.

The scanned and refused file counts are compared too. They are the denominator, and a port
that reads a different set of files can agree on every match it made and still publish a
different reading.

`--specimens` answers the thing a corpus sweep cannot. Thirteen well-run open-source
repositories commit almost no credentials, so eleven of them report zero on both sides and
agree about nothing: a port with fifteen of the seventeen rules missing would sweep clean.
This plants one credential per rule in a throwaway tree and diffs the two readings of it.

Every planted credential is ASSEMBLED at run time from pieces, never written out whole. A
harness that spelled seventeen live-shaped credentials into a tracked file would put them in
this repository's own scan, and a scanner whose parity harness trips it is not one anybody
will keep running.

Exit 1 on any difference, 2 when neither side opened a file. Nothing is written anywhere,
except the throwaway tree `--specimens` builds under the system temp directory and deletes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from parity_harness import binary_is_stale, boundary

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "debug" / "slop-audit-rs"

# One match, as both sides name it: the file, the rule, the line, the shape, and the two
# scope flags that split the count.
Row = tuple[str, str, int, str, bool, bool]


READER = """
import sys, json
from pathlib import Path
from l1_analyzer.scope import PRODUCTION, _bucket_reason, _in_ignored_dir, _repo_has_packages, _rglob_files
from l1_analyzer import secret_scan as s

repo = Path(sys.argv[1])
has_packages = _repo_has_packages(repo)
tracked = s._tracked_files(repo)
rows, scanned, skipped = [], 0, 0
for path in _rglob_files(repo, "*"):
    if _in_ignored_dir(path, ()) or not s._scannable(path):
        continue
    relpath = str(path.relative_to(repo)) if repo in path.parents else path.name
    if tracked is not None and relpath not in tracked:
        continue
    raw = s._read_text_bytes(path, s._MAX_BYTES)
    if raw is None:
        skipped += 1
        continue
    scanned += 1
    bucket = _bucket_reason(path, repo, has_packages, PRODUCTION)
    in_tests = bucket in ("tests", "test")
    in_docs = not in_tests and (bucket == "docs" or path.suffix.lower() in s._DOC_SUFFIXES)
    text = raw.decode("utf8", errors="ignore")
    for rule_id, line, value in s._scan_text(text, text.encode("utf8"), path.name):
        rows.append([relpath, rule_id, line, s._excerpt(value), in_tests, in_docs])
print(json.dumps({"rows": rows, "scanned": scanned, "skipped": skipped,
                  "git": tracked is not None}))
"""


@boundary
def reference_scan(repo: Path) -> tuple[set[Row], int, int, bool]:
    """The reference's matches, over its own walk."""
    out = subprocess.run(
        ["uv", "run", "python", "-c", READER, str(repo.resolve())],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    read = json.loads(out)
    rows = {(r[0], r[1], r[2], r[3], r[4], r[5]) for r in read["rows"]}
    return rows, read["scanned"], read["skipped"], read["git"]


@boundary
def ported_scan(repo: Path) -> tuple[set[Row], int, int, bool]:
    """The port's matches, from the binary's own dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--secrets"],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: set[Row] = set()
    scanned = skipped = 0
    git = False
    for line in out.splitlines():
        if line.startswith("# "):
            head, refused, scope = line[2:].split("\t")
            scanned, skipped, git = int(head.split()[0]), int(refused.split()[0]), scope == "git-tracked"
            continue
        if not line.strip():
            continue
        path, rule, at, shape, in_tests, in_docs = line.split("\t", 5)
        rows.add((path, rule, int(at), shape, in_tests == "true", in_docs == "true"))
    return rows, scanned, skipped, git


@boundary
def report(missing: set[Row], extra: set[Row], shown: int) -> None:
    """What differs, the reference's matches first."""
    for label, rows in (("only the reference finds", missing), ("only the port finds", extra)):
        if not rows:
            continue
        print(f"\n{len(rows)} {label}:")
        for row in sorted(rows)[:shown]:
            path, rule, at, shape, in_tests, in_docs = row
            scope = "test" if in_tests else "docs" if in_docs else "production"
            print(f"   {path}:{at}  {rule}  {shape}  [{scope}]")
        if len(rows) > shown:
            print(f"   ... and {len(rows) - shown} more")


# The filler every planted credential is padded with. Deliberately free of any word on the
# scanner's placeholder list, so a specimen is rejected for its shape and never for its text.
_FILL = "Zk3qR7vL9wX2mB5nT8yHpJ4sD6gF1aC0eWxU"
_HEX = "a1b2c3d4e5f60987654321fedcba098765"
# AWS keys are upper case and digits only, so the mixed-case filler above never
# matched the rule and the specimen tested nothing.
_UPPER = "QWERTYUIOP12345678ASDFGHJKLZXCVBNM"


def _pad(length: int, alphabet: str = _FILL) -> str:
    """`length` characters of filler, repeated as far as it has to go."""
    return (alphabet * (length // len(alphabet) + 1))[:length]


def _specimens() -> dict[str, str]:
    """One file per rule, each carrying one credential of that rule's shape.

    Assembled from pieces rather than written out whole. Spelled literally, these seventeen
    strings would be seventeen findings in this repository's own scan, which is a strange
    thing for a credential scanner's own harness to leave behind.
    """
    planted = {
        "aws.txt": "AKIA" + _pad(16, _UPPER),
        "github.txt": "gh" + "p_" + _pad(36),
        "github_pat.txt": "github" + "_pat_" + _pad(44),
        "gitlab.txt": "glpat" + "-" + _pad(20),
        "slack.txt": "xox" + "b-" + _pad(24),
        "slack_hook.txt": "https://hooks." + "slack.com/services/T" + _pad(20),
        "stripe.txt": "sk" + "_live_" + _pad(24),
        "google.txt": "AIza" + _pad(35),
        "openai.txt": "sk" + "-" + _pad(24),
        "sendgrid.txt": "SG" + "." + _pad(22) + "." + _pad(43),
        "npm.txt": "npm" + "_" + _pad(36),
        "huggingface.txt": "hf" + "_" + _pad(34),
        "twilio.txt": "SK" + _pad(32, _HEX),
        "telegram.txt": "1234567890" + ":AA" + _pad(33),
        "jwt.txt": "eyJ" + _pad(16) + "." + "eyJ" + _pad(16) + "." + _pad(16),
        "connection.txt": "postgres" + "://svc:" + _pad(20) + "@db.internal:5432/app",
        "pem.txt": "-----BEGIN " + "RSA PRIVATE KEY-----\n" + _pad(64),
        "generic.py": 'api_key = "' + _pad(20) + '"\n',
        ".env": "AUTH0_CLIENT_" + "SECRET=" + _pad(20) + "\n",
    }
    return {name: body if body.endswith("\n") else body + "\n"
            for name, body in planted.items()}


@boundary
def _plant(tree: Path) -> int:
    """Write the specimen tree and say how many credentials it holds."""
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(parents=True)
    files = _specimens()
    for name, body in files.items():
        (tree / name).write_text(body)
    return len(files)


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--specimens":
        tree = Path(tempfile.gettempdir()) / f"slop-l114-specimens-{os.getpid()}"
        planted = _plant(tree)
        print(f"{planted} planted credential(s), one per rule")
        try:
            return main([argv[0], str(tree)])
        finally:
            shutil.rmtree(tree, ignore_errors=True)
    if len(argv) != 2:
        print(__doc__)
        return 2
    repo = Path(argv[1])
    stale = binary_is_stale(BINARY, HERE / "src")
    if stale:
        print(stale)
        return 2

    ref_rows, ref_scanned, ref_skipped, ref_git = reference_scan(repo)
    port_rows, port_scanned, port_skipped, port_git = ported_scan(repo)

    print(f"{repo}: {len(ref_rows)} match(es) in the reference over {ref_scanned} file(s), "
          f"{len(port_rows)} in the port over {port_scanned}")
    if ref_scanned == 0 and port_scanned == 0:
        print("NOTHING TO COMPARE: neither side opened a file, so this run proves nothing")
        return 2

    differences = 0
    for name, want, got in (("files scanned", ref_scanned, port_scanned),
                            ("files refused", ref_skipped, port_skipped),
                            ("git-tracked scope", ref_git, port_git)):
        if want != got:
            print(f"DIFF {name}: reference={want} ported={got}")
            differences += 1
    missing, extra = ref_rows - port_rows, port_rows - ref_rows
    if missing or extra:
        report(missing, extra, shown=20)
        differences += 1
    if differences:
        return 1
    print("EQUAL, match for match and file for file")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
