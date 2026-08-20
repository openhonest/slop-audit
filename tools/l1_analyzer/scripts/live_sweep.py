"""Run the live coverage-proof sweep over several repositories and write a dated record.

    uv run --project tools/l1_analyzer python tools/l1_analyzer/scripts/live_sweep.py \
        --ceiling 5 REPO [REPO ...]

Spends money. The ceiling is the total number of gaps the whole run may hand to a model,
across every repository, and it starts at 5. `--dry-run` reports what each repository
would be offered without calling anything.

The key is read from ~/dev/.env, or from --env-file. Never from the ambient environment:
a run has to be able to say which file paid for it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from l1_analyzer import live_sweep

DEFAULT_ENV = Path.home() / "dev" / ".env"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repos", nargs="+", type=Path)
    parser.add_argument("--ceiling", type=int, default=5,
                        help="total gaps the whole run may hand to a model (default 5)")
    parser.add_argument("--per-repo", type=int, default=None,
                        help="most any one repository may take from that total. Unset, the "
                             "ceiling is divided across the repositories so each gets a turn.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what each repository would be offered; call nothing")
    parser.add_argument("--out", type=Path, help="write the record here as JSON")
    args = parser.parse_args(argv)

    per_repo = args.per_repo if args.per_repo is not None else live_sweep.fair_share(args.ceiling, len(args.repos))
    key = live_sweep.key_from(args.env_file)
    print(f"key file: {args.env_file} ({'key found' if key else 'NO KEY'})")
    print(f"ceiling:  {args.ceiling} attempts for the run, at most {per_repo} per repository")

    if args.dry_run:
        spent = 0
        for repo in args.repos:
            language = live_sweep.language_of(repo)
            allowance = live_sweep.share(args.ceiling, per_repo, spent)
            print(f"  {repo}: {language or 'no sweep applies'}, would be offered {allowance}")
            spent += allowance          # the worst case, so the plan shows the most it could cost
        print(f"worst case: {spent} model-backed attempts")
        return 0

    # The real sweeps, named here because this is the boundary that means to spend money.
    record = live_sweep.sweep(args.repos, key, args.ceiling, per_repo, live_sweep.SWEEPS)
    print(record["detail"])
    for report in record["repos"]:
        print(f"  {report['repo']}: attempted {report['attempted']}, "
              f"retained {report['retained']} - {report['detail']}")
    if args.out:
        args.out.write_text(json.dumps(record, indent=2, default=str))
        print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
