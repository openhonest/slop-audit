"""
Pure functions for formatting audit results.

No I/O — returns strings. Caller decides where to write them.
"""


def format_text(results: list[dict]) -> str:
    """Human-readable audit report."""
    lines = []
    lines.append('=' * 60)
    lines.append('UI Component Audit Report')
    lines.append('=' * 60)

    total_dead = 0
    total_hidden = 0
    total_matched = 0
    components_with_issues = 0

    for r in results:
        has_issues = r['emitted_not_read'] or r['read_not_emitted'] or not r['enhance_found']
        if has_issues:
            components_with_issues += 1

        total_dead += len(r['emitted_not_read'])
        total_hidden += len(r['read_not_emitted'])
        total_matched += len(r['matched'])

        lines.append('')
        status = 'PASS' if not has_issues else 'FAIL'
        lines.append(f'[{status}] {r["component"]} (enhance: {r["enhance_name"]})')

        if not r['enhance_found']:
            lines.append(f'  !! No enhance function found for "{r["enhance_name"]}"')
            continue

        if r['emitted_not_read']:
            lines.append(f'  DEAD CONTROLS ({len(r["emitted_not_read"])}):')
            for item in r['emitted_not_read']:
                lines.append(f'    - ux-{item["attr"]} (opts.{item["as_opt"]} not read by enhance)')

        if r['read_not_emitted']:
            lines.append(f'  HIDDEN FEATURES ({len(r["read_not_emitted"])}):')
            for opt in r['read_not_emitted']:
                lines.append(f'    - opts.{opt} (enhance reads it, playground does not emit)')

        if r['matched'] and not has_issues:
            lines.append(f'  {len(r["matched"])} controls matched')

    lines.append('')
    lines.append('-' * 60)
    lines.append(f'Summary: {len(results)} components audited')
    lines.append(f'  {components_with_issues} with issues')
    lines.append(f'  {total_dead} dead controls (playground emits, enhance ignores)')
    lines.append(f'  {total_hidden} hidden features (enhance reads, playground missing)')
    lines.append(f'  {total_matched} properly wired')
    lines.append('=' * 60)

    return '\n'.join(lines)


def format_summary(results: list[dict]) -> str:
    """One-line-per-component summary."""
    lines = []
    for r in results:
        dead = len(r['emitted_not_read'])
        hidden = len(r['read_not_emitted'])
        matched = len(r['matched'])
        found = r['enhance_found']

        if not found:
            status = 'NO ENHANCE'
        elif dead == 0 and hidden == 0:
            status = 'OK'
        else:
            parts = []
            if dead:
                parts.append(f'{dead} dead')
            if hidden:
                parts.append(f'{hidden} hidden')
            status = ', '.join(parts)

        lines.append(f'  {r["component"]:<15} [{status}] ({matched} matched)')

    return '\n'.join(lines)


def format_json(results: list[dict]) -> str:
    """JSON output for programmatic consumption."""
    import json
    return json.dumps(results, indent=2)
