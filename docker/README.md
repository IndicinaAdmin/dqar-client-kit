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
