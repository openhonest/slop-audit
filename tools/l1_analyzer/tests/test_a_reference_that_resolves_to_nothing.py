"""References Resolve Statically, which had no clause until now.

The principle, from the canon: every identifier a rendered artifact names is a reference
across a boundary. An `hx-get` names a route, a `class` names a stylesheet rule, an include
names a template. Asserting that the artifact contains the string proves it was written, not
that it resolves, so two green tests can describe a button and a menu that never connect.

Two of those three are decidable from the repository alone, and this clause decides those
two. A template naming a file that is not there. A class attribute naming a rule no
stylesheet defines.

The third is not. Where a project declares its routes is a convention this reader does not
know, and guessing at one would report every link in every repository whose framework we
guessed wrong. It says so rather than reporting a number that means nothing.
"""

import pytest
from l1_analyzer import honest_code_references as references


def _page(tmp_path, name, body):
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text(body)
    return tmp_path


def test_a_template_naming_a_file_that_is_not_there_is_reported(tmp_path):
    repo = _page(tmp_path, "templates/page.html",
                 '{% include "parts/missing.html" %}\n<p>hello</p>\n')
    found = references.unresolved_references(repo)
    assert [f["symbol"] for f in found] == ["parts/missing.html"], found
    assert "resolves to nothing" in found[0]["detail"]


def test_a_template_naming_a_file_that_is_there_is_left_alone(tmp_path):
    repo = _page(tmp_path, "templates/page.html", '{% include "parts/head.html" %}\n')
    (repo / "templates" / "parts").mkdir(parents=True)
    (repo / "templates" / "parts" / "head.html").write_text("<title>x</title>\n")
    assert references.unresolved_references(repo) == []


@pytest.mark.parametrize("directive", ["include", "extends", "import"])
def test_each_way_a_template_names_another_is_read(directive, tmp_path):
    repo = _page(tmp_path, "page.html", f'{{% {directive} "gone.html" %}}\n')
    assert references.unresolved_references(repo), directive


def test_a_class_no_stylesheet_defines_is_reported(tmp_path):
    repo = _page(tmp_path, "page.html", '<div class="card missing-rule">x</div>\n')
    (repo / "site.css").write_text(".card { color: red }\n")
    found = references.unresolved_references(repo)
    assert [f["symbol"] for f in found] == ["missing-rule"], found


def test_a_class_a_stylesheet_defines_is_left_alone(tmp_path):
    repo = _page(tmp_path, "page.html", '<div class="card">x</div>\n')
    (repo / "site.css").write_text(".card { color: red }\n")
    assert references.unresolved_references(repo) == []


def test_a_repository_with_no_stylesheet_at_all_decides_no_classes(tmp_path):
    """Nothing to resolve against. Reporting every class in the file would be a finding
    about this reader rather than about the code."""
    repo = _page(tmp_path, "page.html", '<div class="card">x</div>\n')
    assert references.unresolved_references(repo) == []


def test_a_route_reference_is_not_decided(tmp_path):
    """Stated as a bound. Where a project declares its routes is a convention this reader
    does not know, and guessing wrong would report every link in the repository."""
    repo = _page(tmp_path, "page.html", '<button hx-get="/api/thing">go</button>\n')
    assert references.unresolved_references(repo) == []


def test_a_repository_with_no_rendered_artifact_is_not_decided(tmp_path):
    """None, not an empty list. A repository with no template and no page was not measured
    against a rule about rendered artifacts."""
    (tmp_path / "app.py").write_text("def go():\n    return 1\n")
    assert references.unresolved_references(tmp_path) is None


# ---------------------------------------------------------------------------
# A class the template computes
#
# The first run on this repository reported 32 findings, every one a fragment of a template
# expression: `{{`, `card.status`, `|`, `lower`, `}}`. The reader split the attribute on
# spaces and dropped only the fragments carrying a brace, so the pieces between the braces
# survived as class names.
#
# A computed class cannot be resolved without rendering the page, and rendering it is what
# this clause exists to avoid. So the whole attribute is refused, not the parts of it that
# look like syntax.
# ---------------------------------------------------------------------------

def test_a_class_the_template_computes_is_not_decided(tmp_path):
    repo = _page(tmp_path, "page.html",
                 '<div class="card {{ card.status|lower }}">x</div>\n')
    (repo / "site.css").write_text(".card { color: red }\n")
    assert references.unresolved_references(repo) == []


def test_a_statement_inside_the_attribute_is_refused_too(tmp_path):
    repo = _page(tmp_path, "page.html",
                 '<div class="{% if x %}on{% endif %}">x</div>\n')
    (repo / "site.css").write_text(".on { color: red }\n")
    assert references.unresolved_references(repo) == []


def test_a_plain_attribute_beside_a_computed_one_is_still_read(tmp_path):
    """Refusing the computed attribute must not stop reading the ones written out."""
    repo = _page(tmp_path, "page.html",
                 '<i class="{{ x }}"></i>\n<div class="gone">y</div>\n')
    (repo / "site.css").write_text(".card { color: red }\n")
    found = references.unresolved_references(repo)
    assert [f["symbol"] for f in found] == ["gone"], found


def test_no_helper_below_the_entry_point_touches_the_filesystem():
    """Rule 4 on this module, asserted rather than described. The first version read every
    stylesheet from inside the function that decides, so the decision needed a disk."""
    import pathlib as _p

    from l1_analyzer import honest_code_edges as edges
    from l1_analyzer import honest_code_read as read

    source = _p.Path(references.__file__).read_text()
    found = edges.io_below_the_boundary(read.read_tree(source, "python")) or []
    assert [f["symbol"] for f in found if f["withheld_by"] == ""] == [], found
