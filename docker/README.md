# CDAR Client Kit — Docker Stack

This directory contains the Docker Compose stack for Rung 1/2 client-side
conformance testing and PHI redaction.

## Files

- `docker-compose.yml` — the standalone UC1 stack: web UI + CLI, FHIR
  conformance packages and the HAPI Validator CLI baked into the image at
  build time. Stage 2 redaction runs inside the same container — no
  separate service (see below).
- `.env.example` — copy to `.env` and edit per engagement.

`docker-compose.uc3.yml` and `config/anonymization.yaml`, previously listed
here, don't exist yet — see "Open items" in the rebuild plan. UC3 (the
`dqar-uc3` sister repo) is expected to build on this repo's image rather
than duplicating Stage 1; its compose delta is a follow-on task there, not
in this repo.

## Client delivery (no build required)

Sonian ships a pre-built image as an offline tarball (see `../RELEASE.md`).
No internet access or registry credentials are needed:

```bash
docker load < cdar-client-kit-X.Y.Z.tar.gz
cp .env.example .env   # set VERSION=X.Y.Z
docker compose up
open http://localhost:8000
```

`--tx-mode local` (the default; see `.env`) makes zero outbound network
calls at runtime — the FHIR R4 + US Core 6.1.0 + terminology package cache
is already baked into the image (see "Stage 1c terminology cache" below).

## Sonian development (rebuilding the image)

```bash
docker compose build   # no extra flags needed — cdar-contracts is vendored in vendor/
docker compose up
```

`cdar-contracts` ships as a pre-built wheel in `vendor/` (committed,
~15KB). When cdar-contracts bumps a version, rebuild it:

```bash
pip wheel ../cdar-contracts --no-deps -w vendor/
git add vendor/cdar_contracts-*.whl
```

## Stage 2 — PHI redaction (Path B only, client-initiated)

Stage 2 runs as a CLI invocation inside the same container — there is no
separate .NET/Microsoft Anonymization Tool service. Redaction uses
`stage2/redact.py`, vendored from `IndicinaAdmin/HealthClawGuardrails`
(`scripts/healthclaw_redact.py`): pure Python, SHA-256-hashes identifiers
with a per-engagement salt (kept client-side, never shipped with the
redacted extract), truncates names to initials, strips addresses below
state/country, coarsens birth dates to year, and masks telecom values. See
`stage2/anonymize_extract.py` for the full rule set.

Two ways to run it:

- **Web UI** — check "Also produce a de-identified extract for Sonian
  delivery (Path B)" before submitting an assessment; a download link
  appears alongside the report once Stage 1 + Stage 2 complete.
- **CLI** — `python stage1/orchestrate.py --ndjson-dir data/export --redact`
  (or run `stage2/anonymize_extract.py` directly against any NDJSON
  directory, independent of Stage 1).

Output: one `.ndjson.gz` per input file (same resource-type filenames Stage
1b/1c expect) plus a `stage2-{engagement}.json` summary — aggregate
redaction counts only, no PHI. Stage 1b re-runs automatically against the
redacted output to confirm redaction didn't corrupt structure.

## Stage 1c terminology cache (build-time step)

Stage 1c's `hapi-cli` backend resolves FHIR R4 + US Core 6.1.0 + terminology
dependencies (hl7.terminology.r4, us.nlm.vsac, us.cdc.phinvads — ~940MB
total) into a pinned, project-local cache (`.fhir-cache/`, gitignored)
rather than the developer's home directory, so every container/CI runner
uses identical package versions. The Dockerfile warms it once during the
image build:

```dockerfile
RUN python tools/provision_fhir_cache.py
```

Two terminology modes (`--tx-mode`, see
`stage1/stage1c_fhir_uscore_validator.py` docstring):

- `local` (default) — no outbound connection, skips terminology binding
  checks. Use for routine/CI runs and for the offline-tarball client
  delivery model.
- `live` — connects to tx.fhir.org for full terminology binding validation,
  ~20% slower, makes outbound calls to a third-party server. Use for the
  periodic/deeper assessment pass.
