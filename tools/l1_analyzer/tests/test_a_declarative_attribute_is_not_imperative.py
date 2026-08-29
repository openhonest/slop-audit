"""We reported the declarative form as the imperative one.

Reported by an adopter, three times, once per copy of the same example file.

    <form hx-post="/db/sqlite" hx-target="#db-result" hx-swap="innerHTML">

`hx-swap` is the framework's own attribute and `innerHTML` is one of its six values. It says
where the response goes, in the markup, on the element it applies to. That is exactly the
shape this clause asks for, and the finding read "innerHTML describes how, somewhere the
reader has to go and find". There is nowhere to go: it is on the element.

Their guess at the cause was right. The check searched the file's text for the word rather
than asking where the word sits. The whole page is attributes; the only script tag loads the
framework from a network address and contains nothing.

The narrowing is the same shape as an earlier one this week, where a decorator name belonged
to two libraries: ask where the name sits, not whether it appears.

A name in a script is imperative. The same name as the value of an attribute the framework
owns is the remedy, and reporting the remedy is the worst thing a rule can do.
"""

import pytest
from l1_analyzer import honest_code_rules as rules

_DECLARATIVE = '''<form hx-post="/db/sqlite" hx-target="#db-result" hx-swap="innerHTML">
  <button type="submit">Run</button>
</form>
<script src="https://unpkg.com/htmx.org@2"></script>
'''

_IMPERATIVE = '''<div id="out"></div>
<script>
  document.querySelector("#out").innerHTML = render(data);
</script>
'''


def _found(source: str, name: str = "page.html") -> list[dict]:
    """Built the way the analyzer builds it. Markup has no shared node vocabulary, so
    read_tree cannot make one and the file reader is the only thing that can."""
    from l1_analyzer import honest_code

    return rules.imperative_dom(honest_code.read_source_text(source, name)) or []


@pytest.mark.parametrize("value", ["innerHTML", "outerHTML", "beforebegin", "afterbegin",
                                   "beforeend", "afterend"])
def test_each_value_the_framework_attribute_takes_is_left_alone(value):
    page = _DECLARATIVE.replace("innerHTML", value)
    assert _found(page) == [], value


def test_a_page_that_is_only_attributes_reports_nothing():
    assert _found(_DECLARATIVE) == []


def test_the_same_name_written_in_script_is_still_reported():
    """The direction that must not move. This is the shape the clause exists to find."""
    found = _found(_IMPERATIVE)
    assert found, "an assignment in script is imperative"
    assert any("innerHTML" in f["symbol"] or "querySelector" in f["symbol"] for f in found)


def test_a_listener_added_in_script_is_still_reported():
    assert _found('<script>\n  el.addEventListener("click", go);\n</script>\n')


def test_a_javascript_file_is_read_as_script_throughout():
    """No markup to sit in, so every occurrence is imperative by construction."""
    assert _found('document.querySelector("#a").innerHTML = "x";\n', "app.js")


def test_a_page_with_both_reports_only_the_script_half():
    """The case that decides whether this is worth having: a real page carries declarative
    attributes and a little script, and only one of the two is a finding."""
    both = _DECLARATIVE + _IMPERATIVE
    found = _found(both)
    assert found, "the script half is still reported"
    for finding in found:
        assert finding["line"] > _DECLARATIVE.count("\n"), finding
