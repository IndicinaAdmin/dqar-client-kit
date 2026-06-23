# Releasing cdar-client-kit

Distribution is an offline tarball — no registry, no client-side
credentials. This matches the Rung 1 pitch: "no procurement, no vendor
contract" — the client's IT team loads an image, they don't pull one.

## Building a release (Sonian)

```bash
scripts/release_image.sh 0.1.0
```

`cdar-contracts` is vendored as a pre-built wheel in `vendor/` — no
sibling repo or cross-repo auth needed. If you need to update the wheel:

```bash
pip wheel ../cdar-contracts --no-deps -w vendor/
git add vendor/cdar_contracts-*.whl
```

This builds the image, saves + gzips it, and writes a checksum:

```
dist/cdar-client-kit-0.1.0.tar.gz
dist/cdar-client-kit-0.1.0.tar.gz.sha256
```

Before sending the tarball to a client, verify it actually works with no
network access — this is the real client-delivery scenario and the whole
point of baking the FHIR package cache into the image:

```bash
# on a machine/VM with networking disabled
docker load < dist/cdar-client-kit-0.1.0.tar.gz
cd docker && cp .env.example .env   # VERSION=0.1.0
docker compose up
# upload a test NDJSON extract via http://localhost:8000 and confirm
# Stage 1c completes with TX_MODE=local and zero outbound connections
```

## Client quick-start

1. Sonian sends `cdar-client-kit-X.Y.Z.tar.gz` + `.sha256` (email, SFTP, or
   physical media per the engagement's data-handling agreement).
2. Verify the checksum: `shasum -a 256 -c cdar-client-kit-X.Y.Z.tar.gz.sha256`
3. `docker load < cdar-client-kit-X.Y.Z.tar.gz`
4. `cd docker && cp .env.example .env` — set `VERSION=X.Y.Z`
5. `docker compose up`
6. Open `http://localhost:8000`, upload the Bulk FHIR NDJSON extract, run
   the assessment. Nothing leaves this machine. Optionally check "Also
   produce a de-identified extract for Sonian delivery" if proceeding to
   Path B.

## Versioning

The image tag tracks `pyproject.toml`'s `[project].version`. Bump it
whenever the conformance ruleset, Stage 2 redaction rules, or baked FHIR
package set changes, so a support conversation can immediately identify
which ruleset a client is running against `pyproject.toml`'s pinned
`cdar-contracts` range.
