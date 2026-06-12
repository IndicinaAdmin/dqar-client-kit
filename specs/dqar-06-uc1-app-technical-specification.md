# UC1 Assessment App — Technical Specification
**Digital Measure Readiness Assessment Application**
*Version: June 2026 | For Claude Code + Health Samurai Implementation*

---

## Overview

This document specifies the technical architecture for the UC1 Digital Measure Readiness Assessment application. This application is the technical implementation of one tenet of the broader Digital Quality Audit Readiness (DQAR) — specifically Domain 6 (ECDS and dQM readiness) with elements of Domain 2 (value set conformance) and Domain 3 (data lineage tracing).

**Framework linkage:** This app implements UC1 of the DQAR use case index (`dqar-03-use-case-index.md`). The full DQAR framework, six audit domains, three-tier findings structure, regulatory timeline, and partner guides live in the DQAR Shared KB project. This application does not implement the full framework — it implements the technical pipeline that powers UC1 assessment engagements.

**Partners:** Health Samurai (Aidbox + Termbox), Indicina (pipeline, query library, findings report)

---

## Architecture Summary

The app is a seven-stage data ingestion and validation pipeline. All stages involving PHI execute in the client's environment. Only anonymized data and conformance reports cross to Indicina's infrastructure.

```
CLIENT ENVIRONMENT (PHI present)
  Preflight:   CapabilityStatement check — server capability + resource inventory
               output: preflight-report.json
  Stage 1:     Client $export — US Core 6.1.0 ndjson
  Stage 1a:    NDJSON structural validation
               output: stage1a-report.json (no PHI)
  Stage 1b:    Resource conformance ($validate — base FHIR R4 + US Core 6.1.0)
               output: stage1b-{engagement}.json (no PHI)
  Stage 1c:    Bulk FHIR API protocol conformance ($export async protocol + manifest)
               output: stage1c-{engagement}.json (no PHI)
  Stage 3:     PHI redaction + anonymization

PHI BOUNDARY — nothing above crosses to Indicina

INDICINA ENVIRONMENT (no PHI)
  Stage 4:  Delivery — anonymized extract + 3 conformance reports
  Stage 5:  Load to Aidbox sandbox
            (a) Base FHIR R4 validation on write
            (b) US Core 6.1.0 profile validation on write
            (c) Termbox $validate-code — US Core bindings + HEDIS MY2025 VSD
            (d) AuditEvent + 6 extensions generated atomically
  Stage 6:  DQAR SQL on FHIR assessment queries
  Stage 7:  Three-tier findings report generation
```

---

## Client-Side Validation Kit (Stages 1a, 1b, 1c)

### Deliverable to client at engagement kickoff

Indicina provides a validation kit the client's IT team runs on their own infrastructure against raw PHI-containing ndjson before redaction. Findings from this kit are delivered to Indicina as aggregate reports with no PHI.

The kit is configured via engagement config files (see **Engagement Configuration** section below). Each engagement config declares the FHIR server type, base URL, and credentials. The `--engagement` flag is the single required input for all kit scripts.

### Preflight — CapabilityStatement check

```bash
python packages/client-kit/preflight/preflight_check.py \
  --engagement config/engagements/{client}.json \
  --output preflight-report.json
```

Checks that the target FHIR server declares all required US Core resource types and reports whether Bulk FHIR `$export` is supported. Output is read by Stage 1c to determine whether bulk export protocol testing applies.

### Stage 1a — NDJSON structural validation

```bash
python packages/client-kit/validator/stage1a_ndjson_validator.py \
  --ndjson-dir data/export \
  --output data/stage1a-report.json
```

Five structural checks per `.ndjson` file: UTF-8 decodable, no empty files, all lines valid JSON, `resourceType` present on every record, filename stem matches declared resource type. Outputs aggregate counts only — no PHI in report.

### Stage 1b — Resource conformance ($validate)

```bash
python packages/client-kit/validator/stage1b_fhir_uscore_validator.py \
  --engagement config/engagements/{client}.json \
  --ndjson-dir data/export \
  --output data/stage1b-{engagement}.json
```

Posts each resource to the FHIR server's `/{ResourceType}/$validate` endpoint. Classifies returned OperationOutcome issues as `base-fhir` (core R4 constraint) or `us-core` (US Core 6.1.0 profile violation) by inspecting the `http://hl7.org/fhir/us/core` URL prefix in diagnostics and expression fields. Both base FHIR R4 and US Core conformance are assessed in a single pass — the engagement's server performs both validations and the response is classified accordingly.

Run against multiple engagements to compare server behaviour on the same dataset.

### Stage 1c — Bulk FHIR API protocol conformance

```bash
python packages/client-kit/validator/stage1c_bulk_fhir_export.py \
  --engagement config/engagements/{client}.json \
  --preflight-report preflight-report.json \
  --output data/stage1c-{engagement}.json
```

Tests the server's `$export` implementation against the SMART Bulk Data Access IG. Six checks: `capability_declares_export`, `kick_off_accepted` (202 response), `content_location_header`, `polling_completes`, `manifest_valid` (output array + requiresAccessToken), `output_content_type` (application/fhir+ndjson). Skipped automatically when preflight reports `bulk_export_supported: false`.

### Conformance report format (delivered to Indicina — no PHI)

Stage 1b report (one per engagement):

```json
{
  "report_type": "fhir-validation",
  "stage": "1b",
  "generated_at": "2025-10-14T09:00:00Z",
  "engagement": "client-aidbox-prod",
  "server_type": "aidbox",
  "fhir_server": "https://client.edge.aidbox.app",
  "ndjson_dir": "/data/export",
  "summary": {
    "total_resources": 48230,
    "base_fhir_issues": 234,
    "us_core_issues": 613,
    "total_issues": 847
  },
  "files": [
    {
      "resource_type": "Condition",
      "file": "Condition.ndjson",
      "record_count": 12440,
      "issue_counts": {"base_fhir": 45, "us_core": 189},
      "issues": [
        {
          "resource_id": "cond-abc123",
          "severity": "error",
          "layer": "us-core",
          "code": "MUST_SUPPORT",
          "diagnostics": "Condition.clinicalStatus is required by US Core",
          "expression": ["Condition.clinicalStatus"]
        }
      ]
    }
  ]
}
```

---

## Feed Manifest (Client Deliverable — Engagement Kickoff)

The feed manifest is the ground truth for feed-level traceability. Collected before extract generation.

```json
{
  "plan_id": "[pseudonymized at delivery]",
  "extract_date": "2025-10-14",
  "us_core_version": "6.1.0",
  "fhir_version": "4.0.1",
  "feeds": [
    {
      "feed_id": "epic-prod-org447",
      "feed_type": "ehr-fhir-bulk",
      "source_system_name": "Epic EHR",
      "source_system_type": "ehr-clinical",
      "files": ["Patient.ndjson", "Condition.ndjson", "Observation.ndjson",
                "Encounter.ndjson", "Procedure.ndjson"],
      "member_count": 4823,
      "notes": "Epic MyChart FHIR R4 bulk export, org 447"
    },
    {
      "feed_id": "claims-edw-prod",
      "feed_type": "administrative-claims",
      "source_system_name": "Claims EDW",
      "source_system_type": "administrative",
      "files": ["ExplanationOfBenefit.ndjson", "Coverage.ndjson"],
      "member_count": 9847
    },
    {
      "feed_id": "labcorp-hl7v2",
      "feed_type": "lab-fhir-transformed",
      "source_system_name": "LabCorp",
      "source_system_type": "lab",
      "files": ["Observation-lab.ndjson", "DiagnosticReport.ndjson"],
      "member_count": 3201,
      "notes": "HL7v2 ORU transformed to FHIR via Interbox"
    }
  ]
}
```

**Absence of feed manifest** = Level 6 governance finding (metadata management maturity score 1).
**Resources from undeclared sources** = undeclared source finding (data governance gap).

---

## Aidbox Assessment Sandbox Configuration

### Required Health Samurai products

| Product | Role |
|---|---|
| Aidbox | FHIR R4 server + PostgreSQL store for anonymized extract |
| Termbox | Terminology server — MY2025 VSD + US Core 6.1.0 bindings |

### Aidbox configuration requirements

```yaml
# Aidbox sandbox configuration for DQAR UC1 assessment
fhir_version: R4
postgres:
  database: dqar_assessment
  
validation:
  # US Core 6.1.0 IG loaded on write
  igs:
    - hl7.fhir.us.core#6.1.0
    - hl7.fhir.uv.bulkdata#2.0.0
  
audit:
  # AuditEvent generation on every FHIR operation
  enabled: true
  
terminology:
  # Termbox endpoint for $validate-code
  termbox_endpoint: http://termbox:8080
```

### Termbox VSD configuration

Three modes for VSD access (client determines which applies):

| Mode | Description | BAA required |
|---|---|---|
| 1 — API reference | Client's Termbox instance, Indicina read-only API key | No (read-only access) |
| 2 — Client export | Client-provided VSD export loaded to sandbox, deleted at close | SOW clause required |
| 3 — JSON from dQM package | FHIR ValueSet resources from client's NCQA DCS package | No additional license |

---

## Engagement Configuration

All client-side kit scripts accept a single `--engagement` flag pointing to a JSON config file. This decouples server connection details from the pipeline code and supports running the same validation against multiple server instances (e.g., client's Aidbox sandbox vs. public HAPI for comparison).

### Config file location

```
config/
  engagement.schema.json          # committed — documents the schema
  engagements/
    {client-name}.json            # gitignored — contains credentials
```

### Schema (`config/engagement.schema.json`)

```json
{
  "name": "client-aidbox-prod",
  "server_type": "aidbox",
  "base_url": "https://{instance}.edge.aidbox.app",
  "client_id": "<oauth2-client-id>",
  "client_secret": "<oauth2-client-secret>"
}
```

```json
{
  "name": "client-hapi-r4",
  "server_type": "hapi",
  "base_url": "https://hapi.fhir.org/baseR4"
}
```

Supported `server_type` values:

| Value | Auth method | Notes |
|---|---|---|
| `aidbox` | OAuth2 `client_credentials` — fetches Bearer token from `/auth/token` | `client_id` and `client_secret` required |
| `hapi` | HTTP Basic (optional) or no auth | `basic_user` / `basic_password` optional |

### Implementation (`shared/engagement.py`)

`load_engagement(config_path)` → `EngagementConfig` dataclass  
`get_fhir_headers(engagement)` → auth headers dict for FHIR requests

All kit scripts use this shared module. Engagement configs are gitignored — credentials never enter source control.

---

## AuditEvent Extension Metadata (Six Fields)

Generated by the Indicina ingest pipeline at Stage 5 write time. Not sourced from the client's FHIR server.

### Extension definitions

```json
[
  {
    "url": "http://indicina.com/fhir/ext/source-type",
    "valueType": "valueCode",
    "vocabulary": ["ehr-clinical", "administrative", "lab", "pharmacy", "p2p", "unknown"],
    "source": "feed-manifest | meta.source | resource-inference",
    "confidence": "asserted | high | medium | low | unknown",
    "purpose": "Classifies originating source system type. Study Type 2 lineage analysis."
  },
  {
    "url": "http://indicina.com/fhir/ext/source-system-id",
    "valueType": "valueString",
    "format": "feed-id from manifest | SHA256(meta.source)[:12] | topology-cluster-{hash} | unknown-{pipeline-id}-{resource-type}",
    "purpose": "Pseudonymized source system instance ID. Consistent across all resources from same source."
  },
  {
    "url": "http://indicina.com/fhir/ext/hedis-source-declaration",
    "valueType": "valueCode",
    "vocabulary": ["ecds-ehr", "ecds-administrative", "ecds-lab", "ecds-pharmacy", "ecds-p2p", "ecds-unknown"],
    "mapping": "Derived from source-type via direct vocabulary map",
    "purpose": "NCQA ECDS data source type vocabulary. Measure attribution join key."
  },
  {
    "url": "http://indicina.com/fhir/ext/ingest-pipeline-id",
    "valueType": "valueString",
    "format": "{pipeline-run-id}/{feed-id}/{batch-id}",
    "example": "dqar-20251014-001/epic-prod-org447/Condition.ndjson-chunk-003",
    "purpose": "Three-level traceability: run / feed / batch. Enables feed-level quality analysis."
  },
  {
    "url": "http://indicina.com/fhir/ext/source-feed-id",
    "valueType": "valueString",
    "format": "feed_id from manifest | derived from meta.source | topology-cluster-{hash} | unknown",
    "example": "epic-prod-org447",
    "purpose": "Feed-level identifier independent of full pipeline composite. Primary key for feed-level findings queries."
  },
  {
    "url": "http://indicina.com/fhir/ext/source-inference-confidence",
    "valueType": "valueCode",
    "vocabulary": ["asserted", "high", "medium", "low", "unknown"],
    "purpose": "Confidence tier for source-type inference. Proportion at each tier is a direct provenance maturity metric."
  }
]
```

Note: six extension fields total (EXT 1–4 original + EXT 5 source-feed-id + EXT 6 inference-confidence).

### Atomic transaction bundle pattern

```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "resource": { "resourceType": "Condition", "id": "pat-abc123-cond-001", "..." },
      "request": { "method": "PUT", "url": "Condition/pat-abc123-cond-001" }
    },
    {
      "resource": {
        "resourceType": "AuditEvent",
        "type": { "system": "http://terminology.hl7.org/CodeSystem/audit-event-type", "code": "rest" },
        "recorded": "2025-10-14T09:22:00Z",
        "agent": [{ "requestor": true, "who": { "display": "dqar-ingest-pipeline" } }],
        "source": { "observer": { "display": "Indicina DQAR Sandbox" } },
        "entity": [{ "what": { "reference": "Condition/pat-abc123-cond-001" } }],
        "extension": [
          { "url": "http://indicina.com/fhir/ext/source-type", "valueCode": "ehr-clinical" },
          { "url": "http://indicina.com/fhir/ext/source-system-id", "valueString": "epic-prod-org447" },
          { "url": "http://indicina.com/fhir/ext/hedis-source-declaration", "valueCode": "ecds-ehr" },
          { "url": "http://indicina.com/fhir/ext/ingest-pipeline-id", "valueString": "dqar-20251014-001/epic-prod-org447/Condition.ndjson-chunk-003" },
          { "url": "http://indicina.com/fhir/ext/source-feed-id", "valueString": "epic-prod-org447" },
          { "url": "http://indicina.com/fhir/ext/source-inference-confidence", "valueCode": "asserted" }
        ]
      },
      "request": { "method": "POST", "url": "AuditEvent" }
    }
  ]
}
```

---

## Source-Type Inference Algorithm

Applied when feed manifest does not explicitly declare source-type for a resource and `meta.source` is absent. See `dqar-05-source-inference-algorithm.md` for full decision tree.

### Quick reference

| Signal | Source-type | Confidence |
|---|---|---|
| feed manifest declaration | as declared | asserted |
| meta.source present | URI-derived | asserted |
| ExplanationOfBenefit | administrative | high |
| MedicationDispense | pharmacy | high |
| Observation category=laboratory | lab | high |
| Observation category=vital-signs | ehr-clinical | high |
| Condition + SNOMED + verificationStatus | ehr-clinical | medium |
| Condition + ICD-10-CM only | administrative | medium |
| Encounter + CPT codes + sparse participants | administrative | medium |
| Encounter + SNOMED + rich participants | ehr-clinical | medium |
| Topology cluster match | cluster-derived | low |
| No signals | unknown | unknown |

**Undeclared source finding:** Resources where `source-feed-id = unknown` and feed manifest was provided are documented as undeclared source findings — data flowing from systems not in the plan's own inventory.

---

## SQL on FHIR Assessment Queries — Minimum Viable Library

Five priority measures for UC1 MVP. Each measure has four query types: denominator context check, measurement period window check, exclusion code context check, data source attribution check.

### Infrastructure

```sql
-- HEDIS VSD lookup function (Aidbox PostgreSQL)
-- Requires VSD loaded via Indicina VSD loader
CREATE OR REPLACE FUNCTION hedis_validate_code(
  p_code TEXT,
  p_system TEXT,
  p_value_set_oid TEXT
) RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM hedis_vsd
    WHERE code = p_code
    AND code_system = p_system
    AND value_set_oid = p_value_set_oid
    AND measurement_year = '2025'
  );
$$ LANGUAGE SQL;

-- Measure attribution join function
CREATE OR REPLACE FUNCTION get_resource_provenance(p_resource_ref TEXT)
RETURNS TABLE (
  source_type TEXT,
  source_feed_id TEXT,
  hedis_declaration TEXT,
  pipeline_id TEXT,
  inference_confidence TEXT,
  ingest_timestamp TIMESTAMPTZ
) AS $$
  SELECT
    ext_src.value->>'valueCode',
    ext_feed.value->>'valueString',
    ext_hdx.value->>'valueCode',
    ext_pip.value->>'valueString',
    ext_conf.value->>'valueCode',
    (ae.resource->>'recorded')::timestamptz
  FROM auditevent ae
  CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_src
  CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_feed
  CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_hdx
  CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_pip
  CROSS JOIN LATERAL jsonb_array_elements(ae.resource->'extension') ext_conf
  WHERE ae.resource #>> '{entity,0,what,reference}' = p_resource_ref
  AND ext_src.value->>'url'  = 'http://indicina.com/fhir/ext/source-type'
  AND ext_feed.value->>'url' = 'http://indicina.com/fhir/ext/source-feed-id'
  AND ext_hdx.value->>'url'  = 'http://indicina.com/fhir/ext/hedis-source-declaration'
  AND ext_pip.value->>'url'  = 'http://indicina.com/fhir/ext/ingest-pipeline-id'
  AND ext_conf.value->>'url' = 'http://indicina.com/fhir/ext/source-inference-confidence'
  LIMIT 1;
$$ LANGUAGE SQL;
```

### Priority measure stubs

**CBP — Controlling Blood Pressure**
- Denominator: members 18-85 with hypertension diagnosis (value set OID: 2.16.840.1.113883.3.464.1003.104.12.1003)
- Level 3 checks: outpatient or telehealth encounter type (class AMB or VR), measurement year date window, blood pressure Observation linked to qualifying encounter
- Key failure mode: encounter type constraint — inpatient BP readings should not qualify denominator

**CDC — Comprehensive Diabetes Care**
- Multiple numerators: HbA1c testing, HbA1c control, eye exam, kidney health evaluation, blood pressure
- Level 3 checks: HbA1c LOINC code in correct value set, result value in physiological range (4-15%), result date within measurement year, performing lab linked
- Key failure mode: HbA1c LOINC cross-mapping errors (lab-specific local codes not mapped to standard LOINC)

**COL-E — Colorectal Cancer Screening ECDS**
- Denominator: members 45-75
- Level 3 checks: age constraint applied at measurement year end, exclusion codes in correct context (colorectal cancer diagnosis, colectomy), screening procedure in correct value set
- Key failure mode: exclusion code applied to wrong encounter type silently suppressing eligible members

**BCS-E — Breast Cancer Screening ECDS**
- Denominator: women 50-74
- Level 3 checks: sex/gender constraint, 24-month lookback window for mammography, exclusion for bilateral mastectomy
- Key failure mode: 24-month window not applied — 12-month window used instead, inflating apparent compliance

**FUH/FUM — Follow-Up After Hospitalization**
- Denominator: members discharged from inpatient psychiatric facility
- Level 3 checks: discharge date as anchor for follow-up window (7 days / 30 days), follow-up encounter type constraint (outpatient mental health), encounter sequence logic
- Key failure mode: discharge date vs. admit date confusion — wrong anchor shifts measurement window

Full query implementations: `queries/level3/` directory in the UC1 app repo.

---

## Findings Report Structure

### Three-tier output

```json
{
  "engagement_id": "dqar-uc1-[plan-id]-2025",
  "assessment_date": "2025-10-14",
  "plan_size": "500K-2M",
  "findings": {
    "tier1_compliance_gaps": [
      {
        "finding_id": "T1-001",
        "domain": "Domain 2 — Value Set Conformance",
        "description": "CBP denominator binding using MY2024 hypertension value set — 3 retired ICD-10 codes still active in production",
        "severity": "HIGH",
        "affected_members": 1247,
        "rate_impact_estimate": "1.2 percentage points",
        "remediation_owner": "Terminology governance",
        "remediation_timeline": "Days — VSD update required"
      }
    ],
    "tier2_measure_data_gaps": [],
    "tier3_digital_readiness_gaps": [
      {
        "finding_id": "T3-001",
        "domain": "Domain 6 — ECDS Readiness",
        "description": "No meta.source or Provenance resources present in extract. Source-type inferred for 89% of resources. Inference confidence: high 34%, medium 41%, low 14%, unknown 11%.",
        "severity": "MEDIUM",
        "my2029_risk": "HIGH — NCQA provenance evaluation methodology hardening",
        "remediation_owner": "FHIR server / integration team",
        "remediation_timeline": "Weeks — meta.source population on all writes"
      }
    ]
  },
  "provenance_coverage": {
    "asserted": 0.11,
    "high": 0.34,
    "medium": 0.41,
    "low": 0.14,
    "unknown": 0.0
  },
  "feed_manifest_declared": true,
  "undeclared_sources": 0
}
```

---

## Technology Stack

| Component | Technology | Version |
|---|---|---|
| FHIR server | Aidbox (Health Samurai) | Current |
| Terminology server | Termbox (Health Samurai) | Current |
| Database | PostgreSQL (Aidbox-managed) | 14+ |
| FHIR validation | HAPI FHIR Validator CLI | Latest |
| US Core IG | hl7.fhir.us.core | 6.1.0 |
| SQL on FHIR | SQL on FHIR v2 ViewDefinition | HL7 spec |
| Anonymization | Python 3.11+ | — |
| Lineage tooling | OpenLineage / Marquez (optional) | — |

---

## Open Items — Confirm Before Build

1. **NCQA dQM license for SQL query derivation** — confirm whether building SQL on FHIR queries from Vol. 2 narrative specifications (Indicina-held license) requires separate authorization for consulting use, or whether deriving queries from dQM CQL packages requires a custom NCQA license. Path 2 (Vol. 2 derivation) is the safe default.

2. **Aidbox US Core 6.1.0 profile validation on write** — confirm with Health Samurai that Aidbox supports US Core 6.1.0 profile validation at write time (not just at query time). Confirm whether auto-Provenance generation on ingest is configurable.

3. **Termbox standalone licensing** — confirm with Health Samurai whether Termbox can be licensed independently of Aidbox for plans that already have a FHIR server. This affects UC3 (monitoring service) commercial model.

4. **Velox Health Metadata integration** — confirm Velox's specific capabilities for feed-level lineage documentation. Velox is a clinical data inventory and scoring platform (veloxhealthmetadata.com). Their 10-10-10 assessment process is complementary to DQAR. Explore referral/partner relationship.

5. **NCQA dQM Evaluation Package pricing** — contact NCQA Account Executive to confirm pricing and whether evaluation package covers consulting use of JSON value sets.
