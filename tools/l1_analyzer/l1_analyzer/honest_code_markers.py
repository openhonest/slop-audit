"""Three clauses that read what is attached to a declaration, not what the code does.

A lifecycle hook, a cache, and a step definition are each announced by a marker sitting on a
function or a class: a decorator in Python, an annotation in Java, an attribute in C#. Two of
them are also announced by a call that stands in for the marker, which is how JavaScript
registers a hook and how Ruby writes a step. Reading the marker is the whole job, so the two
helpers that read one serve all three clauses.

Split out of `honest_code_rules` when that file crossed a thousand lines and this tool's own
god-file rule failed the commit that pushed it over. It is the second such split; the first
made `honest_code_contracts`.

Every checker is a pure function of a source and returns the sites it found. `None` is the
third answer: the clause was not decided for this file, which is different from an empty list
meaning the clause ran and found nothing.
"""

from l1_analyzer.honest_code_read import (
    Finding,
    _finding,
    called_spelling,
    node_text,
    walk,
)
from l1_analyzer.honest_code_rules import (
    RESOURCE_CALLS,  # noqa: F401 - kept for adopters
)


def _marker_names(marker, raw: bytes) -> list[str]:
    """The names a marker on a declaration is built from.

    A marker is written four ways: Python's `@atexit.register`, Java's `@PostConstruct`, C#'s
    `[OnDeserialized]`. Stripping the punctuation and splitting on dots leaves the names a
    table can hold, so `atexit` matches whether it was written bare or dotted."""
    text = (node_text(marker, raw) or "").lstrip("@[").rstrip("]").split("(")[0]
    return [part.strip() for part in text.split(".")]


def _declaration_marked(marker, spec: dict):
    """The declaration a marker sits on, as a node, or nothing.

    Looked for beside the marker as well as above it. Python wraps a decorator and the
    function it decorates in one parent and makes them SIBLINGS, so walking up alone finds
    the wrapper and never the function. Java and C# nest the marker inside the declaration,
    where walking up is the only thing that works."""
    declared = spec["func_types"] + spec["class_types"]
    holder = marker.parent
    while holder is not None:
        if holder.type in declared:
            return holder
        for sibling in holder.named_children:
            if sibling.type in declared:
                return sibling
        holder = holder.parent
    return None


def _declaration_named(marker, spec: dict, raw: bytes) -> str:
    """What the declaration a marker sits on is called, for the finding to point at.

    Looked for beside the marker as well as above it. Python wraps a decorator and the
    function it decorates in one parent and makes them SIBLINGS, so walking up alone finds
    the wrapper and never the function, and every decorated finding was named after the
    decorator's own text. Java and C# nest the marker inside the declaration, where walking
    up is the only thing that works."""
    holder = _declaration_marked(marker, spec)
    named = holder.child_by_field_name("name") if holder is not None else None
    return (node_text(named, raw) if named is not None else node_text(marker, raw)) or ""


def lifecycle_hooks(source: dict) -> list[Finding] | None:
    """A registration or a marker that runs work somewhere the reader does not look.

    An exit handler, a signal handler, an ORM callback or a mount effect each put behaviour
    where the sequence cannot be read: the call site says nothing and the registration is
    somewhere else. A call at the place it happens is not a hook, however much work it does.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers rather than being reimplemented per language.

    A marker is matched as a NODE, never as text. Reading the unparsed source found a test
    whose data was the string "atexit.register(cleanup)" and reported it as a registration.

    Not decided for a language this table gives no hook vocabulary. Go, Rust and C have none
    here, and Ruby writes a Rails callback as a bare call in a class body, which needs more
    than this table holds to tell from an ordinary call. An empty list would instead claim
    the file was read against this clause and found clean."""
    spec, raw = source["spec"], source["raw"]
    if not spec["hook_marker_types"] and not spec["hook_registrations"]:
        return None
    found: list[Finding] = []
    # A declaration can carry two markers: registered for two events, memoised twice, or a
    # step bound to two scenarios. Reported per marker, it was reported twice. An adopter
    # found the step case, and the other two had it for the same reason.
    seen: set[int] = set()
    for node in walk(source["root"]):
        if node.type in spec["call_types"]:
            named = node.child_by_field_name(spec["call_fn"])
            whole = (node_text(named, raw) or "").split("(")[0].strip()
            if whole in spec["hook_registrations"]:
                found.append(_finding(
                    "L1.21.16", whole, node.start_point[0] + 1,
                    f"{whole} parks behaviour where the reader does not look",
                    "call the work directly at the point it is needed, so the sequence is "
                    "visible at the call site rather than in a registration", ""))
        if node.type in spec["hook_marker_types"]:
            names = _marker_names(node, raw)
            marked = _declaration_marked(node, spec)
            key = marked.id if marked is not None else node.id
            if any(name in spec["hook_markers"] for name in names) and key not in seen:
                seen.add(key)
                owner = _declaration_named(node, spec, raw)
                found.append(_finding(
                    "L1.21.16", owner, node.start_point[0] + 1,
                    f"{'.'.join(names)} runs this somewhere nobody reads",
                    "call the work directly at the point it is needed, so a reader sees it "
                    "in the flow rather than in a registration that runs later", ""))
    return found


_UNPROFILED = ("whether the query was profiled first is not readable from any file, so "
               "only the cache itself was checked")


def _dependency_names(node, spec: dict, raw: bytes) -> list[str]:
    """The identifiers a dependency declaration mentions.

    One text, split on everything that cannot be part of a name, so a library is found
    however the language spells the path around it: Python writes `import redis`, Java
    `redis.clients.jedis.Jedis`, Go a quoted URL and Rust a double-colon path."""
    text = node_text(node, raw) or ""
    word: list[str] = []
    names: list[str] = []
    for char in text:
        if char.isalnum() or char in "_-":
            word.append(char)
        elif word:
            names.append("".join(word))
            word = []
    if word:
        names.append("".join(word))
    return names


def _brings_in_a_dependency(node, spec: dict, raw: bytes) -> bool:
    """Whether this node pulls a library into the file.

    Two shapes. Most languages declare it, and the vocabulary names the declaration. Ruby
    calls `require`, which is an ordinary call node, so a reader looking only for
    declarations finds no dependencies at all in Ruby."""
    if node.type in spec["import_types"]:
        return True
    if node.type not in spec["call_types"] or not spec["dependency_calls"]:
        return False
    return called_spelling(node, spec, raw) in spec["dependency_calls"]


def unmeasured_caches(source: dict) -> list[Finding] | None:
    """A cache library brought into the file, or a memoising marker on a declaration.

    A cache is a second source of truth with an invalidation bug waiting, and the rule asks
    you to profile the query and fix the index or the schema first.

    Partly decided, and saying so is the whole difference between this and a verdict. The
    cache is readable. Whether anyone profiled anything before adding it is in no file, so
    every finding carries that bound rather than implying the whole rule was checked.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers rather than being reimplemented per language.

    Not decided for a language this table gives no cache vocabulary. C brings a dependency
    in as a header, which this rule cannot tell from any other header, and an empty list
    would instead claim the file was read against this clause and found clean."""
    spec, raw = source["spec"], source["raw"]
    if not spec["cache_names"] and not spec["cache_markers"]:
        return None
    found: list[Finding] = []
    # Declarations only. An import and a marker count different things, so a dependency is
    # never deduplicated against a decorator.
    seen: set[int] = set()
    for node in walk(source["root"]):
        if _brings_in_a_dependency(node, spec, raw):
            named = [n for n in _dependency_names(node, spec, raw) if n in spec["cache_names"]]
            if named:
                found.append(_finding(
                    "L1.21.9", named[0], node.start_point[0] + 1,
                    f"{named[0]} is a second source of truth with an invalidation bug waiting",
                    "profile the query and add the index first", _UNPROFILED))
        if node.type in spec["hook_marker_types"]:
            names = _marker_names(node, raw)
            marker = next((n for n in names if n in spec["cache_markers"]), "")
            marked = _declaration_marked(node, spec)
            key = marked.id if marked is not None else node.id
            if marker and key not in seen:
                seen.add(key)
                found.append(_finding(
                    "L1.21.9", _declaration_named(node, spec, raw), node.start_point[0] + 1,
                    f"@{marker} caches the result before anything measured the cost",
                    "profile it and fix the query or the schema first", _UNPROFILED))
    return found


# Where a step stops being a step and starts being the setup the code should not need.
_STEP_LIMIT = 30


def _step_definitions(source: dict) -> list[tuple[str, object]]:
    """Every step definition in this file, as (what to call it, the node holding its body).

    Two shapes. Python, Java and C# mark a declaration with a decorator, an annotation or an
    attribute, so the step is the thing marked. JavaScript and Ruby pass the body to `Given`,
    so the step has no declaration at all and a reader looking for one finds none of them.

    The call form yields the CALL, whose line span is the step, rather than the anonymous
    function inside it."""
    spec, raw = source["spec"], source["raw"]
    steps: list[tuple[str, object]] = []
    # By the node holding the body, because a step can carry more than one marker: a
    # pytest-bdd function bound to three scenarios has three decorators. Collecting markers
    # and mapping each back to its function reported one adopter's step three times and
    # moved their total by two on a day the code did not change. The site is the finding.
    seen: set[int] = set()
    for node in walk(source["root"]):
        marked = (node.type in spec["hook_marker_types"] and spec["step_markers"]
                  and any(n in spec["step_markers"] for n in _marker_names(node, raw)))
        if marked:
            holder = node.parent
            while holder is not None and holder.type not in spec["func_types"]:
                holder = next((c for c in holder.named_children
                               if c.type in spec["func_types"]), None) or holder.parent
            if holder is not None and holder.id not in seen:
                seen.add(holder.id)
                steps.append((_declaration_named(node, spec, raw), holder))
        if node.type in spec["call_types"] and spec["step_calls"]:
            spelling = called_spelling(node, spec, raw)
            if spelling in spec["step_calls"] and node.id not in seen:
                seen.add(node.id)
                steps.append((spelling, node))
    return steps


def heavy_step_definitions(source: dict) -> list[Finding] | None:
    """A step definition longer than thirty lines.

    Step length is a readout on the ARCHITECTURE, not on the test: a step needing thirty
    lines of setup means the code under test has hidden dependencies. A step of one or two
    lines, calling the thing and checking the result, is the shape the rule asks for.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers rather than being reimplemented per language.

    Not decided for a file holding no step definitions, which was not measured against a rule
    about step definitions; saying it passed would be a claim nobody made. Not decided either
    for a language this table gives no step vocabulary, which is Go, Rust and C."""
    spec = source["spec"]
    if not spec["step_markers"] and not spec["step_calls"]:
        return None
    steps = _step_definitions(source)
    if not steps:
        return None
    found: list[Finding] = []
    for name, node in steps:
        if _never_runs(node, spec):
            found.append(_finding(
                "L1.21.15", name, node.start_point[0] + 1,
                "this step never runs: the runner calls it and throws away what it returns, "
                "so an asynchronous body is handed back unstarted",
                "drop the async and call the asynchronous work through a runner inside the "
                "step. Until then, re-read every scenario that asserts an absence, because "
                "those pass on a step that did nothing", ""))
            continue
        if node.end_point[0] - node.start_point[0] > _STEP_LIMIT:
            found.append(_finding(
                "L1.21.15", name, node.start_point[0] + 1,
                f"{node.end_point[0] - node.start_point[0]} lines of setup, which is a "
                "readout on the code under test rather than on the test",
                "make the function under test pure, so the step is call it and check the "
                "result", ""))
    return found


def _never_runs(step, spec: dict) -> bool:
    """Whether this step is handed back to the runner unstarted.

    Reported by a peer on 2026-08-27, from a suite where seven scenarios went red at once.
    pytest-bdd calls a step and discards what it returns, so a step written `async def`
    yields a coroutine nobody runs and the body never executes. Python prints a warning and
    pytest does not fail.

    The seven went red because each asserted that something had CHANGED. A scenario
    asserting an ABSENCE passes: it reads an untouched context and finds the empty list it
    wanted. So the failure is selective, and the half it hides is the negative controls.

    Only where the vocabulary says the runner discards the result. Every other runner waits
    for what a step returns, and reporting an async step there would ask an author to break
    working tests."""
    if not spec["steps_discard_the_result"]:
        return False
    return any(child.type in spec["async_markers"] for child in step.children)
