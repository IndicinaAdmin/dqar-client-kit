# Phase 1: CLI Architecture & Manifest Validation (Weeks 1–2)

## Objectives

- [ ] Refactor CLI from separate tools to unified entry point with subcommands
- [ ] Build Pydantic models for Manifest validation
- [ ] Implement manifest schema validation logic
- [ ] Generate canonical feed inventory (used by Phase 2)
- [ ] Produce manifest validation report (JSON)

## Deliverables

1. **File structure refactored**
2. **CLI entry point** (`client_kit/cli.py`) with Click routing
3. **Manifest models** (`client_kit/models/manifest.py`)
4. **Manifest validator** (`client_kit/validators/manifest.py`)
5. **Manifest validation command** (`client_kit/commands/validate_manifest.py`)
6. **Unit tests** (`tests/unit/test_manifest_*.py`)
7. **Documentation** (`docs/MANIFEST_SCHEMA.md`)

## Key Implementation

See cli.py, manifest.py, and validator implementations in the complete spec file.

For full code, see: cdar-client-kit-phases-02-to-05.md
