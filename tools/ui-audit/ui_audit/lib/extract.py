"""
Pure functions for extracting component metadata from source text.

No I/O, no side effects. Accepts source strings, returns plain dicts.
"""

import re


# ── Helpers ──────────────────────────────────────────────────────────

def _extract_brace_block(source: str, start: int) -> str:
    """Extract text from opening { to matching }, handling nesting."""
    depth = 0
    i = start
    while i < len(source):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    return source[start:]


def _kebab_to_camel(s: str) -> str:
    """Convert kebab-case to camelCase: 'hover-bg' -> 'hoverBg'."""
    parts = s.split('-')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def _camel_to_kebab(s: str) -> str:
    """Convert camelCase to kebab-case: 'hoverBg' -> 'hover-bg'."""
    return re.sub(r'([a-z])([A-Z])', r'\1-\2', s).lower()


# ── Playground extraction ────────────────────────────────────────────

def extract_playground_components(source: str, attr_prefix: str = 'ux-') -> dict[str, dict]:
    """
    Extract component configs from playground source text.

    Returns: {
        'button': {
            'enhance_name': 'button',
            'options': {'variant': 'select', 'bgColor': 'color', ...},
            'render_attrs': ['variant', 'size', 'bg', 'color', ...],  # kebab attrs without prefix
        },
        ...
    }
    """
    results = {}

    # Find componentConfigs object
    configs_match = re.search(r'const\s+componentConfigs\s*=\s*\{', source)
    if not configs_match:
        return results

    configs_block = _extract_brace_block(source, configs_match.end() - 1)

    # Split into individual component blocks
    # Pattern: component_name: { ... at top-level indentation
    component_pattern = re.compile(
        r'^\s{8}(\w+):\s*\{',
        re.MULTILINE
    )

    matches = list(component_pattern.finditer(configs_block))

    for i, match in enumerate(matches):
        name = match.group(1)
        # Get the block for this component
        block_start = match.start() + configs_block[:match.start()].count('')
        block = _extract_brace_block(configs_block, match.end() - 1)

        component = _extract_single_component(name, block, attr_prefix)
        if component:
            results[name] = component

    return results


def _extract_single_component(name: str, block: str, attr_prefix: str) -> dict | None:
    """Extract metadata from a single component config block."""
    # Extract enhance name
    enhance_match = re.search(r"enhance:\s*'(\w+)'", block)
    enhance_name = enhance_match.group(1) if enhance_match else name

    # Extract options and their types
    options = _extract_options(block)

    # Extract ux-* attributes from render function
    render_attrs = _extract_render_attrs(block, attr_prefix)

    return {
        'enhance_name': enhance_name,
        'options': options,
        'render_attrs': render_attrs,
    }


def _extract_options(block: str) -> dict[str, str]:
    """Extract option keys and their types from an options block."""
    options = {}

    # Find the options: { ... } block
    opts_match = re.search(r'options:\s*\{', block)
    if not opts_match:
        return options

    opts_block = _extract_brace_block(block, opts_match.end() - 1)

    # Find each option key and its type
    # Pattern: optionName: { ... type: 'select' ... }
    opt_pattern = re.compile(r'(\w+):\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', re.DOTALL)

    for match in opt_pattern.finditer(opts_block):
        opt_name = match.group(1)
        opt_body = match.group(2)

        type_match = re.search(r"type:\s*'(\w+)'", opt_body)
        if type_match:
            options[opt_name] = type_match.group(1)

    return options


def _extract_render_attrs(block: str, attr_prefix: str) -> list[str]:
    """Extract ux-* attribute names emitted by the render function."""
    attrs = set()

    # Find render function
    render_match = re.search(r'render:\s*\(opts\)\s*=>', block)
    if not render_match:
        return []

    # Get everything from render: to end of its function body
    render_start = render_match.start()
    # Find the opening { of the arrow function
    brace_pos = block.find('{', render_match.end())
    if brace_pos == -1:
        return []

    render_body = _extract_brace_block(block, brace_pos)

    # Extract ux-* ATTRIBUTE names from the render body
    # Match: ux-variant="...", ux-bg="...", etc.
    # Skip: ux-enhance="...", ux-enhanced, class names like ux-table--striped
    prefix_escaped = re.escape(attr_prefix)

    # Only match attributes (followed by = or interpolation), not class names
    attr_pattern = re.compile(prefix_escaped + r'([a-z][-a-z]*)(?=="|=\'|\$\{|=")')

    for match in attr_pattern.finditer(render_body):
        attr_name = match.group(1)
        # Skip the enhance directive itself and the enhanced marker
        if attr_name in ('enhance', 'enhanced'):
            continue
        attrs.add(attr_name)

    # Also capture data-* attributes that serve as ux attributes
    data_pattern = re.compile(r'data-([a-z][-a-z]*)=')
    for match in data_pattern.finditer(render_body):
        attrs.add(f'data-{match.group(1)}')

    return sorted(attrs)


# ── Enhance function extraction ──────────────────────────────────────

def extract_enhance_functions(source: str) -> dict[str, dict]:
    """
    Extract enhance function metadata from UIX library source.

    Returns: {
        'button': {
            'opts_read': ['bg', 'color', 'variant', 'size', ...],  # camelCase
            'css_vars_set': ['--ux-btn-bg', '--ux-btn-color', ...],
            'classes_added': ['ux-btn', 'ux-btn--primary', ...],
        },
        ...
    }
    """
    results = {}

    # First, extract helper functions that receive opts and read from them
    # e.g., applyColorStyles(el, opts) reads opts.bg, opts.color, opts.borderColor
    helper_opts = _extract_helper_opts(source)

    # Find the enhance object
    enhance_match = re.search(r'const\s+enhance\s*=\s*\{', source)
    if not enhance_match:
        return results

    enhance_block = _extract_brace_block(source, enhance_match.end() - 1)

    # Find each enhance function
    # Pattern: componentName: (el, opts) => {
    func_pattern = re.compile(
        r'(\w+):\s*\(el,\s*opts\)\s*=>\s*\{'
    )

    matches = list(func_pattern.finditer(enhance_block))

    for i, match in enumerate(matches):
        name = match.group(1)
        func_body = _extract_brace_block(enhance_block, match.end() - 1)

        metadata = _extract_enhance_metadata(func_body)

        # If the function delegates to a helper that reads opts, include those
        for helper_name, helper_opts_list in helper_opts.items():
            # Check if this enhance function calls the helper with opts
            if re.search(rf'{helper_name}\s*\([^)]*opts[^)]*\)', func_body):
                for opt in helper_opts_list:
                    if opt not in metadata['opts_read']:
                        metadata['opts_read'].append(opt)
                metadata['opts_read'].sort()

        results[name] = metadata

    return results


def _extract_helper_opts(source: str) -> dict[str, list[str]]:
    """
    Extract opts properties read by helper functions that receive opts as a parameter.

    Finds patterns like: const applyColorStyles = (el, opts) => { ... opts.bg ... opts.color ... }
    """
    helpers = {}

    # Match: const helperName = (el, opts) => { ... } or (params including opts)
    helper_pattern = re.compile(
        r'const\s+(\w+)\s*=\s*\([^)]*opts[^)]*\)\s*=>\s*\{'
    )

    for match in helper_pattern.finditer(source):
        name = match.group(1)
        body = _extract_brace_block(source, match.end() - 1)
        opts_pattern = re.compile(r'opts\.(\w+)')
        opts = sorted(set(m.group(1) for m in opts_pattern.finditer(body)))
        if opts:
            helpers[name] = opts

    return helpers


def _extract_enhance_metadata(func_body: str) -> dict:
    """Extract metadata from a single enhance function body."""
    # Extract all opts.* property accesses
    opts_pattern = re.compile(r'opts\.(\w+)')
    opts_read = sorted(set(m.group(1) for m in opts_pattern.finditer(func_body)))

    # Extract CSS custom properties set
    css_var_pattern = re.compile(r"setProperty\('(--ux[^']+)'")
    css_vars_set = sorted(set(m.group(1) for m in css_var_pattern.finditer(func_body)))

    # Extract classes added
    class_pattern = re.compile(r"classList\.add\(['\"]([^'\"]+)")
    classes_added = sorted(set(m.group(1) for m in class_pattern.finditer(func_body)))

    # Also capture template literal class additions: `ux-btn--${opts.variant}`
    template_class_pattern = re.compile(r"classList\.add\(`([^`]+)`\)")
    for m in template_class_pattern.finditer(func_body):
        classes_added.append(m.group(1))

    return {
        'opts_read': opts_read,
        'css_vars_set': css_vars_set,
        'classes_added': classes_added,
    }
