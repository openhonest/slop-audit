"""
ui-audit: Polymorphic UI component audit tool.

Compares what a playground/configurator offers (controls) against
what the component library's enhance/render functions actually support.
Catches dead controls, hidden features, and wiring mismatches.

Usage:
    from ui_audit import audit

    results = audit(
        playground_source=open('playground.js').read(),
        enhance_source=open('uix.js').read(),
        attr_prefix='ux-',
    )
"""

from .lib.extract import extract_playground_components, extract_enhance_functions
from .lib.compare import audit_all
from .lib.report import format_text, format_summary, format_json


def audit(
    playground_source: str,
    enhance_source: str,
    attr_prefix: str = 'ux-',
    output: str = 'text',
) -> str | list[dict]:
    """
    Run a full audit: extract, compare, report.

    Args:
        playground_source: Full text of the playground JS file
        enhance_source: Full text of the component library JS file
        attr_prefix: Attribute prefix (e.g., 'ux-', 'dx-')
        output: 'text', 'summary', 'json', or 'raw' (returns list of dicts)

    Returns:
        Formatted string, or raw results list if output='raw'
    """
    playground = extract_playground_components(playground_source, attr_prefix)
    enhancers = extract_enhance_functions(enhance_source)
    results = audit_all(playground, enhancers)

    FORMAT_DISPATCH = {
        'text': format_text,
        'summary': format_summary,
        'json': format_json,
        'raw': lambda r: r,
    }

    formatter = FORMAT_DISPATCH.get(output, format_text)
    return formatter(results)
