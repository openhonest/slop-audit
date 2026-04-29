"""
CLI entry point for ui-audit.

Usage:
    uv run python -m ui_audit --config .audit/config.json
    uv run python -m ui_audit --playground site/js/uix-playground.js --enhance src/uix.js
    uv run python -m ui_audit --config .audit/config.json --visual
"""

import argparse
import json
import sys
from pathlib import Path

from . import audit


def main():
    parser = argparse.ArgumentParser(
        description='Audit UI component playground controls against enhance functions'
    )
    parser.add_argument(
        '--config', type=Path,
        help='JSON config file with playground, enhance, and prefix'
    )
    parser.add_argument(
        '--playground', type=Path,
        help='Path to playground JS source'
    )
    parser.add_argument(
        '--enhance', type=Path,
        help='Path to component library JS source'
    )
    parser.add_argument(
        '--prefix', default='ux-',
        help='Attribute prefix (default: ux-)'
    )
    parser.add_argument(
        '--format', choices=['text', 'summary', 'json'], default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--visual', action='store_true',
        help='Run Phase 2: Playwright visual verification of flagged controls'
    )
    parser.add_argument(
        '--url',
        help='Playground URL for visual testing (overrides config)'
    )
    parser.add_argument(
        '--screenshots', default='.audit/screenshots',
        help='Directory for visual test screenshots (default: .audit/screenshots)'
    )

    args = parser.parse_args()

    # Load from config or direct args
    config = {}
    if args.config:
        config = json.loads(args.config.read_text())
        playground_path = Path(config['sources']['playground']['path'])
        enhance_path = Path(config['sources']['enhancers']['path'])
        prefix = config.get('attrPrefix', 'ux-')
    elif args.playground and args.enhance:
        playground_path = args.playground
        enhance_path = args.enhance
        prefix = args.prefix
    else:
        parser.error('Provide --config or both --playground and --enhance')
        return

    # I/O at the boundary
    playground_source = playground_path.read_text()
    enhance_source = enhance_path.read_text()

    # Phase 1: static audit (always runs)
    output = audit(
        playground_source=playground_source,
        enhance_source=enhance_source,
        attr_prefix=prefix,
        output=args.format,
    )
    print(output)

    # Phase 2: visual verification (optional)
    if args.visual:
        from .lib.visual import run_visual_audit

        url = args.url or config.get('visual', {}).get('url')
        if not url:
            print('\nError: --url or config.visual.url required for visual testing', file=sys.stderr)
            sys.exit(1)

        screenshot_dir = args.screenshots or config.get('visual', {}).get('screenshotDir', '.audit/screenshots')

        # Get raw audit results for Phase 2
        raw_results = audit(
            playground_source=playground_source,
            enhance_source=enhance_source,
            attr_prefix=prefix,
            output='raw',
        )

        print(f'\n--- Phase 2: Visual Verification ---')
        print(f'URL: {url}')
        print(f'Screenshots: {screenshot_dir}')

        visual_results = run_visual_audit(
            url=url,
            audit_results=raw_results,
            screenshot_dir=screenshot_dir,
        )

        for vr in visual_results:
            if 'error' in vr:
                print(f'  Error: {vr["error"]}')
                continue

            name = vr['component']
            n_screenshots = len(vr['screenshots'])
            observations = vr.get('observations', [])
            print(f'\n  [{name}] {n_screenshots} screenshots')
            for obs in observations:
                print(f'    - {obs}')

        print(f'\nScreenshots saved to {screenshot_dir}/')


if __name__ == '__main__':
    main()
