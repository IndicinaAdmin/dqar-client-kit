"""
Fetch a patient cohort from a public HAPI FHIR server and package as Bulk FHIR-format
NDJSON (one resource per line, one file per resourceType), then compress to tar.gz.

The public HAPI server at https://hapi.fhir.org/baseR4 does not support $export.
This script uses standard FHIR search with _count and pagination to pull Patient
resources then follows Patient/$everything or individual searches to fetch linked
clinical resources.

Usage:
    python tools/fetch_hapi_extract.py [--server URL] [--count N] [--out PATH]

Defaults:
    --server  https://hapi.fhir.org/baseR4
    --count   100
    --out     data/hapi-100-patients.tar.gz
"""

import argparse
import collections
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import requests

RESOURCE_TYPES = [
    "Condition",
    "Coverage",
    "DiagnosticReport",
    "Encounter",
    "Immunization",
    "MedicationDispense",
    "MedicationRequest",
    "Observation",
    "Procedure",
]

HEDIS_CRITICAL = {
    "Patient", "Coverage", "Condition", "Observation",
    "Encounter", "Procedure", "MedicationRequest", "MedicationDispense",
    "DiagnosticReport", "Immunization",
}


def _get(session: requests.Session, url: str, params: dict = None) -> dict:
    """GET with retry on 429 / 5xx."""
    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", "5"))
                print(f"    Rate-limited — waiting {retry_after}s…", flush=True)
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError as exc:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed after 3 attempts")


def fetch_patients(session: requests.Session, base_url: str, count: int) -> list[dict]:
    """Return up to `count` Patient resources via paginated search."""
    patients = []
    url = f"{base_url}/Patient"
    params = {"_count": min(count, 50), "_elements": "id,name,birthDate,gender"}

    print(f"  Fetching up to {count} patients…", flush=True)
    while url and len(patients) < count:
        bundle = _get(session, url, params)
        params = None  # next-link already includes params
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Patient":
                patients.append(resource)
                if len(patients) >= count:
                    break
        # Follow next page link
        url = None
        for link in bundle.get("link", []):
            if link.get("relation") == "next":
                url = link["url"]
                break

    print(f"  Got {len(patients)} patients")
    return patients[:count]


def fetch_patient_everything(
    session: requests.Session,
    base_url: str,
    patient_ids: list[str],
) -> dict[str, list]:
    """
    For each patient ID, call Patient/{id}/$everything and collect resources by type.
    Falls back to per-type searches if $everything returns nothing.
    """
    by_type: dict[str, list] = collections.defaultdict(list)
    seen: set[str] = set()

    total = len(patient_ids)
    for i, pid in enumerate(patient_ids, 1):
        print(f"\r  Clinical resources: patient {i}/{total}…", end="", flush=True)

        # Try $everything first (supported on some HAPI instances)
        everything_url = f"{base_url}/Patient/{pid}/$everything"
        try:
            bundle = _get(session, everything_url)
            entries = bundle.get("entry", [])
            if entries:
                for entry in entries:
                    r = entry.get("resource", {})
                    rt = r.get("resourceType")
                    rid = r.get("id")
                    key = f"{rt}/{rid}"
                    if rt and rid and key not in seen:
                        seen.add(key)
                        by_type[rt].append(r)
                continue
        except Exception:
            pass  # fall through to individual searches

        # Fallback: search each resource type by subject/patient
        for rt in RESOURCE_TYPES:
            param_key = "patient" if rt not in ("Coverage",) else "subscriber"
            try:
                result = _get(
                    session,
                    f"{base_url}/{rt}",
                    params={param_key: pid, "_count": 100},
                )
                for entry in result.get("entry", []):
                    r = entry.get("resource", {})
                    rid = r.get("id")
                    key = f"{rt}/{rid}"
                    if rid and key not in seen:
                        seen.add(key)
                        by_type[rt].append(r)
            except Exception:
                pass

    print()  # newline after progress
    return by_type


def write_ndjson(tmp_dir: Path, resources_by_type: dict[str, list]) -> list[Path]:
    files = []
    for rt, resources in sorted(resources_by_type.items()):
        if not resources:
            continue
        out = tmp_dir / f"{rt}.ndjson"
        with open(out, "w", encoding="utf-8") as f:
            for r in resources:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
        files.append(out)
        print(f"    {rt}.ndjson — {len(resources):,} resources")
    return files


def create_tarball(ndjson_files: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output_path, "w:gz") as tf:
        for f in ndjson_files:
            tf.add(f, arcname=f.name)
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\n  Packaged {len(ndjson_files)} NDJSON files → {output_path} ({size_mb:.1f} MB)")


def print_summary(by_type: dict[str, list], patient_count: int) -> None:
    total = sum(len(v) for v in by_type.values())
    hedis_types = {rt for rt in by_type if rt in HEDIS_CRITICAL}
    missing = HEDIS_CRITICAL - set(by_type.keys())

    print("\n" + "─" * 58)
    print(f"  HAPI Extract Summary")
    print(f"  Patients fetched : {patient_count:,}")
    print(f"  Total resources  : {total:,}")
    print(f"  Resource types   : {len(by_type)}")
    print(f"  HEDIS-critical   : {len(hedis_types)}/{len(HEDIS_CRITICAL)} types present")
    if missing:
        print(f"  Missing types    : {', '.join(sorted(missing))}")
    print("─" * 58)

    if "Coverage" not in by_type:
        print("  ⚠  No Coverage resources — enrollment not determinable")
    if "Condition" not in by_type:
        print("  ⚠  No Condition resources — measure exclusions unverifiable")


def main():
    parser = argparse.ArgumentParser(description="Fetch HAPI FHIR cohort as Bulk FHIR NDJSON tar.gz")
    parser.add_argument("--server", default="https://hapi.fhir.org/baseR4",
                        help="FHIR server base URL (default: hapi.fhir.org/baseR4)")
    parser.add_argument("--count", type=int, default=100,
                        help="Number of patients to fetch (default: 100)")
    parser.add_argument("--out", default="data/hapi-100-patients.tar.gz",
                        help="Output tar.gz path (default: data/hapi-100-patients.tar.gz)")
    args = parser.parse_args()

    base_url = args.server.rstrip("/")
    output_path = Path(args.out)

    print(f"\nCDAR — HAPI FHIR Extract")
    print(f"  Server : {base_url}")
    print(f"  Target : {args.count} patients")
    print(f"  Output : {output_path}\n")

    session = requests.Session()
    session.headers.update({
        "Accept": "application/fhir+json",
        "Content-Type": "application/fhir+json",
    })

    # Fetch patients
    patients = fetch_patients(session, base_url, args.count)
    if not patients:
        print("ERROR: No patients returned from server.")
        sys.exit(1)

    patient_ids = [p["id"] for p in patients]

    # Fetch clinical resources
    print(f"  Fetching clinical resources for {len(patient_ids)} patients…")
    by_type = fetch_patient_everything(session, base_url, patient_ids)

    # Include patients themselves
    by_type["Patient"] = patients

    # Write to temp dir → tar.gz
    with tempfile.TemporaryDirectory(prefix="dqar-hapi-") as tmp:
        tmp_dir = Path(tmp)
        print("\n  Writing NDJSON files:")
        ndjson_files = write_ndjson(tmp_dir, by_type)
        create_tarball(ndjson_files, output_path)

    print_summary(by_type, len(patients))
    print(f"\n  Done. Upload {output_path} to the CDAR web UI or pass to orchestrate.py --ndjson-dir\n")


if __name__ == "__main__":
    main()
