# Quick Start Guide

Get up and running with dqar-client-kit in 15 minutes.

---

## Prerequisites

- Python 3.9+
- pip
- A manifest.json file ready to validate

---

## 1. Install dqar-client-kit

```bash
pip install dqar-client-kit
```

Or from git:

```bash
git clone https://github.com/Indicina/dqar-client-kit.git
cd dqar-client-kit
pip install -e .
```

---

## 2. Prepare Your Manifest

Create a file called `manifest.json`:

```json
{
  "schema_version": "1.0",
  "version": "1.0",
  "plan": {
    "name": "My Health Plan",
    "engagement_id": "UC1-20251014-myplan",
    "prepared_by": "Data Team",
    "prepared_date": "2025-10-14"
  },
  "feeds": [
    {
      "feed_id": "lab-feed",
      "source_system_id": "labcorp-prod",
      "source_type": "clinical_lab",
      "ecds_ssor": "Clinical Registry/HIE",
      "vendor_name": "LabCorp",
      "ingest_schedule": "daily",
      "ingest_method": "SFTP",
      "source_identification": {
        "method": "meta.source.reference",
        "meta_source_reference": "StructureDefinition/source-feed-lab"
      }
    }
  ]
}
```

See **MANIFEST_SCHEMA.md** for full field reference.

---

## 3. Validate Your Manifest

```bash
client-kit validate-manifest manifest.json
```

Output:
```
✓ PASS: Manifest validation successful
  - Schema version: 1.0
  - Plan name: My Health Plan
  - Feeds: 1 detected
  - Uniqueness checks: PASS
```

If errors occur:
```
✗ FAILED: Manifest validation
  - Missing required field: feeds
  - Invalid engagement_id format
```

See **TROUBLESHOOTING.md** for common issues.

---

## 4. Validate Your FHIR Data

Prepare a test NDJSON file with FHIR resources:

```
observations.ndjson
```

Each line is a FHIR resource:

```json
{"resourceType":"Observation","id":"obs-123","code":{"coding":[{"system":"http://loinc.org","code":"2345-7"}]},"value":{"Quantity":{"value":95}},"effectiveDateTime":"2025-10-14T10:00:00Z"}
{"resourceType":"Observation","id":"obs-124","code":{"coding":[{"system":"http://loinc.org","code":"2345-7"}]},"value":{"Quantity":{"value":102}},"effectiveDateTime":"2025-10-14T10:30:00Z"}
```

Validate:

```bash
client-kit validate-data \
  --manifest manifest.json \
  --data observations.ndjson \
  --conformance-level 2
```

Output:
```
✓ Conformance validation complete
  - Resource count: 2
  - Level 1 (terminology): 100% pass
  - Level 2 (profile): 95% pass
    - 1 resource missing required field
  - Level 3 (context): 100% pass
  - Level 4 (plausibility): 100% pass

Recommendations:
  - 1 Observation missing effectiveDateTime (required for US Core)
```

---

## 5. Generate UC Properties (Optional)

Once your data is validated, generate Databricks Unity Catalog properties:

```bash
client-kit validate-all \
  --manifest manifest.json \
  --data observations.ndjson \
  --output-format json,sql
```

Outputs:
```
outputs/UC1-20251014-myplan_uc_properties.json
outputs/UC1-20251014-myplan_uc_properties.sql
```

Load to Databricks:

```bash
databricks sql < outputs/UC1-20251014-myplan_uc_properties.sql
```

---

## 6. View the Executive Summary

After validation, view a summary report:

```bash
client-kit validate-all \
  --manifest manifest.json \
  --data observations.ndjson \
  --generate-summary
```

Opens:
```
outputs/UC1-20251014-myplan_SUMMARY.html
```

The HTML report shows:
- Plan metadata
- Conformance scores by level and resource type
- PIQI dimensions
- Tier 1–3 findings
- Remediation recommendations

---

## Common Workflows

### Scenario 1: Quick manifest check

```bash
client-kit validate-manifest manifest.json
```

### Scenario 2: End-to-end validation (no UC properties)

```bash
client-kit validate-all \
  --manifest manifest.json \
  --data *.ndjson
```

### Scenario 3: Conformance reporting only

```bash
client-kit validate-data \
  --manifest manifest.json \
  --data *.ndjson \
  --conformance-level 4 \
  --output-format json
```

### Scenario 4: Full assessment with Databricks integration

```bash
client-kit validate-all \
  --manifest manifest.json \
  --data *.ndjson \
  --conformance-level 4 \
  --output-format json,sql \
  --generate-summary \
  --include-piqi
```

---

## Next Steps

- **Phase 2 deep dive:** See `CONFORMANCE_LEVELS.md` for scoring details
- **Phase 3 integration:** See `UC_PROPERTIES.md` for Databricks loading
- **Phase 4 lineage:** See `DBT_INTEGRATION.md` for dbt integration
- **Architecture:** See `ARCHITECTURE.md` for system design
- **Troubleshooting:** See `TROUBLESHOOTING.md` for common issues

---

## Getting Help

```bash
client-kit --help
client-kit validate-manifest --help
client-kit validate-data --help
client-kit validate-all --help
```

Or see **TROUBLESHOOTING.md** for detailed diagnostics.

