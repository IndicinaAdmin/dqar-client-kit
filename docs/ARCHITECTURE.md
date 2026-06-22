# System Architecture

High-level design of dqar-client-kit and how it fits into the DQAR platform.

---

## Purpose

dqar-client-kit is a Python CLI tool that:

1. **Validates manifest.json** — checks that your data source declarations are correct
2. **Validates FHIR data** — runs five levels of conformance checks against your records
3. **Generates UC properties** — produces Databricks metadata for your flattened tables
4. **Detects lineage gaps** — identifies where pre-FHIR transformation is not instrumented
5. **Produces findings** — classifies issues as Tier 1 (governance), Tier 2 (quality), Tier 3 (readiness)

---

## Core Components

### Phase 1: CLI Architecture

```
┌─ client-kit (entry point)
│  ├─ validate-manifest    (Manifest validator)
│  ├─ validate-data        (Conformance validator)
│  └─ validate-all         (Orchestrator)
```

**Subcommands:**
- `validate-manifest manifest.json` — Check manifest syntax/semantics
- `validate-data --manifest M --data D --level L` — Run conformance checks
- `validate-all --manifest M --data D --level L` — End-to-end validation

**Dependencies:**
- click ≥8.1.0 (CLI framework)
- pydantic ≥2.0 (data validation)
- ndjson ≥0.3.1 (NDJSON parsing)
- pandas ≥2.0 (data aggregation)

---

### Phase 2: Data Conformance Validator

```
ManifestValidator
  ├─ Schema validation (Pydantic)
  ├─ Uniqueness checks (feed_id, source_system_id)
  └─ Business rules (source_type, ecds_ssor)
     
ManifestMatcher
  ├─ meta.source.reference matching
  ├─ filename_pattern matching
  └─ external_batch_manifest matching
     
ConformanceValidator (5 Levels)
  ├─ Level 1: Terminology → VSD conformance engine
  ├─ Level 2: Profile → HAPI FHIR Validator
  ├─ Level 3: Context → SQL on FHIR ViewDefinitions
  ├─ Level 4: Plausibility → PIQI rules
  └─ Level 5: Stability → scikit-learn anomaly detection (optional)

MemberDrilldownExporter
  └─ CSV of eligible members + enrollment gaps

CanonicalFeedInventory
  └─ JSON of all detected feeds + metadata
```

**Output:**
- Per-resource conformance scores (Levels 1–4)
- Per-resource-type aggregates
- Per-feed aggregates (+ PIQI dimensions)
- Per-plan summary
- Tier 1–2 findings

---

### Phase 3: UC Properties Generator

```
UCPropertiesJSONExporter
  └─ Generate JSON for Databricks SDK loading

UCPropertiesSQLExporter (Jinja2)
  └─ Generate SQL DDL for manual execution

DatabricksSDKLoader (example)
  └─ Reference implementation using databricks-sdk

TerraformIaCExample
  └─ Reference Terraform configuration
```

**Output:**
- `{engagement_id}_uc_properties.json`
- `{engagement_id}_uc_properties.sql`

---

### Phase 4: Lineage Detection

```
dbtManifestParser
  ├─ Extract models, sources, dependencies
  └─ Parse dbt meta tags (dqar_*)

LineageDetectionValidator
  ├─ Check 1: Source → Staging
  ├─ Check 2: Staging → FHIR flattening
  └─ Check 3: OpenLineage instrumentation

OpenLineageEmissionValidator
  └─ Verify DQARIngestFacet presence
```

**Output:**
- Lineage graph (sources → models → outputs)
- Tier 3 findings (pre-FHIR lineage gaps)

---

### Phase 5: Orchestration & Findings Aggregation

```
validate_all orchestrator
  ├─ Phase 1: Validate manifest
  ├─ Phase 2: Validate data conformance
  ├─ Phase 3: Generate UC properties
  ├─ Phase 4: Detect lineage gaps
  └─ Phase 5: Aggregate findings

DQARFindingsAggregator
  ├─ Tier 1: Governance gaps
  ├─ Tier 2: Data quality issues
  └─ Tier 3: Digital readiness gaps

ExecutiveSummaryGenerator
  └─ HTML report

LoadInstructionsGenerator
  └─ Step-by-step guide to load properties

CIGateway
  └─ Exit code for CI/CD pipelines
```

---

## Data Flow

### Diagram

```
manifest.json + *.ndjson files
        ↓
     [Phase 1]
  ManifestValidator
        ↓
   [Phase 2]
 ConformanceValidator
   (Levels 1–4)
        ↓
   [Phase 3]
 UCPropertiesGenerator
        ↓
   [Phase 4]
 dbtManifestParser +
 LineageDetectionValidator
        ↓
   [Phase 5]
 DQARFindingsAggregator
 ExecutiveSummaryGenerator
        ↓
 outputs/
  ├─ uc_properties.json
  ├─ uc_properties.sql
  ├─ conformance_scores.json
  ├─ findings_tier_1_2_3.json
  └─ SUMMARY.html
```

---

## Integration Points

### Upstream: Client Onboarding

```
Client delivers manifest + NDJSON to S3
        ↓
     [client-kit runs]
        ↓
Validates, scores, generates findings
```

### Downstream: Aidbox + Databricks

```
[client-kit outputs] UC properties
        ↓
     [aidbox-databricks-kit]
        ├─ Load properties to Databricks
        ├─ Emit OpenLineage → OpenMetadata
        └─ Initialize AuditEvent logging
        ↓
[sql-on-fhir-libraries] run HEDIS measures
```

---

## Dependency Tree

```
dqar-client-kit
├─ click (CLI)
├─ pydantic (validation)
├─ ndjson (NDJSON parsing)
├─ pandas (aggregation)
├─ requests (HTTP calls)
├─ jinja2 (template rendering)
└─ [optional] scikit-learn (Level 5 anomaly detection)
```

---

## Conformance Score Aggregation

### Per-Resource

Each FHIR resource gets scored on Levels 1–4:

```json
{
  "resource_id": "Observation/lab-123",
  "level_1": 1.0,  // Pass/Fail binary
  "level_2": 0.95, // % pass for profile
  "level_3": 0.87, // % match to context rules
  "level_4": 0.92  // % within plausibility
}
```

### Per-Resource-Type

All resources of a type (e.g., "Observation") averaged:

```json
{
  "resource_type": "Observation",
  "resource_count": 150000,
  "level_1_avg": 0.9850,
  "level_2_avg": 0.9800,
  "level_3_avg": 0.9900,
  "level_4_avg": 0.9750
}
```

### Per-Feed

All resources from a feed aggregated:

```json
{
  "feed_id": "lab-vendor-x-daily",
  "resource_count": 250000,
  "level_1_avg": 0.9805,
  "level_2_avg": 0.9750,
  "level_3_avg": 0.9820,
  "level_4_avg": 0.9700,
  "piqi_usability": 0.995,
  "piqi_plausibility": 0.998,
  "piqi_comparability": 0.987,
  "piqi_stability": "PASS"
}
```

### Plan-Level

Across all resources and feeds:

```json
{
  "plan": "Acme Health Plan",
  "total_resources": 5000000,
  "level_1_avg": 0.9850,
  "level_2_avg": 0.9800,
  "level_3_avg": 0.9900,
  "level_4_avg": 0.9750
}
```

---

## Tier Classification

### Tier 1: Governance Gaps

Manifest/declaration issues:

- Undeclared sources (resources with no matched feed)
- Missing manifest linkage (source system not in manifest)
- No change control (Interbox rule version missing)

**Detection:** Manifest validator + manifest matcher

**Impact:** Cannot move to Level 2 maturity

---

### Tier 2: Data Quality Issues

FHIR validation failures:

- Codes outside value set (Level 1 failure)
- Profile conformance issues (Level 2 failure)
- Clinical context mismatches (Level 3 failure)
- Implausible values (Level 4 failure)

**Detection:** ConformanceValidator (Levels 1–4)

**Impact:** Measure accuracy at risk

---

### Tier 3: Digital Readiness Gaps

Lineage + instrumentation gaps:

- Pre-FHIR lineage not instrumented (dbt check)
- Measure logic not versioned (SQLQuery Libraries)
- No AuditEvent logging

**Detection:** LineageDetectionValidator (Phase 4)

**Impact:** Cannot move from Level 2 to Level 3 maturity

---

## Maturity Rungs vs. Tier Alignment

```
Rung 1 (Manual):
  → All Tiers present (governance, QA, readiness gaps)

Rung 2 (Level 2):
  → Tier 2 remediated (conformance ≥0.95)
  → Tier 3 still acceptable

Rung 3 (Level 3):
  → Tier 1 + 2 + 3 remediated
  → OpenLineage instrumented
  → SQL-on-FHIR measures versioned

Rung 4 (Study Type 2):
  → Mappings as code (Interbox with dbt)
  → Field-level lineage (DQARIngestFacet)

Rung 5 (Ops):
  → Continuous monitoring
  → Automated remediation
```

---

## Performance Characteristics

### Latency

- Manifest validation: <100ms
- Data conformance (1M resources): ~5–10 min
- UC property generation: <1 sec
- dbt manifest parsing: <1 sec

### Memory

- Per-resource metadata: ~1KB
- Aggregated statistics: ~10MB

---

## Error Handling & Exit Codes

| Exit Code | Meaning |
|---|---|
| 0 | All validations passed |
| 1 | Manifest validation failed |
| 2 | Data conformance failed |
| 3 | Output generation failed |
| 4 | dbt manifest parsing failed |
| 5 | Lineage detection failed |

---

## Testing Strategy

**Unit tests:**
- Manifest validator rules
- Conformance level scorers
- UC property generation

**Integration tests:**
- Full pipeline (manifest → data → UC properties)
- dbt manifest parsing
- HTML report generation

**Reference tests:**
- HAPI FHIR Validator integration
- Termbox integration (if available)
- Databricks SDK loading (mocked)

---

## Roadmap

### v1.0 (Current)
- Phases 1–4 complete
- Levels 1–4 conformance
- Core Tier 1–3 findings

### v1.1 (Planned)
- Level 5 (stability) enabled by default
- Improved dbt integration
- OpenLineage facet validation

### v2.0 (Future)
- Real-time streaming validation
- Continuous monitoring mode
- Automated remediation suggestions

