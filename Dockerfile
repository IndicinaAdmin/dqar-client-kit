# dqar-client-kit — standalone Rung 1/2 conformance testing kit.
#
# Builds a single-runtime (Python + JRE) image with the HAPI Validator CLI
# and the FHIR R4 + US Core 6.1.0 + terminology package cache baked in at
# build time, so a client's IT team can `docker load` the image and run an
# assessment with zero internet access at runtime (--tx-mode local, the
# default).
#
# dqar-contracts is not published to a registry yet (see CLAUDE.md — "during
# development: pip install -e ../dqar-contracts"). This build pulls it in
# via a BuildKit named build context pointing at the sibling repo checkout,
# the same relationship local development already relies on:
#
#   DOCKER_BUILDKIT=1 docker build \
#     --build-context contracts=../dqar-contracts \
#     -t dqar-client-kit:0.1.0 .
#
# (scripts/release_image.sh wraps this so nobody has to remember the flag.)

# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./

# Sibling dqar-contracts checkout, supplied via --build-context (see header).
COPY --from=contracts / /tmp/dqar-contracts
RUN pip install --no-cache-dir /tmp/dqar-contracts \
    && rm -rf /tmp/dqar-contracts

COPY shared/  ./shared/
COPY stage1/  ./stage1/
COPY stage2/  ./stage2/
COPY web/     ./web/
COPY tools/   ./tools/

# Editable install — same as local dev (`pip install -e '.[web]'`, see
# web/app.py and stage1/report.py docstrings). A regular `pip install .`
# would copy the package into site-packages without web/templates/ or
# stage1/templates/ (neither is declared as package data), breaking the
# web UI and the HTML report at runtime.
RUN pip install --no-cache-dir -e .[web]

ENV FHIR_VALIDATOR_JAR=/app/tools/validator_cli.jar \
    JAVA_BIN=java \
    FHIR_PACKAGE_CACHE_HOME=/app/.fhir-cache \
    TX_MODE=local

# Bake the ~940MB FHIR R4 + US Core 6.1.0 + terminology package cache into
# the image layer — the "FHIR conformance packages" requirement. Every
# container starts ready; --tx-mode local makes zero outbound calls.
RUN python tools/provision_fhir_cache.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=3)" || exit 1

# Default: web UI. Override for the CLI path, e.g.:
#   docker run -v $(pwd)/data:/app/data dqar-client-kit \
#     python stage1/orchestrate.py --ndjson-dir data/export --skip-1a
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
