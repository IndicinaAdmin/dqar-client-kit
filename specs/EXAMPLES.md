# Usage Examples

## Example 1: Validate Manifest

```bash
client-kit validate-manifest manifest.json \
  --output manifest-report.json \
  --canonical-feed-inventory feed-inventory.json
```

Output:
- manifest-report.json (validation results)
- feed-inventory-canonical.json (for Phase 2)

## Example 2: Validate Data

```bash
client-kit validate-data \
  ./bulk-export/ \
  manifest.json \
  --output-dir ./conformance-results \
  --profile us-core-6.1.0 \
  --vsd-year MY2026
```

Output:
- conformance_report.json
- uc_table_properties.json
- uc_table_properties.sql
- member_detail_drilldown.csv

## Example 3: Complete UC1 Assessment (Recommended)

```bash
client-kit validate-all \
  ./bulk-export/ \
  manifest.json \
  --output-dir ./uc1-assessment \
  --profile us-core-6.1.0 \
  --vsd-year MY2026 \
  --verbose
```

Produces all artifacts in one command:
- uc1-assessment/
  ├── manifest-validation-report.json
  ├── conformance_report.json
  ├── uc_table_properties.json
  ├── uc_table_properties.sql
  ├── DQAR_FINDINGS.json
  ├── EXECUTIVE_SUMMARY.html
  ├── LOAD_INSTRUCTIONS.md
  └── logs/

## Example 4: Load UC Properties to Databricks (Python API)

```bash
python examples/load_properties_api.py \
  uc1-assessment/uc_table_properties.json \
  --workspace-url https://your-workspace.cloud.databricks.com \
  --token YOUR_PAT_TOKEN
```

## Example 5: Load UC Properties via SQL Editor

```bash
# Copy contents of uc_table_properties.sql
# Paste into Databricks SQL Editor
# Run all statements

cat uc1-assessment/uc_table_properties.sql | \
  databricks sql --file -
```

## Example 6: Load UC Properties via Terraform

```bash
terraform init
terraform apply \
  -var="uc_properties_file=uc1-assessment/uc_table_properties.json" \
  -var="databricks_host=https://your-workspace.cloud.databricks.com" \
  -var="databricks_token=YOUR_PAT_TOKEN"
```

## Sample Manifest

```json
{
  "version": "1.0",
  "plan": {
    "name": "Test Plan",
    "engagement_id": "UC1-20251014-test",
    "prepared_by": "Your Name",
    "prepared_date": "2025-10-14"
  },
  "feeds": [
    {
      "feed_id": "lab-vendor-x-daily",
      "source_system_id": "lab-vendor-x-prod",
      "source_type": "clinical_lab",
      "ecds_ssor": "Clinical Registry/HIE",
      "vendor_name": "LabCorp",
      "ingest_schedule": "daily 10:30 UTC",
      "ingest_method": "SFTP",
      "source_identification": {
        "method": "meta.source.reference",
        "meta_source_reference": "StructureDefinition/source-feed-lab-vendor-x-daily"
      }
    }
  ]
}
```

See MANIFEST_SCHEMA.md for complete field reference.
