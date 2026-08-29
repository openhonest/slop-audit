"""
Pure functions for comparing playground controls against enhance capabilities.

No I/O, no side effects. Accepts extracted metadata, returns audit results.
"""



# One component's reading, and the difference between two of them. Both were written `dict`,
# the least precise mapping the language has, with the key always a string.
Reading = dict[str, object]



def normalize_attr_to_opt(attr_name: str) -> str:
    """
    Convert a ux-* attribute name (kebab) to the opts property name (camelCase).

    'hover-bg' -> 'hoverBg'
    'color' -> 'color'
    'border-color' -> 'borderColor'
    'data-tooltip' -> 'tooltip'  (strip data- prefix)
    """
    if attr_name.startswith('data-'):
        attr_name = attr_name[5:]

    parts = attr_name.split('-')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])
def compare_component(
    component_name: str,
    playground_data: Reading,
    enhance_data: Reading | None,
) -> Reading:
    """
    Compare what a playground component emits vs what enhance reads.

    Returns: {
        'component': str,
        'enhance_name': str,
        'enhance_found': bool,
        'emitted_not_read': [{'attr': str, 'as_opt': str}],  # dead controls
        'read_not_emitted': [str],                             # hidden features
        'matched': [{'attr': str, 'opt': str}],               # properly wired
        'options_summary': {key: type},                        # all playground controls
    }
    """
    enhance_name = playground_data.get('enhance_name', component_name)
    render_attrs = playground_data.get('render_attrs', [])
    options = playground_data.get('options', {})

    result = {
        'component': component_name,
        'enhance_name': enhance_name,
        'enhance_found': enhance_data is not None,
        'emitted_not_read': [],
        'read_not_emitted': [],
        'matched': [],
        'options_summary': options,
    }

    if enhance_data is None:
        # No enhance function found — all emitted attrs are dead
        result['emitted_not_read'] = [
            {'attr': attr, 'as_opt': normalize_attr_to_opt(attr)}
            for attr in render_attrs
        ]
        return result

    opts_read = set(enhance_data.get('opts_read', []))

    # Normalize render attrs to camelCase for comparison
    attr_to_opt = {attr: normalize_attr_to_opt(attr) for attr in render_attrs}

    # Check each emitted attribute against what enhance reads
    for attr, opt_name in attr_to_opt.items():
        if opt_name in opts_read:
            result['matched'].append({'attr': attr, 'opt': opt_name})
        else:
            result['emitted_not_read'].append({'attr': attr, 'as_opt': opt_name})

    # Check for enhance opts not emitted by playground
    emitted_opts = set(attr_to_opt.values())
    for opt in sorted(opts_read):
        if opt not in emitted_opts:
            # Skip common internal opts that aren't from attributes
            if opt not in ('type', 'el', 'element', 'name', 'enhance'):
                result['read_not_emitted'].append(opt)

    return result


def audit_all(
    playground_components: Reading,
    enhance_functions: Reading,
) -> list[Reading]:
    """
    Run comparison for all components.

    Returns list of audit results, sorted by severity (most mismatches first).
    """
    results = []

    for name, pg_data in playground_components.items():
        enhance_name = pg_data.get('enhance_name', name)
        enh_data = enhance_functions.get(enhance_name)
        result = compare_component(name, pg_data, enh_data)
        results.append(result)

    # Sort: components with issues first, then by number of dead controls
    results.sort(
        key=lambda r: (-len(r['emitted_not_read']), -len(r['read_not_emitted']), r['component'])
    )

    return results
