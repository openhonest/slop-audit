"""The four-column call-stack map, and the `.hd` file it renders as.

`.hd` is the Honest Framework's own plain-text architecture spec. The grammar here is that
one rather than a private dialect, so what this emits stays readable by the framework's own
tooling: roles are function prefixes, I/O lives on the outside in columns one and four, and
pure logic sits in the middle.

  boundary_in fn    inbound I/O, reads a source
  orchestrator fn   composes other functions
  fn                pure core, no side effects
  boundary_out fn   outbound I/O, writes a target

The violation the map exists to show is a write sitting in the pure lane: a bare `fn`
carrying `side_effect writes`. It is emitted that way on purpose rather than quietly moved
to column four, because the point is to SHOW the write where nothing should write.

One thing here a reader of the source alone does not have. The audit already watched the
suite run, so a function whose purity BREAKS was seen writing, and the charge rests on that
rather than on a guess. A function nobody watched is not accused at all: silence about a
property is not evidence of a violation.

A layer is not on that list. `layer foundation|data|domain|ui|tooling` is an architectural
intent and no reading of the source decides it, so the caller states it or the file says
nobody did.
"""

import ast
from typing import TypedDict

from l1_analyzer.facets import called_name

ROLES = ("boundary_in", "orchestrator", "pure", "boundary_out")

# What a call touches, by the name being called. A dict rather than a chain of tests, so a
# reader can see the whole vocabulary at once and adding a source is adding a row.
_READS = {
    "read_text": "filesystem", "read_bytes": "filesystem", "iterdir": "filesystem",
    "glob": "filesystem", "rglob": "filesystem", "exists": "filesystem",
    "is_file": "filesystem", "is_dir": "filesystem", "stat": "filesystem",
    "listdir": "filesystem", "walk": "filesystem",
    "getenv": "environment", "environ": "environment",
    "input": "stdin",
    "run": "subprocess", "Popen": "subprocess", "check_output": "subprocess",
    "import_module": "import",
    "loads": "", "get": "",
}
_WRITES = {
    "write_text": "filesystem", "write_bytes": "filesystem", "mkdir": "filesystem",
    "unlink": "filesystem", "rmdir": "filesystem", "rename": "filesystem",
    "touch": "filesystem", "makedirs": "filesystem", "remove": "filesystem",
    "print": "stdout",
    "setattr": "namespace", "delattr": "namespace",
    "write": "file",
}

# `open` decides for itself, by its mode argument.
_WRITE_MODES = ("w", "a", "x", "+")


class Role(TypedDict):
    """One function's column, and what put it there."""

    function: str
    role: str
    parameters: str
    returns: str
    reads: list[str]
    writes: list[str]
    invokes: list[str]
    violation: str


def _open_writes(call: ast.Call) -> bool:
    """Whether this `open` was opened for writing. Read is the default, as it is in Python,
    so a call with no mode is a read rather than an unknown."""
    mode = ""
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        mode = str(call.args[1].value)
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            mode = str(keyword.value.value)
    return any(letter in mode for letter in _WRITE_MODES)


def _made_here(fn: ast.FunctionDef) -> set[str]:
    """Names this function created: its own locals and its nested definitions.

    Writing to something you made is not outbound I/O. A wrapper that sets an attribute on
    the closure it just built was filed in column four on that basis, which puts a pure
    function where a reader is looking for the real writes."""
    made: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            made.add(node.name)
        if isinstance(node, ast.Assign):
            made |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            made.add(node.target.id)
        if isinstance(node, (ast.With, ast.AsyncWith)):
            made |= {item.optional_vars.id for item in node.items
                     if isinstance(item.optional_vars, ast.Name)}
    return made - {fn.name}


def effects(fn: ast.FunctionDef) -> tuple[list[str], list[str]]:
    """The sources this function reads and the targets it writes, each named once.

    Named rather than counted: `side_effect reads "filesystem"` tells a reader what the
    boundary IS, and a number would only tell them how often."""
    reads: list[str] = []
    writes: list[str] = []
    local = _made_here(fn)

    def note(into: list[str], source: str) -> None:
        if source and source not in into:
            into.append(source)

    for node in ast.walk(fn):
        if isinstance(node, ast.Global):
            note(writes, "namespace")
        if isinstance(node, ast.Attribute) and node.attr == "environ":
            note(reads, "environment")
        if not isinstance(node, ast.Call):
            continue
        name = called_name(node)
        if name == "open":
            note(writes if _open_writes(node) else reads, "file")
            continue
        if name in ("setattr", "delattr"):
            target = node.args[0] if node.args else None
            if not (isinstance(target, ast.Name) and target.id in local):
                note(writes, "namespace")
            continue
        note(reads, _READS.get(name, ""))
        note(writes, _WRITES.get(name, ""))
    return reads, writes


def invocations(fn: ast.FunctionDef, siblings: set[str]) -> list[str]:
    """The functions of this same module that this one calls, sorted.

    Its own name is left out: recursion is a fact about the function rather than about what
    it composes, and an orchestrator that lists itself reads as composing nothing else."""
    return sorted({called_name(node) for node in ast.walk(fn)
                   if isinstance(node, ast.Call)} & siblings - {fn.name})


def role_of(reads: list[str], writes: list[str], invokes: list[str]) -> str:
    """Which of the four columns this function belongs in.

    A write outranks a read. The map's whole point is where the writes are, so a function
    doing both belongs in the column a reader is looking for."""
    if writes:
        return "boundary_out"
    if reads:
        return "boundary_in"
    return "orchestrator" if invokes else "pure"


def _first_mutable(fn: ast.FunctionDef) -> str:
    """The parameter an observed mutation is about, named from the signature."""
    for argument in fn.args.args:
        if argument.arg not in ("self", "cls"):
            return argument.arg
    return ""


def classify(tree: ast.AST, watched: dict[str, dict[str, str]]) -> list[Role]:
    """Every function in the module, with its column and any demonstrated violation.

    `watched` is what the run showed. A purity verdict of `breaks` on a function sitting in
    the pure lane is the violation; anything else, including having no verdict, is not."""
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    siblings = {fn.name for fn in functions}
    out: list[Role] = []
    for fn in functions:
        reads, writes = effects(fn)
        invokes = invocations(fn, siblings)
        role = role_of(reads, writes, invokes)
        seen = watched.get(fn.name, {})
        violation = ""
        # The format's own example is a pure-position `fn` that writes its ARGUMENT, so an
        # observed mutation names the argument and an observed impurity names the module.
        if seen.get("mutation", "") == "breaks":
            mutated = _first_mutable(fn)
            if mutated and mutated not in writes:
                writes = [*writes, mutated]
        if seen.get("purity", "") == "breaks" and "namespace" not in writes:
            writes = [*writes, "namespace"]
        if writes and role in ("pure", "orchestrator"):
            violation = ("observed writing while the suite ran, and its column declares no "
                         "write")
        out.append({
            "function": fn.name, "role": role,
            "parameters": ast.unparse(fn.args),
            "returns": ast.unparse(fn.returns) if fn.returns else "",
            "reads": reads, "writes": writes, "invokes": invokes, "violation": violation,
        })
    return out


def _stanza(role: Role) -> str:
    """One function as one line of `.hd`.

    A violation keeps the bare `fn` prefix with the write still attached. Moving it to
    `boundary_out` would make the file describe an honest module, which is the opposite of
    what the map is for."""
    prefix = "" if role["role"] == "pure" else role["role"] + " "
    if role["violation"]:
        prefix = ""
    returns = f" -> {role['returns']}" if role["returns"] else ""
    line = f"  {prefix}fn {role['function']} : ({role['parameters']}){returns}"
    for source in role["reads"]:
        line += f' side_effect reads "{source}"'
    for target in role["writes"]:
        line += f' side_effect writes "{target}"'
    if role["invokes"]:
        line += " invokes " + ", ".join(role["invokes"])
    if role["violation"]:
        line += f"   # VIOLATION: write in the pure lane, {role['violation']}"
    return line


def render(roles: list[Role], module: str, layer: str) -> str:
    """The module as a `.hd` file, in column order."""
    lines = [f"module {module}", ""]
    if layer:
        lines.append(f"  layer {layer}")
    else:
        lines.append("  # layer not declared: a layer is an architectural intent and no "
                     "reading of the source decides it")
    lines.append("")
    for column in ROLES:
        in_column = [r for r in roles if r["role"] == column]
        if not in_column:
            continue
        lines.append(f"  # --- {column} " + "-" * (60 - len(column)))
        lines += [_stanza(role) for role in in_column]
        lines.append("")
    return "\n".join(lines)


def read_roles(rendered: str) -> dict[str, str]:
    """The function-to-column mapping, read back out of a rendered file.

    A format nobody can read back is a report rather than a spec, and this is what says
    the two directions agree."""
    found: dict[str, str] = {}
    for line in rendered.split("\n"):
        stripped = line.split("#")[0].strip()
        if " fn " in stripped:
            prefix, _, rest = stripped.partition(" fn ")
            found[rest.split(" :")[0].strip()] = prefix.strip()
        elif stripped.startswith("fn "):
            found[stripped[3:].split(" :")[0].strip()] = "pure"
    return found
