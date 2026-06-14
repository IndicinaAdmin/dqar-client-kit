"""
Stage 1a-ii — Bulk FHIR extract packaging conformance.

Verifies that an NDJSON file set constitutes a well-formed Bulk FHIR extract
suitable for digital quality assessment:

  1. extract_not_empty        — At least one non-empty NDJSON file
  2. patient_file_present     — Patient.ndjson present (denominator population)
  3. hedis_core_types_present — Condition, Observation, Encounter all present
  4. medication_data_present  — MedicationRequest or MedicationDispense present
  5. single_type_per_file     — Each file contains only one resource type (Bulk FHIR IG)

Does not re-validate JSON structure — that is Stage 1b's responsibility.
Skips unparseable lines silently and reports type presence based on valid lines.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


QM_CORE_TYPES = {"Patient", "Condition", "Observation", "Encounter"}
QM_MEDICATION_TYPES = {"MedicationRequest", "MedicationDispense"}

# Da Vinci DEQM IG — resources required for quality measure *reporting*.
# Source: DEQM Library dataRequirements (MRP, COL/EXM130, VTE/EXM108),
# DEQM IndividualMeasureReport profile, and named QI-Core default profiles.
# Coverage replaces the former DEQM-specific Coverage profile per guidance.html.
DEQM_REQUIRED = {"Patient", "Organization", "Practitioner", "Encounter", "Coverage"}

# QI-Core IG — resource types required by the 5 priority ECDS measures (COL/EXM130,
# MRP, EXM124, VTE/EXM108, CDC) for CQL measure logic execution.
# Distinct from DEQM_REQUIRED: DEQM governs the reporting wrapper; QI-Core governs
# the data model consumed by the CQL engine.
QI_CORE_REQUIRED = {
    "Patient",           # All measures — population denominator anchor
    "Encounter",         # All measures — qualifying encounter criteria
    "Condition",         # COL, VTE, CDC — diagnosis-based inclusions/exclusions
    "Observation",       # COL, EXM124, VTE, CDC — lab and clinical results
    "Procedure",         # COL, EXM124, VTE — screening and prophylaxis procedures
    "DiagnosticReport",  # COL, EXM124 — structured lab report results
    "MedicationRequest", # MRP, VTE — medication orders and reconciliation
}

# All FHIR resource types with defined QI-Core 6.0 profiles.
# Types outside this set have no QI-Core profile and will not be consumed
# by CQL measure logic regardless of what the extract contains.
QI_CORE_PROFILED = QI_CORE_REQUIRED | {
    "AllergyIntolerance", "CarePlan", "CareTeam", "Communication",
    "CommunicationRequest", "Coverage", "Device", "DeviceRequest",
    "DeviceUseStatement", "FamilyMemberHistory", "Goal", "Immunization",
    "Location", "MedicationAdministration", "MedicationDispense",
    "NutritionOrder", "Organization", "Practitioner", "PractitionerRole",
    "RelatedPerson", "ServiceRequest", "Specimen", "Substance", "Task",
}


def _check(name: str, passed: bool, detail: str = "") -> dict:
    return {"check": name, "passed": passed, "detail": detail}


def run(ndjson_dir: str, engagement: str = "client", output_path: str = None) -> dict:
    ndjson_path = Path(ndjson_dir)
    files = sorted(ndjson_path.glob("*.ndjson"))

    inventory: dict[str, int] = {}
    empty_files: list[str] = []
    multi_type_files: list[str] = []

    for f in files:
        types_in_file: set[str] = set()
        count = 0
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    rt = obj.get("resourceType", "Unknown")
                    types_in_file.add(rt)
                    inventory[rt] = inventory.get(rt, 0) + 1
                    count += 1
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

        if count == 0:
            empty_files.append(f.name)
        if len(types_in_file) > 1:
            multi_type_files.append(f.name)

    checks = []
    total_resources = sum(inventory.values())

    checks.append(_check(
        "extract_not_empty",
        total_resources > 0,
        f"{total_resources:,} resources across {len(files)} file{'s' if len(files) != 1 else ''}",
    ))

    patient_count = inventory.get("Patient", 0)
    checks.append(_check(
        "patient_file_present",
        patient_count > 0,
        (f"{patient_count:,} Patient records"
         if patient_count
         else "Patient.ndjson absent — denominator population required for all quality measures"),
    ))

    missing_core = (QM_CORE_TYPES - {"Patient"}) - set(inventory.keys())
    core_ok = len(missing_core) == 0
    present_core = (QM_CORE_TYPES - {"Patient"}) & set(inventory.keys())
    checks.append(_check(
        "hedis_core_types_present",
        core_ok,
        (f"Condition, Observation, Encounter all present"
         if core_ok
         else f"Missing: {', '.join(sorted(missing_core))}; Present: {', '.join(sorted(present_core)) or 'none'}"),
    ))

    med_types = QM_MEDICATION_TYPES & set(inventory.keys())
    med_ok = len(med_types) > 0
    checks.append(_check(
        "medication_data_present",
        med_ok,
        (f"{', '.join(sorted(med_types))} present"
         if med_ok
         else "MedicationRequest and MedicationDispense both absent — medication measures will be incomplete"),
    ))

    single_ok = len(multi_type_files) == 0
    checks.append(_check(
        "single_type_per_file",
        single_ok,
        ("Each file contains exactly one resource type"
         if single_ok
         else f"Mixed-type files: {', '.join(multi_type_files[:3])}{'…' if len(multi_type_files) > 3 else ''}"),
    ))

    overall = "PASS" if all(c["passed"] for c in checks) else "FAIL"

    # Build resource type table with DEQM status.
    # "required" = DEQM-required and present; "required-missing" = required but absent;
    # "optional" = not required by DEQM (covers supplemental QI-Core types and
    # out-of-scope types like Claim, ExplanationOfBenefit, AuditEvent).
    def _qicore_status(rt: str, cnt: int) -> str:
        if rt in QI_CORE_REQUIRED:
            return "required" if cnt > 0 else "required-missing"
        return "optional" if rt in QI_CORE_PROFILED else "not-profiled"

    resource_types = [
        {
            "resource_type": rt,
            "count": cnt,
            "deqm_status": "required" if rt in DEQM_REQUIRED else "optional",
            "qicore_status": _qicore_status(rt, cnt),
        }
        for rt, cnt in sorted(inventory.items())
    ]
    # Append any DEQM-required or QI-Core-required types entirely absent from the extract
    present = {rt["resource_type"] for rt in resource_types}
    for rt in sorted((DEQM_REQUIRED | QI_CORE_REQUIRED) - present):
        resource_types.append({
            "resource_type": rt,
            "count": 0,
            "deqm_status": "required-missing" if rt in DEQM_REQUIRED else "optional",
            "qicore_status": "required-missing" if rt in QI_CORE_REQUIRED else "optional",
        })
    resource_types.sort(key=lambda r: r["resource_type"])

    report = {
        "report_type": "bulk-fhir-extract-packaging",
        "stage": "1a-ii",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engagement": engagement,
        "status": overall,
        "checks": checks,
        "summary": {
            "total_resources": total_resources,
            "total_files": len(files),
            "resource_types_found": len(inventory),
            "empty_files": len(empty_files),
        },
        "resource_types": resource_types,
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as fout:
            json.dump(report, fout, indent=2)

    print(f"Stage 1a-ii — Extract packaging: {overall} "
          f"({total_resources:,} resources, {len(inventory)} types)")
    return report
