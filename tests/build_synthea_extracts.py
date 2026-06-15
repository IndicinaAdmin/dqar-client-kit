"""
Build NDJSON extracts from Synthea patient bundles.

Reads 50 patients from data/synthea/fhir/, converts to NDJSON bulk-export format,
then writes:
  data/synthea-50/          — clean baseline extract
  data/synthea-50-errors/   — same data with error files alongside clean files

Error files use naming convention: <ResourceType>_<error_type>.ndjson

Run from project root:
    python tests/build_synthea_extracts.py
"""

import json
import os
import random
import shutil
from pathlib import Path

SYNTHEA_DIR  = Path("data/synthea/fhir")
BASELINE_DIR = Path("data/synthea-50")
ERRORS_DIR   = Path("data/synthea-50-errors")
PATIENT_LIMIT = 50

# Resource types to extract into separate NDJSON files
RESOURCE_TYPES = [
    "Patient", "Encounter", "Condition", "Observation",
    "Procedure", "DiagnosticReport", "MedicationRequest",
    "Immunization", "Coverage", "Organization", "Practitioner",
    "CarePlan", "CareTeam", "AllergyIntolerance", "Device",
]


# ── 1. Read and extract ───────────────────────────────────────────────────────

def load_resources(synthea_dir: Path, limit: int) -> dict[str, list[dict]]:
    """Return {resourceType: [resource, ...]} from first `limit` patient bundles."""
    buckets: dict[str, list[dict]] = {rt: [] for rt in RESOURCE_TYPES}
    bundle_files = sorted(synthea_dir.glob("*.json"))[:limit]

    for bundle_path in bundle_files:
        bundle = json.loads(bundle_path.read_text())
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            rt = resource.get("resourceType")
            if rt in buckets:
                buckets[rt].append(resource)

    return buckets


def write_ndjson(resources: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in resources:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


# ── 2. Baseline ───────────────────────────────────────────────────────────────

def build_baseline(buckets: dict[str, list[dict]], out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for rt, resources in buckets.items():
        if resources:
            write_ndjson(resources, out_dir / f"{rt}.ndjson")
    print(f"Baseline written → {out_dir}  ({sum(len(v) for v in buckets.values())} resources)")


# ── 3. Error injection helpers ────────────────────────────────────────────────

def inject_utf8_errors(resources: list[dict], n: int = 5) -> bytes:
    """Write valid NDJSON then corrupt `n` random lines with invalid UTF-8 byte."""
    lines = [json.dumps(r, separators=(",", ":")).encode("utf-8") for r in resources]
    targets = random.sample(range(len(lines)), min(n, len(lines)))
    for i in targets:
        pos = len(lines[i]) // 2
        lines[i] = lines[i][:pos] + b"\x80" + lines[i][pos:]
    return b"\n".join(lines) + b"\n"


def inject_invalid_json(resources: list[dict], n: int = 5) -> str:
    """Truncate `n` random lines mid-record."""
    lines = [json.dumps(r, separators=(",", ":")) for r in resources]
    targets = random.sample(range(len(lines)), min(n, len(lines)))
    for i in targets:
        lines[i] = lines[i][:40]   # truncate to 40 chars → invalid JSON
    return "\n".join(lines) + "\n"


def inject_missing_resource_type(resources: list[dict], n: int = 5) -> str:
    """Remove resourceType from `n` random records."""
    resources = [r.copy() for r in resources]
    targets = random.sample(range(len(resources)), min(n, len(resources)))
    for i in targets:
        resources[i] = {k: v for k, v in resources[i].items() if k != "resourceType"}
    return "\n".join(json.dumps(r, separators=(",", ":")) for r in resources) + "\n"


def inject_wrong_resource_type(resources: list[dict], donor: list[dict]) -> str:
    """Append records from a different resource type (filename/content mismatch)."""
    all_resources = list(resources) + random.sample(donor, min(5, len(donor)))
    return "\n".join(json.dumps(r, separators=(",", ":")) for r in all_resources) + "\n"


def inject_missing_required_fields(resources: list[dict], fields: list[str], n: int = 10) -> str:
    """Strip required R4/US Core fields from `n` records."""
    resources = [r.copy() for r in resources]
    targets = random.sample(range(len(resources)), min(n, len(resources)))
    for i in targets:
        for f in fields:
            resources[i].pop(f, None)
    return "\n".join(json.dumps(r, separators=(",", ":")) for r in resources) + "\n"


def inject_missing_us_core_fields(resources: list[dict], fields: list[str], n: int = 10) -> str:
    """Remove US Core must-support fields from `n` records."""
    return inject_missing_required_fields(resources, fields, n)


def inject_subsetted_tag(resources: list[dict], n: int = None) -> str:
    """Add SUBSETTED tag to meta.tag on all (or `n`) records."""
    n = n or len(resources)
    resources = [r.copy() for r in resources]
    for i in range(min(n, len(resources))):
        meta = resources[i].setdefault("meta", {})
        tags = meta.setdefault("tag", [])
        tags.append({"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue", "code": "SUBSETTED"})
    return "\n".join(json.dumps(r, separators=(",", ":")) for r in resources) + "\n"


# ── 4. Build errors extract ───────────────────────────────────────────────────

def build_errors(buckets: dict[str, list[dict]], out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    patients     = buckets["Patient"]
    conditions   = buckets["Condition"]
    observations = buckets["Observation"]
    encounters   = buckets["Encounter"]
    procedures   = buckets["Procedure"]
    med_requests = buckets["MedicationRequest"]
    coverage     = buckets["Coverage"]
    diag_reports = buckets["DiagnosticReport"]

    errors: dict[str, tuple] = {
        # Clean baseline files (carry through unmodified)
        "Patient.ndjson":                ("text",   "\n".join(json.dumps(r, separators=(",", ":")) for r in patients) + "\n"),
        "Immunization.ndjson":           ("text",   "\n".join(json.dumps(r, separators=(",", ":")) for r in buckets["Immunization"]) + "\n"),
        "Organization.ndjson":           ("text",   "\n".join(json.dumps(r, separators=(",", ":")) for r in buckets["Organization"]) + "\n"),
        "Practitioner.ndjson":           ("text",   "\n".join(json.dumps(r, separators=(",", ":")) for r in buckets["Practitioner"]) + "\n"),

        # Stage 1b errors — structural
        "Patient_utf8_errors.ndjson":    ("bytes",  inject_utf8_errors(patients, n=5)),
        "Condition_invalid_json.ndjson": ("text",   inject_invalid_json(conditions, n=5)),
        "Encounter_missing_resourcetype.ndjson": ("text", inject_missing_resource_type(encounters, n=5)),
        "Coverage_empty.ndjson":         ("text",   ""),
        "Procedure_wrong_type.ndjson":   ("text",   inject_wrong_resource_type(procedures, observations)),

        # Stage 1c-i errors — base R4 required fields
        "Observation_missing_status.ndjson":          ("text", inject_missing_required_fields(observations, ["status"])),
        "MedicationRequest_missing_status_intent.ndjson": ("text", inject_missing_required_fields(med_requests, ["status", "intent"])),
        "Encounter_missing_status_class.ndjson":      ("text", inject_missing_required_fields(encounters, ["status", "class"])),

        # Stage 1c-ii errors — US Core profile violations
        "Patient_missing_identifier.ndjson":      ("text", inject_missing_us_core_fields(patients, ["identifier"])),
        "Condition_missing_category.ndjson":      ("text", inject_missing_us_core_fields(conditions, ["category"])),
        "Observation_missing_category.ndjson":    ("text", inject_missing_us_core_fields(observations, ["category"])),
        "Encounter_missing_type.ndjson":          ("text", inject_missing_us_core_fields(encounters, ["type"])),

        # SUBSETTED detection error
        "DiagnosticReport_subsetted.ndjson":      ("text", inject_subsetted_tag(diag_reports)),
    }

    for filename, (mode, content) in errors.items():
        path = out_dir / filename
        if mode == "bytes":
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    print(f"Error extract written → {out_dir}  ({len(errors)} files)")
    print()
    print("  Error files included:")
    for f in sorted(out_dir.glob("*.ndjson")):
        size = f.stat().st_size
        print(f"    {f.name:55s}  {size:>7,} bytes")


# ── 5. Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    random.seed(42)

    print(f"Loading {PATIENT_LIMIT} Synthea patients from {SYNTHEA_DIR} …")
    buckets = load_resources(SYNTHEA_DIR, PATIENT_LIMIT)

    counts = {rt: len(v) for rt, v in buckets.items() if v}
    print(f"  Resource types found: {list(counts.keys())}")
    print(f"  Total resources: {sum(counts.values())}\n")

    build_baseline(buckets, BASELINE_DIR)
    print()
    build_errors(buckets, ERRORS_DIR)
    print("\nDone.")
