# DQAR Client Kit — Docker Stack

This directory contains the Docker Compose stack for Rung 1/2 client-side
conformance testing and pseudonymization.

## Files

- `docker-compose.yml` — UC1 standard stack (conformance + pseudonymization)
- `docker-compose.uc3.yml` — UC3 delta (version detector + dual-pass conformance)
- `config/anonymization.yaml` — Microsoft FHIR Anonymization rules

## Usage

```bash
cp .env.example .env
# Edit .env with engagement-specific values
docker compose up --abort-on-container-exit
```

See `dqar-07-uc1-client-docker-stack.md` in the project KB for full specification.

## Stage 1c terminology cache (build-time step)

Stage 1c's `hapi-cli` backend resolves FHIR R4 + US Core 6.1.0 + terminology
dependencies (hl7.terminology.r4, us.nlm.vsac, us.cdc.phinvads — ~940MB total)
into a pinned, project-local cache (`.fhir-cache/`, gitignored) rather than the
developer's home directory, so every container/CI runner uses identical package
versions. Warm it once during the image build, don't run it per-test:

```dockerfile
RUN python tools/provision_fhir_cache.py
```

Or as a CI cache step keyed on the validator jar version, restoring `.fhir-cache/`
before the test job runs. Two terminology modes (`--tx-mode`, see
`stage1/stage1c_fhir_uscore_validator.py` docstring):

- `local` (default) — no outbound connection, skips terminology binding checks.
  Use for routine/CI runs.
- `live` — connects to tx.fhir.org for full terminology binding validation,
  ~20% slower, makes outbound calls to a third-party server. Use for the
  periodic/deeper assessment pass.
