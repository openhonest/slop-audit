"""CLI for slop-audit-l1 analyzer.

Run against any repo (language auto-detected or specified).
Example:
  uv run --project . l1-analyzer /path/to/repo --since 2025-01-01
  uv run --project . l1-analyzer /path/to/repo --indicators 1,18 --lang python
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from l1_analyzer import indicators

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l1-analyzer")
    parser.add_argument("repo", type=Path, help="Path to git repository root")
    parser.add_argument("--since", default=None, help="Start date for git log (e.g. 2025-01-01)")
    parser.add_argument("--until", default=None, help="End date")
    parser.add_argument(
        "--indicators",
        default="all",
        help="Comma-separated L1 numbers or 'all' (default). E.g. 1,2,18",
    )
    parser.add_argument(
        "--lang",
        default="auto",
        choices=["auto", *sorted(indicators.LANG_CFG)],
        help="Primary language for source-based indicators (L1.12+). 'auto' detects from files.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args(argv)

    results: dict[str, Any] = {}

    inds = [i.strip() for i in args.indicators.split(",")] if args.indicators != "all" else None

    # L1.1-8: git based, language agnostic
    if inds is None or any(i in ("1","2","3","4","5","6","7","8","all") for i in (inds or [])):
        git_results = indicators.compute_git_indicators(
            args.repo, since=args.since, until=args.until
        )
        results.update(git_results)

    # L1.9-11: config presence
    if inds is None or any(i in ("9","10","11","all") for i in (inds or [])):
        config_results = indicators.compute_config_indicators(args.repo)
        results.update(config_results)

    # L1.12-17,18-20: source based -> use tree-sitter for language-agnostic where implemented
    if inds is None or any(i in ("12","13","14","15","16","17","18","19","20","all") for i in (inds or [])):
        lang = args.lang
        if lang == "auto":
            lang = indicators.detect_primary_language(args.repo)
        source_results = indicators.compute_source_indicators(
            args.repo, lang=lang, since=args.since, until=args.until
        )
        results.update(source_results)

    if args.format == "json":
        print(json.dumps({"repo": str(args.repo), "results": results}, indent=2))
    else:
        print(f"LAYER 1: Slop Audit indicators for {args.repo}")
        print(f"Language (for source indicators): {results.get('lang', lang)}")
        for k, v in sorted(results.items()):
            if k.startswith("L1."):
                print(f"  {k}: {v}")
        print(f"\nSlop signal count (demo thresholds): see individual bands above.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
