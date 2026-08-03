"""honest-page reference server (honest-page-architecture.md §10).

Three things make this the reference rather than a demo:

1. **The route map is data** (§9, §10.2). ROUTES pairs one (method, path) with one chain, by name, so a
   tool reads the binding by parsing — honest-check follows a template's hx-get to a path, the path to
   its chain, and checks the chain's first link against exactly the fields the templates send.
2. **State arrives as _state** (§10.3). domx collects the manifest the page declares and submits it;
   intake classifies route params, query params, and _state into one manifest on the request.
3. **Full pages extend base.html; fragments do not** (§10.2). The index renders the page; the search
   route renders a fragment HTMX swaps in.

Decisions are pure functions over data. Rendering goes through the template boundary, and the one
handler that constructs raw HTTP responses — the alert stream — is a declared link that says what it
emits, so its output is checkable rather than assumed.
"""

import json
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request
from fastapi import responses
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from honest_type import link, vocabulary

_HERE = Path(__file__).parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
templates = Jinja2Templates(directory=_HERE / "templates")

# How often the alert stream emits a keep-alive comment. The spec requires at most 30 seconds, so a
# proxy or load balancer does not time the connection out (§4.3).
KEEP_ALIVE_SECONDS = 25

# What the alert stream is allowed to put on the wire (§4.1, §4.4). Declared, so the output shape is
# checkable: an unauthenticated request is an empty 204, an authenticated one an event stream.
ALERT_STREAM_EMITS = vocabulary({
    "status": {"200", "204"},
    "content_type": {"text/event-stream"},
    "body": {"keep-alive"},
})


@link()
def search_chain(manifest):
    """The chain the (GET, /search) route runs. Pure: the classified manifest in, the rows out. The
    reference keeps the body trivial — what matters is that the route map names it, so honest-check can
    check this chain's first link against the fields the templates targeting /search send."""
    query = manifest.get("search", "")
    return [row for row in ("alpha", "beta", "gamma") if query in row]


# The route map (§9): a declared mapping a parser can resolve without running the app. One method and
# path per entry, one chain per entry.
ROUTES = {
    ("GET", "/search"): search_chain,
}


@link()
def extract_tokens(path_params, query_params, state):
    """The three token sources one request carries, merged into one manifest input (§10.3): path
    parameters, query parameters, and the `_state` domx collected from the DOM.

    Precedence is declared, not incidental: `_state` wins over query parameters, which win over path
    parameters. That order follows the specificity of user intent — state the user established in the
    page is more specific about what they meant than anything encoded in the URL. Pure over the three
    already-extracted mappings; reading them off the request is the middleware's job below."""
    return {**path_params, **query_params, **state}


@app.middleware("http")
@link(boundary=True)
async def intake(request: Request, call_next):
    """The intake boundary (§10.3): classify what the request carries once, and hand the interior one
    manifest. Registered before any handler, so every route sees `request.state.manifest` already
    resolved and no handler re-reads the request for its inputs."""
    body = await request.body()
    state = json.loads(dict(parse_qsl(body.decode("utf-8"))).get("_state", "{}")) if body else {}
    request.state.manifest = extract_tokens(dict(request.path_params), dict(request.query_params), state)
    response = await call_next(request)
    request_id = request.headers.get("X-Request-ID")
    if request_id is not None:
        response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", response_class=HTMLResponse)
@link(boundary=True)
async def index(request: Request):
    """A full page: renders page.html, which extends base.html, and passes the standard context
    variables (§6, §10.2). Every one of them is optional — the base template defaults each."""
    return templates.TemplateResponse("page.html", {
        "request": request,
        "app_name": "Honest App",
        "page_title": "Home",
    })


@app.get("/search", response_class=HTMLResponse)
@link(boundary=True)
async def search(request: Request):
    """A fragment route: it renders search_results.html, which does not extend base.html (§10.2). The
    intake middleware places _state and the query params on the request as one classified manifest;
    this handler hands that manifest to the chain the route map names."""
    manifest = getattr(request.state, "manifest", {"search": request.query_params.get("q", "")})
    return templates.TemplateResponse("search_results.html", {
        "request": request,
        "rows": ROUTES[("GET", "/search")](manifest),
    })


@link(boundary=True, emits=ALERT_STREAM_EMITS)
async def alerts_stream(request: Request):
    """The honest-alerts SSE stream the three notification surfaces connect to (§4). Without a valid
    session it is 204 No Content — the SSE extension reads that as an empty stream and shows no error
    (§4.4). Otherwise it holds the connection open, emitting a keep-alive comment inside the timeout
    window (§4.3). A boundary link: the only place this module puts bytes on the wire, and it declares
    what it emits."""
    if request.cookies.get("honest_session") is None:
        return responses.Response(status_code=204)

    async def keep_alive():
        import asyncio

        while True:
            yield ": keep-alive\n\n"
            await asyncio.sleep(KEEP_ALIVE_SECONDS)

    return responses.StreamingResponse(keep_alive(), media_type="text/event-stream")


app.get("/api/alerts/stream")(alerts_stream)
