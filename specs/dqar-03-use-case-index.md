# DQAR Use Case Index
**Indicina Consulting Business — Three Active Use Cases**
*Version: June 2026 v2 | Confidential — Internal Reference*

---

## Governing Decisions

**Indicina will not pursue NCQA audit certification.**
Certifying against Vol. 5 — the framework DQAR argues is inadequate — creates a credibility conflict. Staying advisory means Indicina is never competitive with certified auditors, is free to assess dimensions Vol. 5 doesn't cover, and is not tied to the HEDIS calendar.

**All use cases are advisory and consulting services, not certification services.**

**The core value proposition:**
NCQA certifies that the measure logic executes correctly. NCQA DCS explicitly does not validate data mapping or accuracy. DQAR fills that gap — validating the five semantic layers between raw payer data and the CQL engine, and assessing the MDM maturity, metadata management capability, and data governance policies that determine whether data quality is sustainable across measure years.

*Someone else certifies the plumbing. Indicina certifies the water.*

**Level 6 governance maturity rubric:** Indicina's proprietary DQAR maturity rubric is structured using the CMMI-DMM five-level progression (Initial → Repeatable → Defined → Managed → Optimized) and grounded in the DAMA-DMBOK knowledge areas for data governance, MDM, metadata management, data quality, and data operations. It is calibrated specifically for payer HEDIS pipeline operations — more actionable than either generic model because it names the specific failure modes, tools, and regulatory deadlines relevant to the buyer. This is Indicina IP with no licensing dependency. DAMA-DMBOK slides and reference material will be uploaded to the DQAR Shared KB project to anchor the rubric development.

---

## Active Use Case Map

| # | Name | Buying trigger | Engagement type | Health Samurai |
|---|---|---|---|---|
| UC1 | Digital Measure Readiness Assessment | MY2029 ECDS cliff; plan doesn't know where they stand | Fixed-fee assessment | Aidbox, Termbox |
| UC2 | Digital Quality Data Operations Monitoring | Plan wants continuous visibility into data quality drift | Recurring subscription | Aidbox, Termbox |
| UC3 | Payer-to-Payer Data Exchange Quality | P2P exchange live or imminent; incoming data quality unknown | Fixed-fee assessment | Aidbox, Termbox |

## Deferred to Phase 2

| # | Name | Rationale for deferral |
|---|---|---|
| — | Pre-Audit Digital Readiness Preparation | Requires deep Vol. 5 compliance knowledge and certified auditor ecosystem relationships not yet established. Phase 2 once UC1 generates client credibility. |
| — | CMS Interoperability Compliance Readiness | Different buyer (CIO/technology vs. CDO/quality), different regulatory surface, Payerbox partner relationship not yet formalized. Phase 2 once Health Samurai partnership matures. |

---

## UC1 — Digital Measure Readiness Assessment

**What it is:** A structured assessment of a plan's readiness for ECDS mandatory reporting. Anonymized Bulk FHIR extract loaded into an Aidbox sandbox. Both assessment tracks run in parallel: five-level semantic validation (Track A) and Level 6 governance capability assessment (Track B using DQAR maturity rubric).

**Pitch:** *"NCQA DCS certifies your engine runs correctly. We assess whether the data going into it is semantically trustworthy — the right codes, in the right resources, in the right clinical context, with plausible values, governed by processes that will keep them right next year."*

**Buying trigger:** Plan leadership aware of MY2029 ECDS mandatory reporting deadline without a clear picture of current digital measure infrastructure gaps. Often triggered by new VP of Quality, CIO initiative, or vendor pitch surfacing the issue.

**Buyer:** VP of Quality, Chief Data Officer, VP of Analytics.

**Deliverable:** Three-tier DQAR findings report organized by semantic level and governance sub-domain. Each finding carries technical severity AND governance root cause AND DAMA-DMBOK-anchored maturity score. Prioritized remediation roadmap sequenced against MY2026 and MY2029 milestones.

**Engagement structure:**
- Client provides feed manifest (engagement kickoff) declaring all source system feeds
- Client provides anonymized Bulk FHIR export (ndjson via `$export`) + VSD access (Mode 1, 2, or 3)
- Client runs Indicina-provided validation kit on own infrastructure — PHI never leaves client environment:
  - Stage 1a: NDJSON structural validation
  - Stage 1b: Resource conformance ($validate — base FHIR R4 + US Core 6.1.0, classified by layer)
  - Stage 1c: Bulk FHIR API protocol conformance ($export async protocol + manifest)
- Anonymized extract + three conformance reports delivered to Indicina
- Indicina loads to Aidbox sandbox with AuditEvent + six extension metadata fields generated atomically
- Level 6 governance assessment via structured interviews and documentation review
- Findings report and roadmap delivered

**Level 6 assessment scope (DAMA-DMBOK knowledge areas):**
- Data Governance — change control authority, ownership, enforcement
- Master Data Management — member, provider, terminology MDM
- Metadata Management — data catalog coverage, field-level lineage, VSD governance
- Data Quality — proactive standards vs. reactive remediation
- Data Operations — ETL governance, vendor SLAs, pipeline change management

**PIQI integration — Domain 5 (Population Completeness):**
PIQI framework dimensions map directly to Domain 5 procedures: Usability → 834 enrollment reconciliation; Plausibility → continuous enrollment logic audit; Comparability → clinical data completeness by provider; Stability → population-level anomaly detection (Level 5, scikit-learn/PyOD).

**Technical implementation:** UC1 Assessment App — `dqar-06-uc1-app-technical-specification.md`
**Built with:** Claude Code + Health Samurai (Aidbox + Termbox)
**Framework linkage:** Implements DQAR Domains 2, 3, 6. Full framework in DQAR Shared KB.
**Inference algorithm:** `dqar-05-source-inference-algorithm.md` — Priority 1–4 deterministic, Priority 5 probabilistic classifier (heuristic — findings based on Priority 5 must be qualified accordingly), Priority 6 circumstantial.

**Revenue model:** Fixed-fee. Standalone — does not require plan to adopt any vendor platform.

**Downstream opportunity:** Level 6 governance findings create qualified leads for UC2 (monitoring). Value set drift findings create Termbox referrals. Feed manifest gaps create data governance advisory leads.

---

## UC2 — Digital Quality Data Operations Monitoring

**What it is:** A recurring subscription service providing continuous DQAR conformance monitoring against the plan's FHIR pipeline. Runs Track A Levels 1–3 on a scheduled cadence, reassesses Level 6 governance maturity every six months, produces quarterly findings scorecard with drift detection and trending. Indicina sells the conformance testing methodology and monitoring cadence — the plan owns the terminology data and pipeline infrastructure.

**Pitch:** *"Data quality is continuous. The audit is annual. By the time audit season reveals a value set drift or semantic failure, the problem has been affecting your rates for months. Continuous monitoring catches it in real time — and tracks your governance maturity improvement toward MY2029 readiness."*

**Buying trigger:** One of three triggers:
1. UC1 findings identified Level 6 governance gaps — plan wants ongoing monitoring during remediation
2. Plan has had measure rate anomalies they couldn't explain — reactive quality improvement
3. Plan is preparing for ECDS mandatory reporting and wants continuous conformance visibility

**Buyer:** VP of Quality, VP of Analytics, or Chief Data Officer. Typically a follow-on from a UC1 engagement.

**Deliverable:** Quarterly digital quality scorecard:
- RAG status per semantic level (1–5) and governance sub-domain
- Drift detection — conformance changes since prior quarter
- Maturity progression — DAMA-DMBOK-anchored score movement toward Level 3 (MY2029 floor)
- Anomaly alerts between scheduled reviews (Level 5 population coherence failures)
- Annual VSD refresh validation at measurement year rollover

**VSD model:** Client holds the NCQA license. Indicina holds the conformance test suite and monitoring methodology. Client runs Termbox instance or provides annual VSD export per SOW.

**Monitoring cadence:**
- Track A Levels 1–3: monthly automated conformance run
- Track A Levels 4–5: quarterly (population-level anomaly detection requires sufficient volume)
- Level 6 governance reassessment: semi-annual structured review
- VSD currency check: at NCQA MY release + 30 days

**CMMI-DMM progression narrative:** The UC1 engagement establishes the baseline maturity scores per DAMA-DMBOK knowledge area. UC2 tracks movement up the five-level scale each quarter. Most plans assessed at 1–2 across MDM and metadata. Level 3 is the MY2029 readiness floor — UC2 provides the roadmap and evidence of progress.

**Revenue model:** Annual subscription. Most defensible recurring revenue — VSD changes every year, monitoring need is continuous, maturity improvement is multi-year. Requires prior UC1 engagement as baseline.

**Health Samurai role:** Termbox as client-hosted or Indicina-sandbox terminology server. Aidbox for any in-engagement data loading.

---

## UC3 — Payer-to-Payer Data Exchange Quality

**What it is:** Assessment of the quality of clinical and claims data *received* via Payer-to-Payer API exchange before it enters the receiving plan's FHIR pipeline and affects HEDIS denominators, HCC risk scores, or member economics. The defining characteristic: the receiving plan did not generate this data and cannot control its quality — but they are liable for decisions made from it.

**Pitch:** *"CMS gives you the pipe. UC3 tells you what's actually flowing through it. UCare received an enrollment cascade they couldn't risk-assess because their analytics infrastructure couldn't leverage the clinical data that was theoretically available. A plan with FHIR-native architecture, governed P2P data quality assessment, and SQL on FHIR analytics turns that data into a competitive advantage. Without it, five years of clinical history on transitioning members sits siloed and unused while the losses accumulate."*

**Case study:** UCare (Minnesota) 2025 collapse. ~20% enrollment increase from displaced UnitedHealthcare/Humana members during AEP 2024. Inadequate risk data on transitioning population. Total losses: $504M. The data was theoretically available via P2P exchange. The capability to assess and use it was not. Source: John Hoff, MTR Group, LinkedIn June 2026.

**Regulatory anchor:** CMS-0057-F Payer-to-Payer API mandatory by January 1, 2027.

**Buying trigger:** Plan implementing P2P data exchange and analytics team concerned about incoming data quality. Or plan notices HEDIS denominator or HCC anomalies after P2P exchange goes live.

**Buyer:** VP of Analytics, Chief Data Officer, VP of Quality. Most technically sophisticated buyer in the portfolio.

---

### P2P Format Stack — Critical for UC3 Scope

P2P data received under CMS-0057-F arrives in a three-layer format stack:

**Layer 1 — Transport: Bulk FHIR (mandatory)**
Bulk Payer-to-Payer exchange SHALL use FHIR Bulk Data Access IG STU2 (2.0.0) asynchronous semantics. Same ndjson transport as UC1. Stage 1a structural validation and Stage 1c protocol conformance checks apply.

**Layer 2 — Content: US Core 3.1.1 OR 6.1.0 (both possible)**
CMS-0057-F requires support for USCDI v1 (US Core 3.1.1) and USCDI v3 (US Core 6.1.0). A sending payer on the original CMS-9115 (2021) implementation may be sending 3.1.1-vintage resources. A sending payer on a forward-compliant implementation sends 6.1.0. The receiving plan has no control over which version arrives.

**Layer 3 — Profile: Da Vinci PDex (recommended, not required)**
CMS recommends PDex IG for provenance support. PDex-conformant senders include Provenance resources with transmitted data — this inverts the UC1 inference challenge. A UC3 assessment that finds PDex Provenance in incoming data should flag this as a positive — the sending payer is ahead of most internal pipelines on provenance implementation.

**What's included:** Up to 5 years of claims, encounters, USCDI data elements, and prior auth history. Member consent (Consent resource) required for opt-in.

---

### The Version Gap — The Built-In Quality Risk

This is the commercially defining insight for UC3. The version gap between US Core 3.1.1 and 6.1.0 is not a technical edge case — it is a structural problem baked into the current regulatory framework affecting every receiving plan today.

**Why it exists:** CMS-9115-F (2020) required Patient Access API on US Core 3.1.1 / USCDI v1. CMS-0057-F (2024) upgraded to US Core 6.1.0 for new APIs including P2P. CMS did not require existing 3.1.1 implementations to upgrade before the P2P deadline. A plan that built FHIR infrastructure in 2021 on 3.1.1 is still compliant with their original mandate — and will send 3.1.1 data through P2P starting Jan 1 2027.

**HEDIS-relevant delta between 3.1.1 and 6.1.0:**

| Element | 3.1.1 status | 6.1.0 status | HEDIS impact |
|---|---|---|---|
| `Encounter.type` | Present, not MUST SUPPORT | MUST SUPPORT | CBP, CDC, FUH/FUM encounter type constraints fail without it |
| `Observation.category` | Present, not consistently required | MUST SUPPORT per profile | Source-type inference drops to medium/low confidence |
| `DiagnosticReport` | Single profile | Split lab/clinical note profiles | Wrong profile selected, false validation errors |
| `Observation` (blood pressure) | Less constrained | Tightly constrained component structure + UCUM units | CBP numerator validation failures |
| `MedicationRequest.dosageInstruction` | Optional | MUST SUPPORT | Medication adherence measure gaps |
| `Patient.race/ethnicity` | US Core extensions | USCDI v3 restructured elements | Demographic constraint application failures |

**Three-pass validation for UC3:**

This is the methodology that makes UC3 findings actionable rather than a list of undifferentiated errors:

```
Pass 1 — Base FHIR R4 structural validation
  Errors = genuine structural failures
  Finding: Sending payer implementation quality problem
  Owner: Request retransmission / raise data quality SLA

Pass 2 — US Core 3.1.1 conformance
  New errors vs Pass 1 = 3.1.1 non-conformance
  Finding: Sending payer quality failure against their own standard
  Owner: Request retransmission / raise data quality SLA

Pass 3 — US Core 6.1.0 conformance
  New errors vs Pass 2 = version gap artifacts
  Finding: Regulatory transition mismatch — NOT sending payer's fault
  Owner: Receiving plan must implement version normalization on ingest
```

**Error classification table:**

| Error pattern | Classification | Action |
|---|---|---|
| Pass 1 only | Structural failure | Request retransmission from sending payer |
| Pass 1 + 2 | 3.1.1 non-conformance | Raise data quality SLA with sending payer |
| Pass 3 only | Version gap artifact | Implement receiving-plan normalization |
| Pass 2 + 3 | Genuine data quality problem | Investigate regardless of version |

**Version detection before validation:**

Before running passes, detect which US Core version each incoming feed is using:
1. `meta.profile` declarations on resources — most reliable if populated
2. `GET [sending-payer-base]/metadata` CapabilityStatement — query before bulk export, add version to feed manifest
3. Structural fingerprinting — presence/absence of 6.1.0-specific MUST SUPPORT elements in a resource sample

Grouping incoming resources by `source-feed-id` (AuditEvent extension) and detecting US Core version per feed turns a chaotic multi-sender validation problem into a structured per-sender quality assessment.

---

### UC3 Deliverable

**Incoming P2P data quality assessment** covering all five semantic levels applied to *received* data:

- Stage 1a: NDJSON structural validation
- Stage 1b: Resource conformance — three-pass version-aware ($validate: base FHIR R4 → US Core 3.1.1 → US Core 6.1.0 delta classification)
- Stage 1c: Bulk FHIR API protocol conformance ($export async protocol + manifest)
- Level 3: Measure context constraint validation against receiving plan's HEDIS measures
- Level 4: Clinical plausibility of received data
- Level 5: Population completeness — all expected members and historical records arriving?
- Level 6 (receiving plan): Governance assessment of P2P ingest process — is received data governed before entering the pipeline?
- Consent resource validity check — FHIR Consent resources documenting member opt-in
- Provenance coverage — PDex Provenance resources present? If so, flag as positive; if absent, document gap

**Recommendation per feed:** accept as-is | transform on ingest | reject and request retransmission

**Per-sender quality scorecard:** Each sending payer's data assessed separately. Version vintage identified. Error classification table applied. Receiving plan knows exactly which senders have quality problems, which have version gaps, and which are clean.

**Key framing from industry dialogue (Michael E. Campbell, LinkedIn, June 2026):** *"Any strategic advantage on payer to payer exchange depends on several data concerns. How complete is the payer data — most clinical data is left out of FHIR by default and most plans don't use FHIR data for analytics. It's still treated as a data source incompatible with legacy analytic platforms. A plan with FHIR native architecture, broad scope of included data, and SQL on FHIR or similar analytic environments can leverage that data while others leave it siloed."*

**Competitive position:** Most forward-looking and least crowded space in the portfolio. Almost no one is providing P2P data quality assessment services. First-mover advantage is meaningful — the Jan 1 2027 deadline creates urgency now.

**Revenue model:** Fixed-fee assessment. Evolves into UC2-style continuous monitoring on the P2P ingest pipeline as P2P exchange volume grows.

**Health Samurai role:** Aidbox as receiving FHIR server sandbox with Termbox validation on ingest. AuditEvent six-extension pattern applied — tag each received resource with P2P sending-plan feed ID at ingest.

**Technical infrastructure:** Shares UC1 pipeline architecture with three additions:
1. Dual-version US Core validation (3.1.1 and 6.1.0) with delta classification
2. Da Vinci PDex profile validation as optional third pass
3. FHIR Consent resource validity check

---

## Engagement Architecture — Three Use Cases

### The Three-Phase Model

**Phase 1 — Assessment (Indicina-led)**
Fixed-fee. Vendor-neutral. DQAR framework applied. Three-tier findings report with semantic level breakdown, version-aware conformance classification (UC3), and DAMA-DMBOK-anchored governance maturity scores. No partner products required at this phase.

**Phase 2 — Roadmap (Indicina-led)**
Prioritized implementation roadmap sequenced against MY2026/MY2029 (UC1) or Jan 1 2027 (UC3). Partner products named — Aidbox, Termbox, Velox — with specific capability gap-to-solution mapping.

**Phase 3 — Implementation (partner-led, Indicina as advisor)**
Health Samurai or other vendor leads. Indicina provides implementation advisory, integration oversight, parallel testing, and roadmap validation.

### Revenue Progression

| Phase | Indicina revenue | Health Samurai revenue |
|---|---|---|
| UC1 Assessment | Fixed-fee | None |
| UC1 Roadmap | Fixed-fee | None |
| UC1 Implementation | Advisory fee | Aidbox + Termbox licensing |
| UC2 Monitoring subscription | Annual subscription | Termbox subscription |
| UC3 Assessment | Fixed-fee | None |
| UC3 → UC2 Monitoring | Annual subscription | Aidbox + Termbox subscription |

### Critical Role Separation

Indicina retains the advisory/audit role permanently. Implementation vendors are the implementation layer. Mixing these roles erodes audit credibility and creates conflict of interest.

---

## Shared Infrastructure — Three Active Use Cases

| Component | UC1 | UC2 | UC3 |
|---|---|---|---|
| DQAR six audit domains | All | Domains 2,3,6 | Domains 2,3,4,5 |
| Five-level semantic validation | Track A | Levels 1-3 scheduled | All five (incoming data) |
| Level 6 DAMA-DMBOK rubric | Full | Semi-annual reassessment | Receiving-plan governance |
| Feed manifest | Required | Ongoing maintenance | Required per sending payer |
| Aidbox sandbox | Assessment | Monitoring | Assessment |
| Termbox VSD | Mode 1/2/3 | Client-hosted / SOW | Mode 1/2/3 |
| AuditEvent six extensions | Full | Scheduled | Full + sending-payer-id |
| Source inference algorithm | Full | Scheduled | Full + version detection |
| SQL on FHIR query library | Five measures | Scheduled | Five measures (incoming) |
| Client validation kit | UC1 standard | Reused | UC3 three-pass version |
| PIQI framework (Domain 5) | Full | Level 5 monthly | Full (incoming data) |
| US Core version detection | 6.1.0 only | 6.1.0 drift | 3.1.1 + 6.1.0 + delta |
| PDex profile validation | Not applicable | Not applicable | Optional third pass |
| Consent resource check | Not applicable | Not applicable | Required |

---

## Project Architecture

### Four-project structure

**Project 1 — DQAR Shared KB** (authoritative framework)
Framework critique, six domains, three-tier findings, five-level semantic validation, Level 6 DAMA-DMBOK maturity rubric, regulatory timeline, Health Samurai partner guide, inference algorithm, lineage studies methodology, PIQI Domain 5 integration, CMMI-DMM level structure. DAMA slides to be uploaded. No application code.

**Project 2 — DQAR UC1 Assessment App** (Claude Code + Health Samurai)
Eight-stage validation pipeline, Aidbox sandbox, SQL on FHIR library, AuditEvent six extensions, source inference, client validation kit, findings report generator. Primary spec: `dqar-06-uc1-app-technical-specification.md`.

**Project 3 — DQAR UC2 Monitoring Service** (advisory + subscription product)
Monitoring cadence design, drift detection methodology, quarterly scorecard format, DAMA-DMBOK maturity progression tracking, VSD refresh service design, subscription commercial model. Reuses UC1 app infrastructure on scheduled cadence.

**Project 4 — DQAR UC3 P2P Exchange Quality** (advisory)
P2P format stack (Bulk FHIR + US Core 3.1.1/6.1.0 + PDex), three-pass version-aware validation methodology, error classification table, version detection methodology, per-sender scorecard design, Consent validity check, UCare case study. Extends UC1 infrastructure with dual-version and PDex validation.

### Cross-project linkage

Every project uploads from DQAR Shared KB:
- `dqar-01-framework-summary.md`
- `dqar-02-health-samurai-partner-guide.md`
- `dqar-03-use-case-index.md` (this file)
- `dqar-04-lineage-studies-methodology.md`
- `dqar-05-source-inference-algorithm.md`

UC1 app and UC3 additionally upload:
- `dqar-06-uc1-app-technical-specification.md`
- `DQAR_Bulk_FHIR_Extract_Specification_v1.0.docx`
