# Five-Level Semantic Validation & PIQI Metrics

Reference for the five levels of FHIR data conformance validation and PIQI quality dimensions.

## Five-Level Validation

### Level 1: Terminology Conformance

**Question:** Is the code in the correct NCQA value set for this measurement period?

**Scope:** Code system and code value

**Tools:**
- Termbox or FHIR terminology server
- NCQA MY2026 value set definitions
- Conformance engine

**What it checks:**
- `coding.system` is correct (e.g., SNOMED vs. ICD10)
- `coding.code` exists in the declared value set
- Code is not retired for this measurement period
- No typos or malformed codes

**What it does NOT check:**
- Whether the code is being used in the right clinical context
- Whether the result makes clinical sense
- Whether the code is correctly mapped from source system

**Pass rate:** Percentage of resources with all codes in valid value sets

**Example failure:** LOINC code `2345-7` (glucose) coded as ICD10 instead of LOINC

---

### Level 2: FHIR Profile Conformance

**Question:** Does the FHIR resource conform to US Core 6.1.0 profile?

**Scope:** FHIR resource structure, cardinality, data types

**Tools:**
- HAPI FHIR Validator
- US Core 6.1.0 StructureDefinition
- Conformance engine

**What it checks:**
- Required fields present (MUST SUPPORT)
- Data types correct
- Cardinality constraints met
- Extension usage valid
- Reference targets exist (when resolvable)

**What it does NOT check:**
- Clinical context (is this the right resource type for this clinical event?)
- Value validity (is the value in a plausible range?)
- Semantic correctness (does the data make clinical sense?)

**Pass rate:** Percentage of resources conforming to profile

**Example failure:** `Observation.effective` is missing or has wrong data type

---

### Level 3: Clinical Context Conformance

**Question:** Is the resource being used in the correct clinical context for this measure?

**Scope:** Encounter type, timing, relationships between resources

**Tools:**
- SQL on FHIR ViewDefinitions
- HEDIS measure specification
- Conformance engine

**What it checks:**
- Encounter type matches measure requirements (e.g., CBP only in office visits)
- Service date falls within measurement period
- Resource date consistent with encounter date
- Required references point to correct resource types
- Resource is not negated or in exception list

**What it does NOT check:**
- Clinical plausibility (is the value reasonable?)
- Population-level patterns (are there anomalies?)

**Pass rate:** Percentage of resources in correct clinical context for their measure

**Example failure:** Blood pressure reading coded with wrong encounter type, or dated outside measurement period

---

### Level 4: Clinical Plausibility

**Question:** Does the data make clinical sense? Are values in reasonable ranges?

**Scope:** Value ranges, logical constraints, negation/exception handling

**Tools:**
- PIQI plausibility rules
- Clinical constraint rules
- Conformance engine

**What it checks:**
- Numeric values within physiological ranges
  - HbA1c: 4.0–12.0%
  - Blood pressure systolic: 30–300 mmHg
  - Weight: 10–500 lbs
- No impossible combinations (e.g., pregnancy in males, age constraints on diagnoses)
- Negation codes handled correctly
- Exception codes present when measure requires
- Dates are logical (birth before visit, etc.)

**What it does NOT check:**
- Population-level patterns or anomalies

**Pass rate:** Percentage of resources with plausible values

**Example failures:**
- HbA1c value of 15% (above physiological range)
- Encounter dated 01-01-1900
- Diabetes diagnosis in 8-year-old

---

### Level 5: Stability (Population-Level)

**Question:** Are there anomalies in the population-level distribution of codes/values?

**Scope:** Population distributions, anomaly detection

**Tools:**
- scikit-learn (Isolation Forest, DBSCAN, One-Class SVM)
- Statistical outlier detection
- Conformance engine (optional, requires scikit-learn)

**Note:** Level 5 is optional for UC1 baseline assessment. It requires `scikit-learn` and is most useful for continuous monitoring (UC2).

**What it checks:**
- No sudden spikes in code frequencies
- Provider attribution patterns are normal
- Clinical record density consistent across time
- No systematic missing data by demographic group
- No ghost providers with zero clinical records

**What it does NOT check:**
- Whether individual resources are correct (that's Levels 1–4)

**Pass rate:** Stability assessment (PASS/FAIL based on anomaly threshold)

**Example anomalies:**
- 300% spike in diabetes diagnoses month-over-month
- High-volume PCP with zero clinical records
- Sudden drop in Observation volume

---

## PIQI Quality Dimensions

PIQI (Patient Information Quality Improvement) framework provides four dimensions for assessing data quality.

### Usability

**Question:** Is the eligible population complete?

**Measures:**
- Member count from 834 enrollment files
- Patient count in FHIR system
- Match rate between enrollment and FHIR

**Target:** >95% match between 834 members and FHIR Patient resources

**Remediation:** Member identity resolution, enrollment synchronization

---

### Plausibility

**Question:** Do enrolled members have continuous enrollment and valid demographics?

**Measures:**
- Continuous enrollment gaps detected
- Demographic constraints violated (age, sex)
- Retroactive disenrollment handled

**Target:** >99% of records have valid enrollment and demographics

**Remediation:** Enrollment processing rules, demographic validation

---

### Comparability

**Question:** Are clinical records present for all providers with attribution?

**Measures:**
- Provider-level clinical record density
- "Ghost PCP" detection (high attribution, zero records)
- Coverage rate across high-volume providers

**Target:** >90% of attributed PCPs have at least one clinical record

**Remediation:** Provider directory validation, EHR feed completeness

---

### Stability

**Question:** Are population-level metrics stable over time?

**Measures:**
- Code frequency distributions
- Attribution pattern changes
- Record volume trends
- Demographic composition shifts

**Target:** <5% month-over-month variance in key metrics (without clinical justification)

**Remediation:** Data pipeline health checks, source feed monitoring

---

## Aggregation Rules

### Per-Resource Metrics

Each FHIR resource gets scored on Levels 1–4:

```json
{
    "resource_id": "Observation/lab-123",
    "level_1_vsd_conformance": 1.0,      // 100%
    "level_2_profile_conformance": 1.0,  // 100%
    "level_3_context_conformance": 0.87, // 87%
    "level_4_plausibility": 0.92,        // 92%
}
```

### Per-Resource-Type Aggregates

All resources of a type (e.g., "Observation") averaged:

```json
{
    "resource_type": "Observation",
    "resource_count": 150000,
    "level_1_avg": 0.9888,
    "level_2_avg": 0.9818,
    "level_3_avg": 0.9943,
    "level_4_avg": 0.9809,
}
```

### Per-Feed Aggregates

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

### Plan-Level Summary

Across all resources and feeds:

```json
{
    "plan_summary": {
        "total_resources": 5000000,
        "level_1_avg": 0.9850,
        "level_2_avg": 0.9800,
        "level_3_avg": 0.9900,
        "level_4_avg": 0.9750,
        "feeds_count": 8,
        "resource_types_count": 12
    }
}
```

---

## Interpretation Guide

### What scores mean

**0.95–1.00:** Excellent. Few issues.

**0.90–0.95:** Good. Minor issues that should be investigated.

**0.85–0.90:** Adequate. Moderate issues requiring remediation.

**0.80–0.85:** Poor. Significant gaps that affect measure accuracy.

**<0.80:** Critical. Requires immediate investigation and remediation.

### Per-Level Remediation Priorities

**Level 1 failure (0.90):** Value set bindings incorrect or outdated. Remediation: Update mappings, refresh value sets.

**Level 2 failure (0.90):** FHIR profile conformance gaps. Remediation: StructureDefinition validation, FHIR server updates.

**Level 3 failure (0.90):** Clinical context mismatches. Remediation: ETL logic review, HEDIS specification alignment.

**Level 4 failure (0.90):** Implausible values. Remediation: Data quality rules, source system validation.

**Level 5 anomaly (FAIL):** Population-level outliers. Remediation: Pipeline health checks, data source investigation.
