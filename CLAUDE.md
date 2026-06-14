# CLAUDE.md — Indicina DQAR Project
*Digital Quality Audit Readiness — Claude Code project briefing*
*Last updated: June 2026 | Confidential — Internal*

---

## What This Project Is

Indicina provides the **Digital Quality Audit Readiness (DQAR)** methodology — a proprietary framework that assesses U.S. health payer readiness for digital quality reporting. It replaces the manual, PSV-heavy HEDIS compliance audit paradigm with a FHIR-native, automated, semantically rigorous assessment.

**The one-sentence value proposition:** NCQA certifies that measure logic executes correctly. NCQA DCS explicitly does not validate data mapping or accuracy. DQAR fills that gap — validating the five semantic layers between raw payer data and the CQL engine.

**Indicina's position:** Assessment and advisory consultant, not a certified HEDIS auditor. This is by design — staying advisory means Indicina is free to assess dimensions Vol. 5 doesn't cover, can assess and remediate with the same client, and is not tied to the HEDIS calendar.

---

## Aidbox / FHIR Infrastructure Reference

> For all development work and business explanation involving FHIR storage, APIs, search, access control, subscriptions, SQL on FHIR, bulk operations, MCP tools, or Aidbox configuration — see @docs/aidbox-kb.md

This KB should inform every implementation decision touching Aidbox, Termbox, and the Health Samurai stack. When explaining platform capabilities to business clients, use the KB to ground technical claims before translating them.

---

## Partner Stack

| Partner | Product | Role in DQAR |
|---|---|---|
| **Health Samurai** | Aidbox | FHIR server + PostgreSQL for assessment sandbox and client production |
| **Health Samurai** | Termbox | MP2025 HEDIS VSD binding validation; hybrid terminology governance |
| **Health Samurai** | Interbox | HL7v2/C-CDA ingest pipeline instrumentation; AuditEvent metadata generation |
| **Velox** (prospective) | Business platform | Quality dashboards, measure tracking, gap closure for plan-side business users |

**Health Samurai relationship status:** Prospective partner as of June 2026. No formal agreement. Preferred FHIR vendor for DQAR assessment sandbox and client implementation referrals.

**Commercial model:** Aidbox + Termbox appear in the roadmap phase after assessment findings are independently documented. Assessment phase is vendor-neutral and fixed-fee.

---

## Project Structure — Four Projects

```
Project 1 — DQAR Shared KB        (authoritative framework — this project)
Project 2 — DQAR UC1 Assessment App   (Claude Code + Health Samurai)
Project 3 — DQAR UC2 Monitoring Service
Project 4 — DQAR UC3 P2P Exchange Quality
```

Every project references the Shared KB specs. UC1 App and UC3 additionally reference `dqar-06-uc1-app-technical-specification.md` and the Bulk FHIR Extract Specification.

---

## Core Framework Concepts

### The Core Thesis — Semantic Validation Gap

Most U.S. payers have:
- A FHIR surface that passes structural conformance ✅
- A data lakehouse for claims analytics ✅
- **Nothing between those layers that validates whether clinical data feeding HEDIS measure execution actually means what the measure specification requires** ❌

This semantic validation gap is the primary locus of HEDIS audit failure.

### Five-Level Semantic Validation (Track A)

| Level | Name | Tool | What it answers |
|---|---|---|---|
| 1 | Terminology conformance | Termbox + VSD | Is this code in the correct NCQA value set for this measurement period? |
| 2 | Resource structural conformance | HAPI FHIR Validator | Does this FHIR resource conform to US Core / QI Core profiles? |
| 3 | Context conformance | SQL on FHIR (Aidbox/Postgres) | Is this resource type correct for this measure? Encounter type enforced? Date in measurement period? |
| 4 | Clinical plausibility | SQL on FHIR + rules | Is this data physiologically plausible? (HbA1c ranges, age/sex consistency, encounter date vs. enrollment) |
| 5 | Population completeness | SQL on FHIR + PIQI framework | Are there systematic gaps by provider, geography, or data source? |

Level 6 (governance maturity) is Track B — DAMA-DMBOK/CMMI-DMM rubric assessing organizational capability, not just data state.

### Three-Tier Findings

| Tier | Name | Definition | Business significance |
|---|---|---|---|
| 1 | Governance gap | Organizational failure — change control, MDM, metadata management | Root cause that will produce the same error next measurement period if untouched |
| 2 | Measure data gap | Technical data quality failure affecting measure rates now | Correctable — patch ETL, update value set |
| 3 | Digital readiness gap | Capability gap vs. MP2029 ECDS mandatory or CMS-0057-F P2P | Not failing today; will fail the MP2029 transition without remediation |

Every finding carries both a **technical severity** (what is broken) and a **governance root cause** (why it broke and whether the plan can prevent recurrence).

---

## Active Use Cases

### UC1 — Digital Measure Readiness Assessment
- **Buying trigger:** MP2029 ECDS mandatory reporting deadline; plan doesn't know where they stand
- **Format:** Fixed-fee assessment
- **Aidbox role:** Assessment sandbox for SQL on FHIR measure queries after Stage 3 load
- **Termbox role:** MP2025 VSD binding validation at ingest
- **Output:** Three-tier DQAR findings report + remediation roadmap

### UC2 — Digital Quality Data Operations Monitoring
- **Buying trigger:** Plan wants continuous visibility into data quality drift post-assessment
- **Format:** $4K/month recurring subscription
- **Infrastructure:** Reuses UC1 pipeline on scheduled cadence (monthly/quarterly)
- **Output:** Quarterly digital quality scorecard + drift alerts + governance maturity progression

### UC3 — Payer-to-Payer Data Exchange Quality
- **Buying trigger:** P2P exchange live or imminent under CMS-0057-F; incoming data quality unknown
- **Format:** Fixed-fee assessment
- **CMS-0057-F deadline:** Patient Access, Provider Access, and P2P APIs required January 1, 2027
- **Extra conformance passes:** Dual-version US Core testing (3.1.1 and 6.1.0) + optional Da Vinci PDex + FHIR Consent validity check
- **Output:** Per-sender scorecard + three-tier findings for receiving plan

---

## Assessment Pipeline Architecture

### Six Stages — Client vs. Indicina Boundary

```
CLIENT ENVIRONMENT (PHI present — Stages 1a, 1b, 1c)

Stage 1a  Bulk FHIR API conformance preflight     [stage1a_bulk_fhir_export_preflight.py]
          Tests the plan's FHIR vendor $export implementation against Bulk Data Access IG STU2
          Six checks: CapabilityStatement, 202 Accepted, Content-Location, polling, manifest, content-type
          Output: stage1a-{engagement}.json

Stage 1b  ndjson structural conformance            [stage1b_ndjson_validator.py]
          Every line: parseable JSON, resourceType present, one resource per line, UTF-8
          FAIL at 1b blocks Stage 1c
          Output: stage1b-{engagement}.json + PDF

Stage 1c  FHIR R4 + US Core conformance           [stage1c_fhir_uscore_validator.py]
          1c-i  Base FHIR R4 (4.0.1) structural conformance (HAPI Validator or Aidbox)
          1c-ii US Core 6.1.0 profile conformance
          Output: stage1c-{engagement}.json + PDF

→ Client receives 3 JSON + 3 PDF reports
→ Client chooses a path:

PATH A — Stop. No data leaves the plan. Act on findings internally.
PATH B — PHI redaction locally → anonymized extract to Indicina sandbox (no BAA required)
PATH C — Full PHI direct to plan-owned Aidbox (post BAA — target state)

─────── PHI BOUNDARY (Path B only) ────────

INDICINA / PLAN-OWNED AIDBOX ENVIRONMENT

Stage 2   PHI redaction + anonymization           [Path B only — client-initiated]
          Pseudonym mapping table retained within client environment
          Referential integrity must be preserved across all resource references

Stage 3   Load to Aidbox sandbox                  [atomic transaction bundles]
          Each resource + AuditEvent posted as single atomic FHIR transaction bundle
          Re-run Stage 1b + 1c on loaded extract to confirm redaction integrity
          Termbox $validate-code: US Core required bindings + HEDIS MP2025 VSD (369 value sets)

Stage 4   SQL on FHIR semantic assessment          [five priority measures]
          Level 3–5 assessment queries against Aidbox/Postgres
          Source inference algorithm assigns source-type + AuditEvent extension metadata

Stage 5   Findings report generation
          Three-tier findings, measure rate impact estimates, governance maturity score
          Remediation roadmap sequenced against MP2029 / Jan 1 2027 deadlines
```

### Three Stage 1 Substages Test Independent Dimensions

- **Stage 1a** — can the FHIR server export at all? (API conformance)
- **Stage 1b** — are the exported files structurally valid? (file format)
- **Stage 1c** — does the exported content conform to US Core? (resource conformance)

A plan can pass 1a and 1b while every resource fails 1c. These are three different questions.

---

## Aidbox Role in the Pipeline — Critical Implementation Notes

### AuditEvent Pattern
Every resource loaded into Aidbox must be posted as a **single atomic FHIR transaction bundle** together with its AuditEvent. Separate writes risk resources without audit records if the pipeline fails between operations. This is a hard architectural requirement, not a preference.

### Seven AuditEvent Extension Fields (Indicina-defined)
Indicina generates these at Stage 3 ingest — they are not produced by Aidbox automatically:

| Extension URL | Field name | Purpose |
|---|---|---|
| `http://indicina.com/fhir/ext/source-type` | EXT 1 | Source type vocabulary (13 values — see source inference algorithm) |
| `http://indicina.com/fhir/ext/source-system-id` | EXT 2 | Originating system identifier |
| `http://indicina.com/fhir/ext/source-feed-id` | EXT 3 | Primary key for feed-level queries |
| `http://indicina.com/fhir/ext/source-inference-confidence` | EXT 4 | Direct provenance maturity metric |
| `http://indicina.com/fhir/ext/ecds-ssor` | EXT 5 | NCQA ECDS SSoR four-category vocabulary (derived from EXT 1) |
| `http://indicina.com/fhir/ext/ingest-pipeline-id` | EXT 6 | Pipeline run identifier (orchestrator-set; not inference-derived) |
| `http://indicina.com/fhir/ext/ol-run-id` | EXT 7 | OpenLineage run ID UUID — links AuditEvent to lineage graph (Marquez/OpenMetadata) |

### What Aidbox Provides Out of the Box
- AuditEvent on every FHIR API operation (who, what, when, outcome)
- PostgreSQL JSONB storage — queryable via SQL on FHIR
- HIPAA audit control compliance (45 CFR §164.312(b))

### What Requires Additional Implementation
- The seven AuditEvent extension fields — must be added by the ingest pipeline before POSTing
- Measure-level execution provenance linking CQL results back to source resources
- Auto-Provenance resource generation on ingest (confirm with Health Samurai)

### US Core Version Requirement
- **Required for assessment:** US Core 6.1.0 (USCDI v3, CMS-0057-F compliant)
- **Outdated:** US Core 3.1.1 — documented as UC3 gap finding with Jan 1 2027 deadline attached
- **Forward-compatible:** US Core 7.0.0 — acceptable
- Plans on 3.1.1 should declare their version; Indicina assesses against the available version and documents the conformance delta

---

## Platform Ladder — Commercial Architecture

The ladder gives Indicina productive billable work at every stage while the plan's security/compliance team completes HIPAA and SOC2 due diligence on Health Samurai.

```
Rung 1 — Offline Conformance Testing
  No PHI leaves the plan. No HS infrastructure required.
  Client-side Stage 1 testing kit + Track B governance interviews.
  Deliverable: preliminary findings + Level 6 governance score.
  Revenue: low fixed-fee or retainer-included.

Rung 2 — Anonymized Sandbox Assessment (UC1 standard)
  PHI-redacted extract → Indicina-managed Aidbox + Termbox sandbox.
  Full five-level assessment + three-tier findings report.
  HS HIPAA BAA + SOC2 review runs concurrently — no plan-side HS contract yet.
  Revenue: UC1 fixed-fee.

Rung 3 — Continuous Monitoring (UC2 subscription)
  Plan has completed HS HIPAA BAA + SOC2 review. HS contract in place.
  UC2 monthly/quarterly cadence. Termbox client-hosted or SOW.
  Revenue: $4K/month retainer + HS licensing.

Rung 4 — Full PHI Operational Mode (Path C — target state)
  No redaction step. Bulk FHIR extract → plan-owned Aidbox directly.
  Conformance testing kit becomes the production pre-ingest quality gate.
  AuditEvent metadata is permanent production lineage from day one.
  Revenue: $4K/month retainer + HS Aidbox/Termbox licensing.
```

---

## Source-Type Inference Algorithm (Summary)

When a client FHIR extract has no `meta.source` URI and no Provenance resources, source-type is inferred from FHIR resource structure signals.

### Tier A — Structurally Detectable
| source-type | Primary detection signal |
|---|---|
| `clinical_ehr` | SNOMED codes + verificationStatus + recorder + rich Encounter participants |
| `administrative_claims` | ExplanationOfBenefit or Claim (determinative); ICD-10-only Condition |
| `administrative_encounter` | CPT-coded Encounter with no participants |
| `pharmacy_pbm` | MedicationDispense (determinative); known PBM identifier URIs |
| `clinical_lab` | Observation.category = `laboratory` (US Core MUST SUPPORT — declaration, not inference) |
| `payer_exchange` | PDex meta.profile; Provenance with payer agent type |

### Tier B — Manifest/meta.source Required
`clinical_phr`, `pharmacy_specialty`, `clinical_hie`, `clinical_registry`, `case_management`, `disease_management`

**Tier B types defaulting to `unknown` are a Tier 1 governance finding.** The algorithm's inability to classify them proves the metadata management gap.

### SSoR Mapping (NCQA ECDS four categories)
- `clinical_ehr` / `clinical_phr` / `payer_exchange` → `EHR/PHR`
- `administrative_claims` / `administrative_encounter` / `pharmacy_*` → `Administrative`
- `clinical_lab` / `clinical_hie` / `clinical_registry` → `Clinical Registry/HIE`
- `case_management` / `disease_management` → `Case Management/Disease Management`
- `unknown` → `None` (Tier 1 finding)

---

## Business Client Explanation Guide

### The Calibration Problem (primary pitch)
> *"The audit was calibrated for a 500K-member plan with a claims system and spreadsheet supplemental data. It is not calibrated for a 5M-member payer with a cloud data lakehouse, five upstream vendors, and a FHIR API surface serving Prior Auth and payer-to-payer data exchange simultaneously."*

### The NCQA DCS Gap (secondary pitch)
> *"NCQA certifies the measure logic. NCQA DCS explicitly does not validate your data mapping or accuracy. DQAR fills that gap — validating the five semantic layers between your raw data and your CQL engine, and assessing the MDM maturity and governance policies that determine whether your data quality is sustainable across measurement periods. Without both, you have a precisely executed calculation on ungoverned inputs."*

### Explaining Aidbox to a Business Client
Aidbox is the FHIR-native database that makes the assessment possible. Every health record is stored as structured data in PostgreSQL — the same database technology most enterprise systems already use. This means:
- **SQL queries work directly on clinical data** — no proprietary query language, no vendor black box
- **Every data change is automatically versioned and auditable** — every write to the system creates an audit record satisfying HIPAA requirements
- **The plan owns the data** — when Aidbox is deployed as Path C (plan-owned instance), the plan's FHIR infrastructure, data governance, and CQL engine live at the plan, not at the vendor
- **Engine-agnostic CQL execution** — the FHIR server is the single source of truth; CQL engines (HEDIS dQMs, ACC cardiology, ACS oncology, CMS value-based care) are consumers. Multiple measure frameworks can run against the same data simultaneously

### Questions a CDO Should Ask Their HEDIS Vendor
1. *"When ACC publishes their cardiology CQL library, how quickly can we run it against our data? What does that cost?"*
2. *"Can we query our FHIR data directly with our own SQL tools, independent of your reporting engine?"*
3. *"What is your upgrade path when NCQA changes US Core profile requirements between MP2025 and MP2029?"*
4. *"Who owns the AuditEvent provenance metadata on our FHIR resources — us or you?"*
5. *"When the P2P exchange goes live in January, who validates that incoming data before it enters our pipeline?"*

No incumbent HEDIS vendor (Inovalon, Cotiviti) has satisfactory answers to all five.

---

## Regulatory Timeline — Key Deadlines

| Deadline | Event |
|---|---|
| MY2025 | 19 HEDIS measures reportable via ECDS |
| **Jan 1, 2027** | **CMS-0057-F: Patient Access, Provider Access, and P2P APIs required** |
| MY2029 | **NCQA transitions all Hybrid-method measures to mandatory ECDS reporting** |

The MP2029 ECDS cliff is the primary buying trigger for UC1. Jan 1, 2027 P2P deadline is the primary buying trigger for UC3.

---

## Technology Stack

- **Language:** Python (pyproject.toml present)
- **FHIR server:** Aidbox (Health Samurai) — PostgreSQL + JSONB backend
- **Terminology server:** Termbox (Health Samurai) — $validate-code, $expand, $lookup, $translate
- **Conformance testing:** HAPI FHIR Validator (Rungs 1–2); upgrades to Aidbox validator at Rung 3+
- **Query layer:** SQL on FHIR v2 ViewDefinitions against Aidbox/PostgreSQL
- **Bulk data format:** NDJSON per FHIR Bulk Data Access IG STU2
- **Required conformance target:** US Core 6.1.0

---

## Key Spec Files in This Project

| File | Contents |
|---|---|
| `docs/aidbox-kb.md` | Aidbox platform architecture, APIs, security, SQL on FHIR, MCP tools |
| `specs/dqar-01-framework-summary.md` | Core DQAR thesis, five-level validation, three-tier findings, business positioning |
| `specs/dqar-02-health-samurai-guide.md` | Health Samurai product portfolio, AuditEvent capabilities, honest assessment of what HS provides vs. what requires implementation |
| `specs/dqar-03-use-case-index.md` | Three active use cases, platform ladder, revenue model, project architecture |
| `specs/dqar-04-lineage-studies-methodology.md` | Lineage topology, sampling methodology |
| `specs/dqar-05-source-inference-algorithm.md` | Full inference algorithm, Tier A/B vocabulary, SSoR mapping rules |
| `specs/DQAR_Bulk_FHIR_Extract_Specification_v2_0.md` | Client-facing extract specification, six-stage pipeline, anonymization protocol, resource table |

---

## Development Principles

- **PHI never enters Indicina infrastructure** unless Path C (plan-owned Aidbox, post BAA). Stage 1 always runs client-side.
- **Every resource and its AuditEvent must be posted as a single atomic transaction bundle** — no separate writes.
- **Assessment phase is vendor-neutral** — Aidbox and Termbox are named in the roadmap phase, not the assessment findings.
- **Conformance testing ≠ semantic validation.** Stage 1 (conformance testing) answers structural questions. Levels 3–5 (semantic validation) answer clinical meaning questions. Keep the distinction sharp in both code and client communication.
- **HAPI Validator is the default for Stage 1c.** Aidbox validator is the upgrade at Rung 3+. Don't assume Aidbox is available at every stage.
- **Source inference drives five AuditEvent extension fields.** When writing ingest code, the inference algorithm output must populate EXT 1, 2, 3, 4, and 5 before the transaction bundle is assembled. EXT 6 (`ingest-pipeline-id`) and EXT 7 (`ol-run-id`) are set by the pipeline orchestrator, not by the inference algorithm.
- **Unknown source-type is a finding, not an error.** The algorithm deliberately surfaces `unknown` — don't suppress it; log it and flag as Tier 1 governance gap in the findings output.

---

## Unanswered Questions — Confirm With Health Samurai

1. Does Aidbox's CQL evaluation engine generate AuditEvents or Provenance resources referencing resources consumed during measure calculation?
2. Does Aidbox support auto-generation of Provenance resources on ingest (companion Provenance on every POST from an external system)?
3. Does Interbox support the typed/testable/modular mapping pattern described at DevDays 2026 ("HL7v2 to FHIR Integration Designed for AI" — Aleksandr Kislitsyn, June 18 2026)?
4. Termbox standalone licensing terms for plans with existing FHIR servers (AWS HealthLake, Azure API for FHIR, HAPI).
