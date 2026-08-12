"""Scope-awareness of the L1.18b module-state classifier.

A module-level binding and a function-local of the SAME name are different bindings
(Python scoping: a name assigned in a function body is local to that function unless
declared ``global``). The classifier collects references by name across the file, so a
same-named local could wrongly attach to the module global's finding and poison its
verdict. These lock the fix: a shadowing local's uses never change the module binding's
verdict, while a genuine escape of the module binding itself still stands.

Found against declaro-persistum's ``audit_log = table(...)`` module handle, which a
function-local ``audit_log = build_audit_log(...)`` shadowed one function away.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds


def _verdict(src: str, name: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        return next((f["verdict"] for f in r["findings"] if f["state"] == name), "absent")


# --- CLEAR: the module binding is benign; a same-named local must not poison it ---

def test_module_global_not_poisoned_by_shadowing_local_escape():
    # `h` is a module handle used only as a method receiver (neutral). A DIFFERENT,
    # same-named function-local escapes to an unknown callee. That local is scoped to its
    # function and must not attach to the module global's verdict.
    src = ("h = table('x', schema=s)\n"
           "def make(pool):\n    h = build(1)\n    return serialize(h)\n"
           "def q(pool):\n    return h.select()\n")
    assert _verdict(src, "h") == "neutral"


def test_module_global_not_poisoned_by_shadowing_parameter():
    # A parameter named `h` is local to its function; its escape is not the global's.
    src = ("h = table('x', schema=s)\n"
           "def make(h):\n    return serialize(h)\n"
           "def q(pool):\n    return h.select()\n")
    assert _verdict(src, "h") == "neutral"


# --- KEEP: genuine findings the scope fix must NOT clear -------------------------

def test_module_global_that_itself_escapes_stays_unresolved():
    # No shadow: the module binding itself is handed to an unknown callee. Real finding.
    src = ("h = build()\n"
           "def q():\n    return serialize(h)\n")
    assert _verdict(src, "h") == "unresolved"


def test_global_declared_rebind_still_attaches_to_the_module_binding():
    # `global h` means the function rebinds the MODULE binding, not a local. Its refs must
    # still attach, so a later escape of the global stays visible.
    src = ("h = build()\n"
           "def swap():\n    global h\n    h = other()\n"
           "def q():\n    return serialize(h)\n")
    assert _verdict(src, "h") == "unresolved"
