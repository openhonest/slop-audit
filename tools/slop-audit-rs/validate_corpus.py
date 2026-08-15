"""Validate the port equal to the Python reference across the pinned corpus.

`validate.py` checks one repository. This walks corpus.toml, clones each entry at its
pinned commit, and runs the same diff over all of them. Exit code 1 if any indicator
disagrees anywhere, so it can gate a commit or a release.

    uv run validate_corpus.py                  # every language in the manifest
    uv run validate_corpus.py java c           # only these
    uv run validate_corpus.py --verbose        # print every EQUAL line, not just diffs

Clones land in ~/.cache/slop-audit-corpus, or $SLOP_AUDIT_CORPUS if set. They are full
clones, not shallow: L1.1 through L1.8 read the commit history, and a shallow clone
would compare two tools on one commit rather than on a history.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from validate import diff_panels

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "corpus.toml"
CACHE = Path(os.environ.get("SLOP_AUDIT_CORPUS", Path.home() / ".cache" / "slop-audit-corpus"))


def clone_at(slug: str, commit: str) -> Path:
    """The repo at the pinned commit, cloned on first use and reused after. Returns the
    checkout path. A cached clone that does not have the commit is fetched again, which
    covers a manifest bump without a manual cache wipe."""
    target = CACHE / slug.replace("/", "__")
    if not target.exists():
        print(f"  cloning {slug} ...", flush=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", f"https://github.com/{slug}.git", str(target)],
                       check=True)
    have = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                          cwd=target, capture_output=True)
    if have.returncode != 0:
        print(f"  fetching {commit[:12]} for {slug} ...", flush=True)
        subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=target, check=True)
    subprocess.run(["git", "checkout", "--quiet", "--detach", commit], cwd=target, check=True)
    return target


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    entries = tomllib.loads(MANIFEST.read_text())["repo"]
    if args:
        entries = [e for e in entries if e["lang"] in args or e["slug"] in args]
        if not entries:
            print(f"nothing in corpus.toml matches {args}")
            return 2

    failures: list[str] = []
    for entry in entries:
        slug, lang, commit = entry["slug"], entry["lang"], entry["commit"]
        print(f"\n=== {slug} ({lang}) @ {commit[:12]}")
        repo = clone_at(slug, commit)
        # --lang auto on purpose: detection is part of what is being validated, and the
        # manifest's `lang` is the expectation it is checked against.
        diffs, compared = diff_panels(repo, "auto", quiet=not verbose)
        detected = subprocess.run(
            [str(HERE / "target" / "release" / "slop-audit-rs"), str(repo), "--tsv"],
            capture_output=True, text=True, check=True).stdout.splitlines()[0].split("\t")[1]
        if detected != lang:
            print(f"  DIFF  language: manifest says {lang}, both tools detect {detected}")
            failures.append(f"{slug}: detected {detected}, manifest says {lang}")
        status = "OK" if diffs == 0 else f"{diffs} DIFF"
        print(f"  {compared - diffs}/{compared} compared indicators equal  [{status}]")
        if diffs:
            failures.append(f"{slug}: {diffs} indicator(s) disagree")

    print()
    if failures:
        for line in failures:
            print(f"FAIL {line}")
        return 1
    # Not "every indicator equal": this compares the indicators the binary claims to
    # measure. The ones it does not are listed per repo as GAP lines by the differ, and
    # a summary that hides them is how a parity number read 16/16 while L1.18 was absent.
    print(f"every COMPARED indicator equal across {len(entries)} repositories")
    print("indicators the binary does not measure are reported as GAP lines above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
