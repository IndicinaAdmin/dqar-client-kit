# Manifest Schema Reference (v1.0)

Complete field reference for `manifest.json` used by cdar-client-kit.

## Top-Level Object

```json
{
  "schema_version": "1.0",
  "version": "1.0",
  "plan": { ... },
  "feeds": [ ... ],
  "exclusions": [ ... ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| schema_version | string | Yes | Schema version (current: "1.0") |
| version | string | Yes | Manifest version (e.g., "1.0", "2.1") |
| plan | object | Yes | Plan metadata object |
| feeds | array | Yes | Array of Feed objects (min 1) |
| exclusions | array | No | Array of excluded sources |

---

## Plan Object

```json
{
  "name": "Acme Health Plan",
  "engagement_id": "UC1-20251014-acme",
  "prepared_by": "John Smith",
  "prepared_date": "2025-10-14"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| name | string | Yes | Plan name (e.g., "Acme Health Plan") |
| engagement_id | string | Yes | Unique engagement ID (format: UC{1-3}-YYYYMMDD-{planname}) |
| prepared_by | string | Yes | Person/team name who prepared this manifest |
| prepared_date | string | Yes | ISO 8601 date (YYYY-MM-DD) |

**Example engagement IDs:**
- `UC1-20251014-acme` (UC1 assessment, Oct 14 2025, Acme plan)
- `UC2-20251015-bluecross` (UC2 monitoring, Oct 15 2025, Blue Cross plan)
- `UC3-20251020-cigna` (UC3 P2P assessment, Oct 20 2025, Cigna plan)

---

## Feed Object

```json
{
  "feed_id": "lab-vendor-x-daily-1030utc",
  "source_system_id": "lab-vendor-x-prod",
  "source_type": "clinical_lab",
  "ecds_ssor": "Clinical Registry/HIE",
  "vendor_name": "LabCorp Analytics",
  "vendor_contact": "data-ops@labcorp.com",
  "ingest_schedule": "daily 10:30 UTC",
  "ingest_method": "SFTP",
  "source_identification": { ... },
  "upstream_transformation_rule": "Interbox rule v2.1",
  "upstream_rule_version": "2.1",
  "upstream_rule_last_reviewed": "2025-08-15",
  "data_elements": ["LOINC codes", "lab values"],
  "expected_record_volume_per_run": 50000,
  "estimated_latency_hours": 2,
  "notes": "Daily feed from LabCorp via SFTP"
}
```

### Required Fields

| Field | Type | Pattern | Description |
|---|---|---|---|
| feed_id | string | `^[a-z0-9_-]+$` | Unique feed ID (snake_case, no spaces) |
| source_system_id | string | `^[a-z0-9_-]+$` | Canonical system ID (must be unique across manifest) |
| source_type | enum | See table below | Type of source system |
| ecds_ssor | enum | See table below | ECDS Source System of Record category |
| vendor_name | string | | Vendor or system name |
| ingest_schedule | string | | Schedule description (e.g., "daily 10:30 UTC", "weekly Monday") |
| ingest_method | string | | How data arrives (SFTP, FHIR Bulk $export, S3, API, etc.) |
| source_identification | object | | How to match resources to feed (see below) |

### Optional Fields

| Field | Type | Description |
|---|---|---|
| vendor_contact | string | Email or team contact for vendor |
| upstream_transformation_rule | string | Interbox rule name (if applicable) |
| upstream_rule_version | string | Version of transformation rule |
| upstream_rule_last_reviewed | string | ISO 8601 date of last review |
| data_elements | array | List of data element descriptions |
| expected_record_volume_per_run | integer | Typical records per ingest |
| estimated_latency_hours | integer | Hours from event to availability |
| notes | string | Free-form notes |

---

## Source Type Enum

**Tier A (Structurally Detectable):**
Source type can be inferred from FHIR resource structure.

- `clinical_ehr` — Electronic Health Record system
- `clinical_phr` — Personal Health Record (patient portal)
- `administrative_claims` — Claims/billing data
- `administrative_encounter` — Encounter records
- `pharmacy_pbm` — Pharmacy/PBM data
- `clinical_lab` — Laboratory results (FHIR Observation, LOINC codes)
- `payer_exchange` — Data from another payer
- `clinical_immunization_registry` — Immunization registry

**Tier B (Manifest/meta.source Declared):**
Source type cannot be inferred from FHIR structure alone; must be declared.

- `pharmacy_specialty` — Specialty pharmacy
- `clinical_hie` — Health Information Exchange
- `clinical_registry` — Clinical registry or data repository
- `case_management` — Care management system
- `disease_management` — Disease management program

---

## ECDS SSoR Enum

Maps `source_type` to NCQA ECDS Source System of Record categories.

| source_type | → | ecds_ssor |
|---|---|---|
| clinical_ehr | → | EHR/PHR |
| clinical_phr | → | EHR/PHR |
| clinical_hie | → | Clinical Registry/HIE |
| clinical_registry | → | Clinical Registry/HIE |
| clinical_immunization_registry | → | Clinical Registry/HIE |
| administrative_claims | → | Administrative |
| administrative_encounter | → | Administrative |
| pharmacy_pbm | → | Administrative |
| pharmacy_specialty | → | Clinical Registry/HIE |
| case_management | → | Case/Disease Management |
| disease_management | → | Case/Disease Management |
| payer_exchange | → | (varies) |

---

## Source Identification Object

Specifies how to match FHIR resources to this feed. **Exactly one method must be specified.**

### Method 1: meta.source.reference

```json
{
  "method": "meta.source.reference",
  "meta_source_reference": "StructureDefinition/source-feed-lab-vendor-x-daily"
}
```

**Matching logic:**
```
resource.meta.source.reference == "StructureDefinition/source-feed-lab-vendor-x-daily"
```

Use when: Resources explicitly declare their source via `meta.source.reference`.

### Method 2: filename_pattern

```json
{
  "method": "filename_pattern",
  "filename_pattern": "LabCorp_*.ndjson"
}
```

**Matching logic:**
```
filename matches glob pattern (e.g., "LabCorp_20251014.ndjson" matches "LabCorp_*.ndjson")
```

Use when: Resource source can be inferred from the NDJSON file it came from.

### Method 3: external_batch_manifest

```json
{
  "method": "external_batch_manifest",
  "batch_manifest_uri": "s3://plan-bucket/batch-20251014/manifest.json"
}
```

**Matching logic:**
```
resource.id in external_manifest['resource_ids']
```

Use when: An external file lists which resources belong to this feed.

---

## Complete Examples

### Minimal Valid Manifest

```json
{
  "schema_version": "1.0",
  "version": "1.0",
  "plan": {
    "name": "Test Plan",
    "engagement_id": "UC1-20251014-test",
    "prepared_by": "QA User",
    "prepared_date": "2025-10-14"
  },
  "feeds": [
    {
      "feed_id": "lab-vendor-x",
      "source_system_id": "lab-vendor-x-prod",
      "source_type": "clinical_lab",
      "ecds_ssor": "Clinical Registry/HIE",
      "vendor_name": "LabCorp",
      "ingest_schedule": "daily",
      "ingest_method": "SFTP",
      "source_identification": {
        "method": "meta.source.reference",
        "meta_source_reference": "StructureDefinition/source-feed-lab-vendor-x"
      }
    }
  ]
}
```

### Full Featured Manifest

```json
{
  "schema_version": "1.0",
  "version": "2.1",
  "plan": {
    "name": "Acme Health Plan",
    "engagement_id": "UC1-20251014-acme",
    "prepared_by": "Data Governance Team",
    "prepared_date": "2025-10-14"
  },
  "feeds": [
    {
      "feed_id": "lab-vendor-x-daily-1030utc",
      "source_system_id": "lab-vendor-x-prod",
      "source_type": "clinical_lab",
      "ecds_ssor": "Clinical Registry/HIE",
      "vendor_name": "LabCorp Analytics",
      "vendor_contact": "data-ops@labcorp.com",
      "ingest_schedule": "daily 10:30 UTC",
      "ingest_method": "SFTP",
      "source_identification": {
        "method": "meta.source.reference",
        "meta_source_reference": "StructureDefinition/source-feed-lab-vendor-x-daily"
      },
      "upstream_transformation_rule": "Interbox v2.1",
      "upstream_rule_version": "2.1",
      "upstream_rule_last_reviewed": "2025-08-15",
      "data_elements": ["LOINC lab codes", "result values", "reference ranges"],
      "expected_record_volume_per_run": 50000,
      "estimated_latency_hours": 2
    },
    {
      "feed_id": "ehr-epic-daily",
      "source_system_id": "epic-prod-org-447",
      "source_type": "clinical_ehr",
      "ecds_ssor": "EHR/PHR",
      "vendor_name": "Epic EHR",
      "ingest_schedule": "daily midnight UTC",
      "ingest_method": "FHIR Bulk $export",
      "source_identification": {
        "method": "filename_pattern",
        "filename_pattern": "Epic_export_*.ndjson"
      },
      "expected_record_volume_per_run": 500000
    }
  ],
  "exclusions": [
    {
      "vendor_name": "Quest Diagnostics",
      "reason": "No FHIR integration; manual chart review only (MRR)"
    }
  ]
}
```

---

## Validation Rules

### Schema Validation

- All required fields present
- Field types match declared types
- `feed_id` matches pattern `^[a-z0-9_-]+$`
- `source_system_id` matches pattern `^[a-z0-9_-]+$`
- `engagement_id` matches pattern `^UC[1-3]-[0-9]{8}-[a-z0-9_-]+$`
- `prepared_date` is valid ISO 8601

### Uniqueness Validation

- `feed_id` must be unique across all feeds
- `source_system_id` must be unique across all feeds

### Business Rules

- `source_identification.method` must be one of: `meta.source.reference`, `filename_pattern`, `external_batch_manifest`
- `source_identification` must have exactly one value field populated (the one matching the method)
- `source_type` must be valid enum value
- `ecds_ssor` must be valid enum value
- If `source_type` is Tier B, `ecds_ssor` should match the mapping table above

### Run Validation

```bash
client-kit validate-manifest manifest.json
```

Returns:
- PASS: All validations successful
- FAILED: List of validation errors
