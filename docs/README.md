# cdar-client-kit Documentation

Reference documentation for cdar-client-kit (Phase 1–5).

---

## Files Guide

### Getting Started

**[QUICKSTART.md](QUICKSTART.md)**
- Install cdar-client-kit
- Validate manifest
- Validate FHIR data
- Generate UC properties
- Common workflows (5 minutes)

**[ARCHITECTURE.md](ARCHITECTURE.md)**
- System design and components
- Data flow
- Integration points
- Maturity rungs vs. tier alignment

### Reference Documentation

**[MANIFEST_SCHEMA.md](MANIFEST_SCHEMA.md)**
Complete field reference for `manifest.json`:
- Top-level object
- Plan object
- Feed object
- Source Type and ECDS SSoR enums
- Source Identification methods
- Validation rules
- Complete examples

**[CONFORMANCE_LEVELS.md](CONFORMANCE_LEVELS.md)**
Five-level semantic validation and PIQI quality dimensions:
- Level 1: Terminology conformance
- Level 2: FHIR profile conformance
- Level 3: Clinical context conformance
- Level 4: Clinical plausibility
- Level 5: Stability (population-level)
- PIQI dimensions (Usability, Plausibility, Comparability, Stability)
- Aggregation rules
- Interpretation guide

**[UC_PROPERTIES.md](UC_PROPERTIES.md)**
Databricks Unity Catalog properties:
- JSON format output
- SQL DDL format output
- Loading with Databricks SDK
- Loading with Terraform
- Querying properties
- Version control

**[DBT_INTEGRATION.md](DBT_INTEGRATION.md)**
dbt manifest parsing and lineage detection:
- dbt meta tags for lineage
- Lineage detection validator (3 checks)
- dbt-openlineage configuration
- CDARIngestFacet structure
- Diagnosing lineage gaps
- Remediation checklist

### Support

**[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**
Common issues and solutions:
- Installation issues
- Manifest validation issues
- Data validation issues
- Output issues
- Performance issues
- Verbose logging and help

---

## Quick Navigation

| I want to... | Go to... |
|---|---|
| Get started in 5 minutes | QUICKSTART.md |
| Understand the system | ARCHITECTURE.md |
| Write a manifest | MANIFEST_SCHEMA.md |
| Understand conformance scoring | CONFORMANCE_LEVELS.md |
| Load properties to Databricks | UC_PROPERTIES.md |
| Integrate with dbt | DBT_INTEGRATION.md |
| Troubleshoot an issue | TROUBLESHOOTING.md |

---

## Usage Examples

### Validate manifest

```bash
client-kit validate-manifest manifest.json
```

See **MANIFEST_SCHEMA.md** for manifest structure.

### Run conformance checks

```bash
client-kit validate-data \
  --manifest manifest.json \
  --data observations.ndjson \
  --conformance-level 2
```

See **CONFORMANCE_LEVELS.md** for level details.

### Generate UC properties

```bash
client-kit validate-all \
  --manifest manifest.json \
  --data *.ndjson \
  --output-format json,sql
```

See **UC_PROPERTIES.md** to load properties.

### Run full pipeline

```bash
client-kit validate-all \
  --manifest manifest.json \
  --data *.ndjson \
  --conformance-level 4 \
  --output-format json,sql \
  --generate-summary
```

---

## Document Versions

- MANIFEST_SCHEMA.md: v1.0 (matches `schema_version: "1.0"`)
- CONFORMANCE_LEVELS.md: v1.0 (5-level model)
- UC_PROPERTIES.md: v1.0 (dqar.* properties)
- DBT_INTEGRATION.md: v1.0 (dbt-openlineage + CDARIngestFacet)
- QUICKSTART.md: v1.0
- TROUBLESHOOTING.md: v1.0
- ARCHITECTURE.md: v1.0

---

## Dependencies

All docs assume cdar-client-kit v1.0.0+.

Core dependencies:
- Python 3.9+
- click ≥8.1.0
- pydantic ≥2.0
- ndjson ≥0.3.1
- pandas ≥2.0

Optional:
- scikit-learn (for Level 5 anomaly detection)
- databricks-sdk (for UC property loading)

---

## Support Matrix

| Component | Documented | Status |
|---|---|---|
| Manifest validation | Yes | GA |
| Conformance Levels 1–4 | Yes | GA |
| Conformance Level 5 | Yes | Optional |
| UC properties JSON/SQL | Yes | GA |
| dbt integration | Yes | GA |
| OpenLineage emission | Yes | Roadmap |

---

## Contributing

If you find an issue with documentation:
1. Open an issue in the repository
2. Include which document and section
3. Provide the error or confusion

