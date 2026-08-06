"""Thread-safety surface meter, Python conformance.

Python has NO compiler thread-safety guarantee to override (unlike Rust's
Send/Sync). Under the GIL, shared mutable state was de-facto serialized; under
free-threaded CPython (cp314t / gil_used=false) it is genuinely concurrent. So the
Python surface is not a hand-override, it is shared mutable state that free-threading
makes racy. The signals here are deliberately conservative to stay honest:

  REVIEW   mutable_default_arg           - def f(x=[]) : shared across calls, always decidable
  EXPOSED  unguarded_shared_state        - module-level mutable container in a file that uses
                                           threads/processes, with NO lock in the file
  REVIEW   possibly_unguarded_shared_state - same, but a lock IS present in the file (cannot
                                           prove it guards this state; verify)

A module-level mutable container with no concurrency primitive in the file is NOT
surfaced: free-threading is not in play, so it is not thread surface. As always, a
finding is "verify this", never "a race exists".
"""

from l1_analyzer import thread_surface


def _scan(tmp_path, src):
    (tmp_path / "case.py").write_text(src)
    return thread_surface.scan(tmp_path, "python")


def _find(result, kind, symbol):
    return next(
        (f for f in result.get("findings", []) if f["kind"] == kind and f["symbol"] == symbol),
        None,
    )


def test_mutable_default_arg_is_review(tmp_path):
    result = _scan(tmp_path, "def f(items=[]):\n    return items\n")
    f = _find(result, "mutable_default_arg", "items")
    assert f is not None, "mutable default arg not surfaced"
    assert f["severity"] == "review"
    result2 = _scan(tmp_path, "def g(cfg: dict = {}):\n    return cfg\n")
    assert _find(result2, "mutable_default_arg", "cfg") is not None


def test_immutable_default_is_clean(tmp_path):
    result = _scan(tmp_path, "def f(n=3, s='x', t=()):\n    return n\n")
    assert result["findings"] == []
    assert result["verdict"] == "clean"


def test_shared_container_with_threads_no_lock_is_exposed(tmp_path):
    result = _scan(
        tmp_path,
        "import threading\n"
        "CACHE = {}\n"
        "def worker(k, v):\n"
        "    CACHE[k] = v\n"
        "threading.Thread(target=worker, args=(1, 2)).start()\n",
    )
    f = _find(result, "unguarded_shared_state", "CACHE")
    assert f is not None, "shared module container under threads not surfaced"
    assert f["severity"] == "exposed"
    assert result["verdict"] == "exposed"


def test_shared_container_with_lock_present_is_review(tmp_path):
    # A lock exists in the file, so we downgrade: cannot prove it guards CACHE, but
    # it is not the no-guard-in-sight case. Honest middle tier.
    result = _scan(
        tmp_path,
        "import threading\n"
        "CACHE = {}\n"
        "_lock = threading.Lock()\n"
        "def worker(k, v):\n"
        "    with _lock:\n"
        "        CACHE[k] = v\n",
    )
    f = _find(result, "possibly_unguarded_shared_state", "CACHE")
    assert f is not None, "shared container with a lock present not surfaced as review"
    assert f["severity"] == "review"
    assert result["verdict"] == "review"


def test_shared_container_without_concurrency_is_not_surface(tmp_path):
    # A module-level dict with no threads/processes in the file is not thread surface.
    result = _scan(
        tmp_path,
        "REGISTRY = {}\n"
        "def register(name, fn):\n"
        "    REGISTRY[name] = fn\n",
    )
    assert result["findings"] == []
    assert result["verdict"] == "clean"
