# Troubleshooting Guide

Common issues and solutions.

---

## Installation Issues

### Issue: `ModuleNotFoundError: No module named 'dqar_client_kit'`

**Cause:** Package not installed or virtual environment not activated.

**Solution:**

```bash
# Install from PyPI
pip install cdar-client-kit

# Or from git
git clone https://github.com/Indicina/cdar-client-kit.git
cd cdar-client-kit
pip install -e .

# Verify installation
python -c "import dqar_client_kit; print(dqar_client_kit.__version__)"
```

### Issue: `command not found: client-kit`

**Cause:** Command-line entry point not installed.

**Solution:**

```bash
# Reinstall with entry point
pip install --upgrade --force-reinstall cdar-client-kit

# Or activate the virtual environment and use Python module
python -m dqar_client_kit.cli --help
```

---

## Manifest Validation Issues

### Issue: `Invalid engagement_id format`

**Error:**
```
Validation failed: Invalid engagement_id format
Expected: UC{1-3}-YYYYMMDD-{planname}
Got: UC1-2025-10-14-myplan
```

**Solution:**

The `engagement_id` must follow strict format:
- `UC1`, `UC2`, or `UC3` (use case)
- Hyphen
- `YYYYMMDD` (date, no hyphens inside)
- Hyphen
- Lowercase alphanumeric + hyphens (plan name)

**Correct format:**
```json
{
  "engagement_id": "UC1-20251014-myplan"
}
```

### Issue: `Missing required field: feeds`

**Solution:** Ensure manifest has at least one feed object:

```json
{
  "feeds": [
    {
      "feed_id": "lab-vendor-x",
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

### Issue: `Duplicate feed_id detected`

**Error:**
```
Validation failed: Duplicate feed_id: lab-vendor-x
```

**Solution:** Ensure each feed has a unique `feed_id`:

```json
{
  "feeds": [
    {"feed_id": "lab-vendor-x", ...},
    {"feed_id": "ehr-epic-daily", ...},  // Must be unique
    {"feed_id": "claims-837-daily", ...}  // Must be unique
  ]
}
```

### Issue: `Invalid source_identification method`

**Error:**
```
Validation failed: source_identification.method must be one of:
meta.source.reference, filename_pattern, external_batch_manifest
```

**Solution:** Pick one valid method:

```json
{
  "source_identification": {
    "method": "meta.source.reference",
    "meta_source_reference": "StructureDefinition/source-feed-lab"
  }
}
```

Or:

```json
{
  "source_identification": {
    "method": "filename_pattern",
    "filename_pattern": "LabCorp_*.ndjson"
  }
}
```

---

## Data Validation Issues

### Issue: `No valid FHIR resources found`

**Error:**
```
Validation failed: 0 resources parsed from observations.ndjson
```

**Causes:**
- File is empty
- File format is wrong (not NDJSON — newline-delimited JSON)
- Resources are malformed JSON

**Solution:**

Check file format:
```bash
# Should print one JSON object per line
head -1 observations.ndjson | jq .

# Should be valid JSON
cat observations.ndjson | jq -s length  # Count resources
```

If empty:
```bash
# Check file size
ls -lh observations.ndjson

# Verify it has content
wc -l observations.ndjson
```

### Issue: `Invalid FHIR JSON structure`

**Error:**
```
Validation failed: Resource obs-123 is not valid FHIR
Expected resourceType, got: unknown
```

**Solution:** Ensure resources have correct structure:

```json
{
  "resourceType": "Observation",
  "id": "obs-123",
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "2345-7"
      }
    ]
  }
}
```

### Issue: `Level 1 (Terminology) score is low`

**Error:**
```
✗ Level 1 (terminology): 45% pass
  - 55 resources have invalid LOINC codes
  - 10 resources missing code system
```

**Causes:**
- Code system URI wrong
- Code value not in NCQA value set
- Typos in codes

**Solution:**

Check specific failures:
```bash
client-kit validate-data \
  --manifest manifest.json \
  --data observations.ndjson \
  --conformance-level 1 \
  --verbose
```

Remediate:
1. Verify code systems match NCQA definitions
2. Use Termbox to validate codes exist
3. Check for typos (e.g., `2345-7` vs `2345-71`)

### Issue: `Level 2 (Profile) failures for required fields`

**Error:**
```
✗ Level 2 (profile): 87% pass
  - 13 resources missing required field: effectiveDateTime
```

**Cause:** Required fields per US Core 6.1.0 not present.

**Solution:**

For Observation.effectiveDateTime:
```json
{
  "resourceType": "Observation",
  "id": "obs-123",
  "effectiveDateTime": "2025-10-14T10:00:00Z",
  ...
}
```

Or use effectivePeriod:
```json
{
  "resourceType": "Observation",
  "id": "obs-123",
  "effectivePeriod": {
    "start": "2025-10-14T10:00:00Z"
  },
  ...
}
```

### Issue: `Level 3 (Context) failures`

**Error:**
```
✗ Level 3 (context): 70% pass
  - 15 resources outside measurement period
  - 5 resources missing encounter reference
```

**Causes:**
- Service date outside Jan 1 — Dec 31 of measurement year
- Missing Encounter.id reference
- Encounter type doesn't match measure requirement

**Solution:**

Verify dates are in measurement period (Jan 1 — Dec 31 of year):
```json
{
  "resourceType": "Observation",
  "effectiveDateTime": "2025-06-15T10:00:00Z"  // Must be 2025
}
```

Add encounter reference for relevant resources:
```json
{
  "resourceType": "Observation",
  "encounter": {
    "reference": "Encounter/enc-456"
  }
}
```

### Issue: `Level 4 (Plausibility) failures`

**Error:**
```
✗ Level 4 (plausibility): 92% pass
  - 8 resources have implausible values
    - HbA1c = 16% (exceeds physiological range)
    - BP Systolic = 350 mmHg
```

**Cause:** Values outside reasonable clinical ranges.

**Solution:**

For Observation.valueQuantity:
```json
{
  "resourceType": "Observation",
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "4548-4"  // HbA1c
      }
    ]
  },
  "valueQuantity": {
    "value": 7.5,      // 7.5% — within range
    "unit": "%",
    "system": "http://unitsofmeasure.org",
    "code": "%"
  }
}
```

Common ranges:
- HbA1c: 4.0–12.0%
- BP Systolic: 30–300 mmHg
- Weight: 10–500 lbs
- Temperature: 85–110 °F

---

## Output Issues

### Issue: `Permission denied writing to outputs/`

**Error:**
```
Failed to write uc_properties.json: Permission denied
```

**Solution:**

```bash
# Check directory permissions
ls -ld outputs/

# Create directory if missing
mkdir -p outputs

# Fix permissions
chmod 755 outputs
```

### Issue: `UC Properties file is empty`

**Error:**
```
uc_properties.json exists but contains no tables
```

**Cause:** No conformance metrics were calculated.

**Solution:**

Ensure validation ran with conformance metrics:
```bash
client-kit validate-all \
  --manifest manifest.json \
  --data *.ndjson \
  --conformance-level 4 \
  --output-format json
```

### Issue: `Summary HTML report is blank`

**Error:**
```
SUMMARY.html renders but shows no data
```

**Solution:**

Regenerate with debug output:
```bash
client-kit validate-all \
  --manifest manifest.json \
  --data *.ndjson \
  --generate-summary \
  --verbose
```

Check for errors in console output.

---

## Performance Issues

### Issue: `Validation is very slow`

**Causes:**
- Large NDJSON file (>1GB)
- Level 5 (anomaly detection) enabled (requires scikit-learn)
- Insufficient memory

**Solutions:**

Split the data:
```bash
# Validate a sample
head -100000 observations.ndjson > sample.ndjson
client-kit validate-data \
  --manifest manifest.json \
  --data sample.ndjson
```

Disable optional checks:
```bash
# Skip Level 5 anomaly detection
client-kit validate-data \
  --manifest manifest.json \
  --data observations.ndjson \
  --conformance-level 4  # Up to level 4 only
```

Increase memory:
```bash
# Run with more memory (Python)
PYTHONHASHSEED=0 python -m dqar_client_kit.cli validate-all \
  --manifest manifest.json \
  --data *.ndjson
```

---

## Getting Help

### Enable verbose logging

```bash
client-kit validate-manifest manifest.json --verbose
```

### Check version and dependencies

```bash
client-kit --version
pip show cdar-client-kit
pip list | grep -i dqar
```

### View raw validation results

```bash
client-kit validate-data \
  --manifest manifest.json \
  --data observations.ndjson \
  --output-format json | jq .
```

---

## Still Stuck?

Check:
1. **MANIFEST_SCHEMA.md** — Field reference
2. **CONFORMANCE_LEVELS.md** — Scoring details
3. **ARCHITECTURE.md** — System design

Or contact your data governance team.

