# dqar-client-kit: Complete Specifications (v2.0)

**Component:** Data conformance validation CLI for UC1 assessment  
**Duration:** 10 weeks (5 phases, 2 weeks each)  
**Owner:** Sonian Team  
**Status:** Ready for Implementation  

## What This Component Does

Validates health payer FHIR data against:
1. Feed manifest declarations
2. Five-level semantic conformance (terminology → clinical plausibility)
3. PIQI data quality metrics
4. dbt transformation lineage gaps
5. Generates Databricks/Snowflake UC table properties

## Input → Output

```
FHIR Bulk Export (NDJSON)
+ Manifest (feed declarations)
    ↓
client-kit validate-all
    ↓
Output:
- Conformance report (5 levels + PIQI)
- UC table properties (JSON + SQL)
- DQAR findings (Tiers 1, 2, 3)
- Executive summary (HTML)
```

## Key Design Decisions

- ✅ Single CLI with subcommands
- ✅ No source-type inference (explicit manifest matching only)
- ✅ Dual UC properties output (JSON for API, SQL for IaC)
- ✅ Optional ML dependencies (Level 5 anomaly detection)
- ✅ dbt detection as Tier 3 finding (pre-FHIR lineage gap)

## Five Phases

| Phase | Duration | What | Output |
|---|---|---|---|
| 1 | Weeks 1–2 | CLI architecture, manifest validation | Manifest report, feed inventory |
| 2 | Weeks 3–4 | Data conformance, PIQI metrics | Conformance report, member drill-down |
| 3 | Weeks 5–6 | UC properties (JSON + SQL) | uc_table_properties.json/sql |
| 4 | Weeks 7–8 | dbt lineage detection | Tier 3 findings |
| 5 | Weeks 9–10 | Orchestration, integration tests | DQAR_FINDINGS.json, EXECUTIVE_SUMMARY.html |

## How to Use This Spec

1. Read this file (you are here)
2. Follow phases sequentially:
   - Phase 1: 01-phase-1-cli-architecture.md
   - Phase 2: 02-phase-2-data-conformance.md
   - Phase 3: 03-phase-3-uc-properties.md
   - Phase 4: 04-phase-4-dbt-lineage.md
   - Phase 5: 05-phase-5-integration-orchestration.md
3. Use DEPENDENCIES.md for package setup
4. Check ACCEPTANCE_CRITERIA.md to validate completion
5. See EXAMPLES.md for usage patterns

## Files in This Directory

- **00-OVERVIEW.md** (this file)
- **01-phase-1-cli-architecture.md** → Phase 1 detailed spec
- **02-phase-2-data-conformance.md** → Phase 2 detailed spec
- **03-phase-3-uc-properties.md** → Phase 3 detailed spec
- **04-phase-4-dbt-lineage.md** → Phase 4 detailed spec
- **05-phase-5-integration-orchestration.md** → Phase 5 detailed spec
- **dqar-client-kit-phases-02-to-05.md** → COMPLETE code implementations for all phases
- **DEPENDENCIES.md** → Package dependencies
- **ACCEPTANCE_CRITERIA.md** → Validation checklist
- **EXAMPLES.md** → Usage examples

## Start Here

**New to this project?** → Read this 00-OVERVIEW.md, then start with Phase 1

**Ready to implement?** → Open dqar-client-kit-phases-02-to-05.md for all code

**Need examples?** → See EXAMPLES.md

**Need to validate?** → Check ACCEPTANCE_CRITERIA.md
