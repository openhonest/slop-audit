"""
Phase 2: Playwright visual verification for flagged components.

Interacts with real browser — hover, click, screenshot.
Only runs for components/controls flagged by Phase 1.

Requires: playwright (optional dependency)
"""

import asyncio
from pathlib import Path
async def verify_components(
    url: str,
    components: list[dict],
    screenshot_dir: str = '.audit/screenshots',
    playground_selector: str = '[data-playground]',
) -> list[dict]:
    """
    Visually verify flagged components using Playwright.

    Args:
        url: Playground page URL
        components: List of Phase 1 audit results (only those with issues)
        screenshot_dir: Where to save screenshots
        playground_selector: CSS selector for playground containers

    Returns:
        List of visual verification results with screenshot paths
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return [{'error': 'playwright not installed. Run: uv pip install playwright && playwright install'}]

    screenshots = Path(screenshot_dir)
    screenshots.mkdir(parents=True, exist_ok=True)

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto(url, wait_until='networkidle')

        for component in components:
            name = component['component']
            result = await _verify_single_component(
                page, name, component, screenshots, playground_selector
            )
            results.append(result)

        await browser.close()

    return results


async def _verify_single_component(
    page,
    name: str,
    audit_result: dict,
    screenshot_dir: Path,
    playground_selector: str,
) -> dict:
    """Verify a single component's controls visually."""
    result = {
        'component': name,
        'screenshots': [],
        'observations': [],
    }

    # Scroll to the component section
    section = page.locator(f'{playground_selector}="{name}"')
    try:
        await section.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        result['observations'].append(f'Could not find section for {name}')
        return result

    # Take default state screenshot
    default_path = screenshot_dir / f'{name}-default.png'
    await section.screenshot(path=str(default_path))
    result['screenshots'].append({'state': 'default', 'path': str(default_path)})

    # For dead controls: change each one and screenshot to confirm no visual change
    for dead in audit_result.get('emitted_not_read', []):
        attr = dead['attr']
        opt_name = dead['as_opt']

        # Find the control for this option
        control_result = await _test_dead_control(
            page, section, name, opt_name, attr, screenshot_dir
        )
        if control_result:
            result['screenshots'].append(control_result)
            result['observations'].append(
                f'Dead control {opt_name}: changed to test value, '
                f'visual {"changed" if control_result.get("visual_changed") else "unchanged"}'
            )

    # For matched controls with hover: test hover states
    for matched in audit_result.get('matched', []):
        if matched['opt'] in ('hoverBg', 'hoverColor'):
            hover_result = await _test_hover_control(
                page, section, name, matched, screenshot_dir
            )
            if hover_result:
                result['screenshots'].append(hover_result)

    return result


async def _test_dead_control(
    page, section, name: str, opt_name: str, attr: str, screenshot_dir: Path,
) -> dict | None:
    """Change a dead control and screenshot to confirm it has no visual effect."""
    # Find the control by label text matching the option name
    # Convert camelCase to human label: 'hoverBg' -> 'Hover Bg' (approximate)
    import re
    label_text = re.sub(r'([A-Z])', r' \1', opt_name).strip().title()

    try:
        # Try to find a control group with this label
        control_group = section.locator('.ux-playground__control').filter(
            has=page.locator(f'.ux-playground__label:text-is("{label_text}")')
        ).first

        if not await control_group.is_visible(timeout=1000):
            return None

        # Find the input element
        color_input = control_group.locator('input[type="color"]')
        text_input = control_group.locator('input[type="text"]')
        select_input = control_group.locator('select')
        checkbox_input = control_group.locator('input[type="checkbox"]')

        changed = False
        if await color_input.count() > 0:
            await color_input.fill('#ff0000')
            await color_input.dispatch_event('input')
            changed = True
        elif await select_input.count() > 0:
            options = await select_input.locator('option').all()
            if len(options) > 1:
                val = await options[1].get_attribute('value')
                await select_input.select_option(val)
                changed = True
        elif await text_input.count() > 0:
            await text_input.fill('TEST')
            await text_input.dispatch_event('input')
            changed = True
        elif await checkbox_input.count() > 0:
            await checkbox_input.check()
            changed = True

        if not changed:
            return None

        # Screenshot after change
        screenshot_path = screenshot_dir / f'{name}-{opt_name}-changed.png'
        await section.screenshot(path=str(screenshot_path))

        return {
            'state': f'{opt_name}-changed',
            'path': str(screenshot_path),
            'control_type': 'dead',
            'visual_changed': None,  # Needs human/AI review
        }

    except Exception as e:
        return {'state': f'{opt_name}-error', 'error': str(e)}


async def _test_hover_control(
    page, section, name: str, matched: dict, screenshot_dir: Path,
) -> dict | None:
    """Test a hover-related control with real mouse hover."""
    try:
        preview = section.locator('.ux-playground__preview')
        if not await preview.is_visible(timeout=1000):
            return None

        # Find the first interactive element in preview
        interactive = preview.locator('a, button, [role="menuitem"], [role="tab"]').first
        if not await interactive.is_visible(timeout=1000):
            return None

        # Hover and screenshot
        await interactive.hover()
        await page.wait_for_timeout(200)  # Let CSS transition settle

        screenshot_path = screenshot_dir / f'{name}-hover-{matched["opt"]}.png'
        await section.screenshot(path=str(screenshot_path))

        return {
            'state': f'hover-{matched["opt"]}',
            'path': str(screenshot_path),
            'control_type': 'hover',
        }

    except Exception:
        return None


# ── Sync wrapper ─────────────────────────────────────────────────────

def run_visual_audit(
    url: str,
    audit_results: list[dict],
    screenshot_dir: str = '.audit/screenshots',
    only_failures: bool = True,
) -> list[dict]:
    """
    Synchronous entry point for visual verification.

    Args:
        url: Playground page URL
        audit_results: Phase 1 results from audit()
        screenshot_dir: Where to save screenshots
        only_failures: If True, only test components with issues
    """
    if only_failures:
        components = [r for r in audit_results if r['emitted_not_read'] or r['read_not_emitted']]
    else:
        components = audit_results

    return asyncio.run(verify_components(url, components, screenshot_dir))
