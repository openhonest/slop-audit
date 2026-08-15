# Run the Slop Audit L1 analyzer against a repo with nothing installed but Docker.
#
# The analyzer needs Python, uv, the tree-sitter grammars, and git. Mount the repo to
# audit at /repo (read-only is enough) and the panel comes back on stdout.
#
#   docker build -t slop-audit .
#   docker run --rm -v "$PWD:/repo:ro" slop-audit
#   docker run --rm -v "$PWD:/repo:ro" slop-audit --format json --no-exec
#
# The two runtime indicators (L1.19 coverage, L1.20 determinism) run the target repo's
# own test suite, and this image carries no language toolchains, so they report n/a with
# the reason. Pass --no-exec to skip them outright. Audit a repo in its own build image
# instead when you want those two measured.
#
# ARG PYTHON_VERSION parameterizes the interpreter; nothing else here is machine-specific.
ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

# git is not optional: L1.1 through L1.8 are git-log queries, and the analyzer reports
# them as n/a without it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt/slop-audit
COPY tools/l1_analyzer/ ./tools/l1_analyzer/
RUN uv sync --project tools/l1_analyzer --no-dev

# A mounted repo is owned by another uid; git refuses to read it unless it is trusted.
RUN git config --system --add safe.directory '*'

WORKDIR /repo
ENTRYPOINT ["uv", "run", "--project", "/opt/slop-audit/tools/l1_analyzer", "slop-audit-l1", "/repo"]
CMD ["--no-exec"]
