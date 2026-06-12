# DQAR Framework Summary
**Digital Quality Audit Readiness — Indicina**
*Version: June 2026 | Confidential — Internal Reference*

---

## What DQAR Is

The Digital Quality Audit Readiness (DQAR) is Indicina's proprietary methodology for assessing health payer readiness for digital quality reporting. It replaces the manual, PSV-heavy HEDIS compliance audit paradigm with a FHIR-native, automated, standards-conformant, and semantically rigorous assessment framework.

**Indicina's position:** Advisory and consulting only. Indicina does not pursue NCQA audit certification and does not act as a certified HEDIS auditor. The DQAR is a pre-audit readiness and digital transformation advisory service, complementary to — not competitive with — certified HEDIS auditors.

---

## The Core Thesis

Most U.S. health payers have:
- A FHIR surface that passes structural validation ✅
- A data lakehouse for claims analytics ✅
- **Nothing between those layers that validates whether clinical data feeding HEDIS measure execution actually means what the measure specification requires** ❌

This semantic validation gap is the primary locus of HEDIS audit failure and digital measure readiness risk.

### The Calibration Problem — Primary Marketing Pitch

> *"A one-week IS assessment with staff interviews and system demonstrations cannot assess this complexity. The audit was calibrated for a 500,000-member commercial plan with a claims system and a spreadsheet-based supplemental data process. It is not calibrated for a 5-million-member multi-product payer with a cloud data lakehouse, five upstream data vendors, and a FHIR API surface serving Prior Auth and payer-to-payer data exchange simultaneously."*

Condensed version:
> *"The audit was calibrated for a 500K-member plan with a claims system and spreadsheet supplemental data. It is not calibrated for a 5M-member payer with a cloud data lakehouse, five upstream vendors, and a FHIR API surface serving Prior Auth and payer-to-payer data exchange simultaneously."*

### The NCQA DCS Positioning — Secondary Marketing Pitch

> *"NCQA certifies that the measure logic is correct. NCQA's Digital Content Services explicitly does not validate your data mapping or accuracy. DQAR fills that gap — validating the five semantic layers between your raw payer data and your CQL engine, and assessing the MDM maturity, metadata management capability, and data governance policies that determine whether your data quality is sustainable across measure years. Without both, you have a precisely executed calculation on ungoverned inputs."*

**Source:** NCQA Digital Content Services Customer Handbook (April 2025): *"Successful Implementation confirms that Licensee successfully installed the Digital Content Services Application or Licensee Engine, and the Measures. It does not confirm the Licensee's data mapping, data accuracy or implementation of the NCQA FHIR IG."*

This is not a weakness in NCQA DCS — it is a deliberate scope boundary. NCQA is a measure standards body, not a data operations company. DQAR fills the upstream gap DCS explicitly does not cover.

---

## The Three-Tier Findings Structure

Every DQAR engagement produces findings organized into three tiers. This is the competitive differentiator — no certified HEDIS auditor produces all three.

| Tier | Name | Definition | Example |
|---|---|---|---|
| 1 | Compliance gap | Deviation from current Vol. 5 audit standards | ETL rule modified post-lock with no change record |
| 2 | Measure data gap | Data quality failure affecting measure rates | Value set binding using retired NDC codes in 3 drug measures |
| 3 | Digital readiness gap | Capability gap relative to MY2029 ECDS mandatory reporting | No AuditEvent logging on FHIR server; lineage graph terminates at lakehouse boundary |

Tier 3 findings are invisible to the current HEDIS audit. They represent the DQAR's primary competitive moat.

Every finding carries two dimensions:
- **Technical severity** — what is broken now and what is the measure rate impact
- **Governance root cause** — why it broke and whether the organization has the capability to prevent recurrence

Without the governance dimension, findings produce one-time fixes. With it, findings produce structural remediations — which is what a CDO needs.

---

## The Assessment Framework — Two Parallel Tracks

### Track A — Five-Level Semantic Validation (Technical)

Assesses what the data *is* right now. Point-in-time. Executable against a Bulk FHIR extract in the Aidbox assessment sandbox.

**Level 1 — Terminology conformance**
Is the code in the correct NCQA-published value set for the correct measurement year?
- Tool: Termbox + VSD conformance testing
- Answers: "is this code valid for this measure?"
- Does NOT answer: "is this code being used correctly in this clinical context?"

**Level 2 — Resource structural conformance**
Is the FHIR resource correctly structured per US Core and QI Core profiles? Is the code in the right field?
- Tool: HAPI FHIR Validator
- Answers: "is this resource well-formed per the IG?"
- Does NOT answer: "does this resource represent the right clinical event for this measure?"

**Level 3 — Context conformance** (measure logic awareness required)
Is the resource type correct? Is the encounter type constraint enforced? Does the resource date fall within the measurement period?
- Tool: SQL on FHIR v2 ViewDefinition queries against Aidbox/Postgres
- Answers: "is this resource being used in the right clinical context for this measure?"
- Requires: knowledge of the HEDIS measure specification, not just the value set

**Level 4 — Clinical plausibility**
Does the data make physiological and logical sense?
- Tool: PIQI-style plausibility rules as SQL checks
- Checks: HbA1c values outside physiological range, encounter dates predating enrollment, diagnosis codes inconsistent with age or sex, lab results without performing organization
- Answers: "is this data clinically believable?"

**Level 5 — Population-level semantic coherence**
Is the distribution of codes across the population plausible? Are there systematic anomalies suggesting pipeline failures rather than clinical patterns?
- Tool: scikit-learn/PyOD anomaly detection (Isolation Forest, DBSCAN, One-Class SVM)
- Checks: sudden code frequency spikes, zero clinical records from high-volume PCPs, implausible population-level distributions
- Note: requires sufficient population volume — most meaningful in continuous monitoring (UC3) rather than sample-based assessment (UC1/UC2)

**Important:** Terminology conformance (Level 1) alone does not constitute semantic validation. All five levels are required. A plan can have 100% VSD conformance and produce completely wrong measure rates if Levels 2–5 are broken.

---

### Track B — Level 6 Governance and Management Capability (Organizational)

Assesses whether the organization can *sustain* data quality over time. Assessed through structured interviews, documentation review, and artifact inspection — not executable against data. Uses a 1–4 maturity rubric.

**MDM Maturity**

Three master data domains directly affect HEDIS measure rates:

*Member MDM* — identity resolution across enrollment sources, retroactive disenrollment handling, product-line transitions. Failures corrupt denominator completeness. Assess: is there a governed member identity matching process connected to HEDIS eligible population logic? Are enrollment edge cases handled by a governed rule set or ad hoc?

*Provider MDM* — provider specialty, network status, TIN-to-NPI mapping, attribution logic. Failures corrupt provider-attributed denominators and clinical data completeness by provider. Assess: is the provider directory governed against NPPES? Is specialty mapping version-controlled?

*Terminology MDM* — SNOMED, LOINC, RxNorm, NDC bindings governed at platform level or per-application? Is the VSD refresh an annual governed process with a documented owner and change control record?

**Metadata Management Maturity**

Does a data catalog exist (Collibra, Alation, dbt docs) covering HEDIS-relevant data assets? Does it reach the FHIR pipeline or only the BI/reporting layer?

Are transformation rules documented at field level? System-level descriptions ("claims flow from CAPS to EDW") are not field-level lineage ("diagnosis code in EDW.claim_line.diag_cd_1 sourced from CAPS.transaction.icd_diag_1, no transformation applied").

Is there a data dictionary mapping HEDIS data elements to source fields? Without this, semantic validation findings cannot be remediated — the plan doesn't know which upstream field to fix.

**Data Governance Policy Maturity**

Is there a data governance function — council, CDO, or equivalent — with authority over data quality standards across HEDIS-relevant systems? Or is quality governance fragmented by application owner?

Are there documented data quality SLAs for HEDIS-relevant data feeds? Vendor contractual obligations for conformant LOINC codes, latency SLAs for EHR feeds?

Is there a year-round change control process for ETL rules, value set bindings, and measure logic? Absence of post-lock change documentation is a common Vol. 5 finding — the deeper problem is absence of year-round change governance.

**Maturity Rubric — DAMA-DMBOK Anchored, CMMI-DMM Structured**

The DQAR Level 6 maturity rubric uses the CMMI-DMM five-level progression as its structural backbone and is grounded in DAMA-DMBOK knowledge areas for data governance, MDM, metadata management, data quality, and data operations. It is calibrated specifically for payer HEDIS pipeline operations — not generic enterprise data management. This is Indicina proprietary IP with no licensing dependency on CMMI Institute (now merged with ISACA) or any other licensed framework.

DAMA-DMBOK provides the knowledge area taxonomy your CDO buyers already know. CMMI-DMM provides the maturity ladder structure. DQAR operationalizes both for the specific failure modes, tools, and regulatory deadlines of payer HEDIS operations.

Five DAMA-DMBOK knowledge areas assessed per engagement:

| CMMI-DMM Level | Plain language (DQAR) | Typical plan finding |
|---|---|---|
| 1 — Initial | Ad hoc — no documented processes, tribal knowledge | Most plans at score 1 on metadata, many at 1 on MDM |
| 2 — Repeatable | Reactive — processes exist for some areas, not enterprise-governed | Common for governance where HEDIS team has processes but no CDO authority |
| 3 — Defined | Governed — documented, standardized, applied consistently across HEDIS pipeline | MY2029 readiness floor |
| 4 — Managed | Measured — quality metrics tracked, SLAs in place, vendor accountability | Where leading payers with strong CDO functions are |
| 5 — Optimizing | Continuous improvement — quality embedded in pipeline, automated monitoring | Future state — UC2 monitoring service enables this level |

Most plans assessed will score 1–2 across MDM and metadata, 2–3 on governance. Level 3 is the MY2029 readiness floor. The UC2 monitoring subscription tracks maturity progression toward Level 3 each quarter.

**Note:** DAMA-DMBOK reference slides will be uploaded to the DQAR Shared KB project to anchor rubric development. Do not author the detailed rubric until DAMA materials are available in the project KB.

---

## The Six DQAR Audit Domains

### Domain 1 — IS Assessment
Evaluates payer information system capabilities: system inventory, EDI transaction handling, FHIR server provenance, access controls, and change management. The current Vol. 5 IS Assessment accepts narrative descriptions and staff interviews. The DQAR requires machine-readable artifacts.

### Domain 2 — Value Set Conformance and Currency
Highest-yield domain. Most plans have stale value set bindings. Key procedures:
- VSD currency check against NCQA MY2025 (369 value sets, 179,831 codes, 15 code systems)
- NDC Medication List Directory currency
- SNOMED/LOINC/ICD-10 cross-mapping audit (Level 1–3 combined)
- Terminology drift detection (MY2024 → MY2025 retirements)

**VSD conformance template — three modes:**
- Mode 1: API reference — client's Termbox/FHIR terminology server, Indicina read-only scoped access
- Mode 2: Client-provided export — client's licensed VSD loaded to assessment sandbox, deleted at engagement close per SOW
- Mode 3: JSON value sets from client's dQM package — FHIR ValueSet resources included in licensed DCS package, loaded directly to Termbox; covers ECDS measures only; no Excel parsing required

**NCQA DCS JSON value sets:** For the 19 ECDS-eligible MY2025 measures, NCQA distributes value sets as JSON FHIR ValueSet resources within the dQM package. Pricing not publicly listed — contact NCQA Account Executive. The dQM Evaluation Package is likely the appropriate tier for assessment/testing purposes.

### Domain 3 — Data Lineage Tracing
For each HEDIS measure:
```
source field → transformation rule → intermediate table → analytic field → measure flag
```
Plans without dbt or equivalent lineage tooling cannot produce this documentation. Absence of traceable lineage is itself a material finding.

### Domain 4 — Semantic Validation
The highest unmet demand in the market. Corresponds to Levels 3–4 of the semantic validation framework. Key procedures:
- Code-in-context validation (encounter type constraints)
- Negation and exception code audit
- Clinical plausibility checks
- ECDS data source attribution verification

### Domain 5 — Population Completeness

**PIQI Framework integration:** Domain 5 is operationalized using the PIQI (Patient Information Quality Improvement) framework dimensions. PIQI is explicitly cited in the foundational DQAR article as a required framework for the next-generation audit. The four PIQI dimensions map directly to Domain 5 procedures:

- **Usability** -- 834 enrollment reconciliation. Is the full eligible population present in the FHIR pipeline? Gap between 834 member count and FHIR Patient/Coverage count is a PIQI usability failure.
- **Plausibility** -- Continuous enrollment logic audit. Enrollment periods, gaps, retroactive disenrollment, product-line transitions. Demographic constraint consistency (age, sex, product line) across resources.
- **Comparability** -- Clinical data completeness by provider. Contribution rate consistency across high-volume PCPs. A provider with high attribution and zero clinical records is a PIQI comparability failure -- systematic completeness gap affecting every ECDS measure denominator.
- **Stability** -- Population-level anomaly detection (Level 5). Unexpected shifts in denominator size, exclusion rate, attribution patterns, feed volume per source-feed-id. Implemented via scikit-learn/PyOD (Isolation Forest, DBSCAN, One-Class SVM). Apply per source-feed-id, not globally -- multi-vendor pipelines have different baselines per feed.

**PIQI limitations for DQAR:** Stability checks require per-feed baselines, not global baselines. Comparability checks require concept-level comparison via Termbox value set mapping where multiple code systems represent the same clinical concept across feeds.

### Domain 6 — ECDS and dQM Readiness
Forward-looking domain:
- CQL library version verification against NCQA-released packages
- Parallel hybrid/ECDS reconciliation
- FHIR pipeline completeness by measure
- Data source attribution for all ECDS measures

---

## Regulatory Timeline

| Milestone | Detail | Source |
|---|---|---|
| MY2025 | 19 HEDIS measures reportable via ECDS | NCQA Vol. 2 MY2025 |
| MY2026 | SSoR reporting no longer required for ECDS; NCQA exploring provenance evaluation methods | NCQA KB (verify against current Vol. 2) |
| MY2029 | All Hybrid-method measures transition to ECDS mandatory reporting | NCQA Vol. 2 MY2025 |
| Jan 1, 2027 | CMS-0057-F: Patient Access, Provider Access, Payer-to-Payer APIs required | CMS Final Rule |

**Note:** MY2026 and MY2029 milestones sourced from prior Claude session — verify against current NCQA Vol. 2 MY2025 before client-facing use.

---

## AuditEvent Provenance Architecture

### The Minimum Viable Provenance Pattern
Extend the standard FHIR AuditEvent at ingest time with four fields. Written once per resource, at write time, by the pipeline.

```json
"extension": [
  { "url": "http://indicina.com/fhir/ext/source-type", "valueCode": "ehr-clinical" },
  { "url": "http://indicina.com/fhir/ext/source-system-id", "valueString": "epic-prod-org-447" },
  { "url": "http://indicina.com/fhir/ext/hedis-source-declaration", "valueCode": "ecds-ehr" },
  { "url": "http://indicina.com/fhir/ext/ingest-pipeline-id", "valueString": "interbox-job-20251014-ehr-001" }
]
```

`hedis-source-declaration` maps to ECDS source type vocabulary: `ecds-ehr`, `ecds-administrative`, `ecds-lab`, `ecds-pharmacy`.

### Measure Attribution Join
```
member flag → resource ID → AuditEvent.entity.reference → hedis-source-declaration + source-system-id
```

### What AuditEvent Logging Is and Is Not
- ✅ Closes HIPAA audit control gap (45 CFR §164.312(b))
- ✅ Establishes FHIR server transaction log baseline
- ✅ Provides write-time source attribution for ingest pipeline resources
- ❌ Not a current CMS or NCQA mandate
- ❌ Does not automatically provide measure-level execution provenance
- ❌ Does not cover resources created outside the managed ingest pipeline

**Regulatory status:** No specific CMS or NCQA mandate requires AuditEvent logging today. Position as Digital Readiness Gap (Tier 3), not Compliance Gap (Tier 1).

---

## Industry Dialogue — Semantic Validation

**LinkedIn exchange with Jeff Helman (AEGIS), June 2026:**

Michael E. Campbell: *"Clearly Layers 1 and 2 can be validated against base FHIR or IG schemas. Do you envision the same approach for 3 and 4 (i.e., the national or state agency or organization creates an IG specific to their requirements) for conformance validation? Is there a better way than making more IGs?"*

Jeff Helman response: AEGIS directly supports and validates all FHIR IGs named in the CMS-0057-F Final Rule. This confirms IG-based validation covers the regulatory compliance surface (Levels 1–2) but not the measure-specific semantic layer (Levels 3–5). The "better way than making more IGs" answer DQAR proposes: computable data quality rules implemented at multiple lineage checkpoints.

Michael E. Campbell follow-up: *"This is a critical opportunity to implement layered computable data quality validations on multiple points of the data lineage. In my opinion, an under-appreciated feature of open source standards like FHIR is that it establishes a shared but [truncated — retrieve full text]."*

**Note:** Retrieve full text of truncated reply and add here. This is a primary source articulation of the DQAR thesis in industry dialogue.

---

## Industry Case Study — UCare Collapse (2025)

**Source:** John Hoff, MTR Group, LinkedIn, June 2026. "The UCare Collapse Was Fully Visible Before It Happened."

UCare (Minnesota) absorbed a ~20% enrollment increase of displaced UnitedHealthcare/Humana members during AEP 2024 network disruption. The receiving plan had inadequate risk data on the transitioning population. 2025 results: MA loss $263M, Medicaid loss $315M, total $504M. Reserves exhausted.

**Tom Shankle's observation (Healthcare Strategy and Operations):** If the CMS-0057-F Payer-to-Payer data exchange mandate had been in place in 2024, UCare would have received five years of clinical history on those transitioning members — potentially changing the risk assessment and avoiding the financial collapse.

**Michael E. Campbell's reply:** *"Any strategic advantage on payer to payer exchange depends on several data concerns. How complete is the payer data — most clinical data is left out of FHIR by default and most plans don't use FHIR data for analytics. It's still treated as a data source incompatible with legacy analytic platforms. A plan with FHIR native architecture, broad scope of included data, and SQL on FHIR or similar analytic environments can leverage that data while others leave it siloed."*

**DQAR implication for UC5:** The UCare case is the concrete financial consequence of P2P data quality failure. The data was theoretically available. The capability to assess and use it was not. UC5 (Payer-to-Payer Data Exchange Quality) addresses exactly this gap: assessing whether incoming P2P data is complete, semantically valid, and analytically usable — before it enters the risk and quality pipelines.

**Pitch for UC5:** *"UCare received an enrollment cascade they couldn't risk-assess because their analytics infrastructure couldn't leverage the clinical data that was theoretically available. A plan with FHIR-native architecture, governed P2P data quality assessment, and SQL on FHIR analytics turns that data into a competitive advantage. Without it, five years of clinical history on transitioning members sits siloed and unused while the losses accumulate."*

---

## Industry Pain Points (Strategic Context)

- Annual HEDIS reporting requires "redundant, idiosyncratic, annual hard coding" of measures and manual chart abstractions
- CAQH estimates shifting from manual to automated quality workflows could save payers and providers ~$20 billion annually
- Health plans choose and pay their own certified auditor — structural conflict of interest analogous to pre-Sarbanes-Oxley corporate auditing
- Plans eager for anything that makes their data defensible before an auditor arrives
- Direct public criticism of HEDIS auditors suppressed by regulatory stakes (star ratings, CMS bonuses)
- NCQA DCS explicitly disclaims data mapping and accuracy validation — the upstream gap is unowned and unaddressed in the current vendor landscape
