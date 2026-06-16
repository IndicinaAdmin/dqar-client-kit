# dqar-client-kit — standalone Rung 1/2 conformance testing kit.
#
# Builds a single-runtime (Python + JRE) image with the HAPI Validator CLI
# and the FHIR R4 + US Core 6.1.0 + terminology package cache baked in at
# build time, so a client's IT team can `docker load` the image and run an
# assessment with zero internet access at runtime (--tx-mode local, the
# default).
#
# dqar-contracts is vendored as a pre-built wheel in vendor/ (15KB,
# dqar_contracts-1.0.0-py3-none-any.whl) so the build needs no cross-repo
# auth, no BuildKit named contexts, and no internet access beyond PyPI for
# fastapi/uvicorn/jinja2. When dqar-contracts bumps a version, rebuild the
# wheel on the dev machine and commit it:
#
#   pip wheel ../dqar-contracts --no-deps -w vendor/
#   git add vendor/dqar_contracts-*.whl

# Pin to bookworm (Debian 12 LTS) — the current python:3.11-slim resolves to
# Trixie (Debian 13) which has dropped openjdk-17; bookworm retains it and
# has a better-reviewed CVE surface as a stable/LTS release.
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY vendor/ ./vendor/

# Install the vendored dqar-contracts wheel, then the kit itself (editable,
# so web/templates/ and stage1/templates/ resolve from /app at runtime).
RUN pip install --no-cache-dir vendor/dqar_contracts-*.whl

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
