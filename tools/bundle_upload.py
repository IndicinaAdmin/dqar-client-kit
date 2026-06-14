import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.engagement import load_engagement, get_fhir_headers

import requests

US_CORE_PREFIX = "http://hl7.org/fhir/us/core"


def _normalise_bundle(bundle: dict) -> dict:
    """
    Rewrite POST entries that already have resource.id set to PUT /{type}/{id}.
    Synthea sets resource.id but uses POST, which is non-idempotent — retries
    after a timeout cause duplicate-key errors. PUT is an upsert so re-runs
    are always safe.
    """
    for entry in bundle.get("entry", []):
        req = entry.get("request", {})
        resource = entry.get("resource", {})
        if req.get("method") == "POST" and resource.get("id"):
            rt = resource["resourceType"]
            rid = resource["id"]
            req["method"] = "PUT"
            req["url"] = f"{rt}/{rid}"
    return bundle


def _post_chunk(entries: list, base_url: str, headers: dict) -> dict:
    """POST a single transaction bundle chunk. Returns (created, entries, error_dict|None)."""
    chunk = {"resourceType": "Bundle", "type": "transaction", "entry": entries}
    response = requests.post(f"{base_url}/fhir", json=chunk, headers=headers)
    if response.status_code not in (200, 201):
        try:
            outcome = response.json()
        except Exception:
            outcome = {"raw": response.text}
        return {"ok": False, "http_status": response.status_code, "outcome": outcome}
    result = response.json()
    created = sum(
        1 for e in result.get("entry", [])
        if e.get("response", {}).get("status", "").startswith("201")
    )
    return {"ok": True, "entries": len(result.get("entry", [])), "created": created}


def upload_bundle(bundle_path: Path, base_url: str, headers: dict, chunk_size: int = 0) -> dict:
    with open(bundle_path) as f:
        bundle = json.load(f)

    bundle = _normalise_bundle(bundle)
    entries = bundle.get("entry", [])

    # Split into chunks when chunk_size is set and bundle exceeds it
    if chunk_size > 0 and len(entries) > chunk_size:
        chunks = [entries[i:i + chunk_size] for i in range(0, len(entries), chunk_size)]
    else:
        chunks = [entries]

    total_entries = 0
    total_created = 0

    for chunk in chunks:
        result = _post_chunk(chunk, base_url, headers)
        if not result["ok"]:
            return {
                "file": bundle_path.name,
                "status": "error",
                "http_status": result["http_status"],
                "outcome": result["outcome"],
            }
        total_entries += result["entries"]
        total_created += result["created"]

    return {
        "file": bundle_path.name,
        "status": "ok",
        "entries": total_entries,
        "created": total_created,
    }


def _classify_issue(issue: dict) -> str:
    text = " ".join([
        issue.get("diagnostics", ""),
        json.dumps(issue.get("details", {})),
        " ".join(issue.get("expression", [])),
    ])
    return "us-core" if US_CORE_PREFIX in text else "base-fhir"


def extract_issues(error_record: dict) -> list[dict]:
    outcome = error_record.get("outcome", {})
    issues = []
    for issue in outcome.get("issue", []):
        issues.append({
            "severity": issue.get("severity"),
            "code": issue.get("code"),
            "diagnostics": issue.get("diagnostics", ""),
            "expression": issue.get("expression", []),
            "layer": _classify_issue(issue),
        })
    for entry in outcome.get("entry", []):
        for issue in entry.get("response", {}).get("outcome", {}).get("issue", []):
            if issue.get("severity") in ("error", "fatal"):
                issues.append({
                    "severity": issue.get("severity"),
                    "code": issue.get("code"),
                    "diagnostics": issue.get("diagnostics", ""),
                    "expression": issue.get("expression", []),
                    "layer": _classify_issue(issue),
                })
    return issues


def run_upload(
    engagement_path: str,
    synthea_dir: str = "data/synthea/fhir",
    error_report_path: str = "data/upload-validation-errors.json",
    only_files=None,
    chunk_size: int = 0,
) -> None:
    engagement = load_engagement(engagement_path)
    bundle_dir = Path(synthea_dir)
    all_bundles = sorted(bundle_dir.glob("*.json"))

    if not all_bundles:
        print(f"No JSON bundles found in {bundle_dir}")
        sys.exit(1)

    priority = sorted(bundle_dir.glob("hospitalInformation*.json")) + \
               sorted(bundle_dir.glob("practitionerInformation*.json"))
    patient_bundles = [b for b in all_bundles if b not in priority]
    bundles = priority + patient_bundles

    if only_files:
        bundles = [b for b in bundles if b.name in only_files]

    print(f"Uploading {len(bundles)} bundles to {engagement.base_url} ({engagement.server_type})...\n")

    headers = get_fhir_headers(engagement)
    total_created = 0
    error_records = []

    for i, bundle_path in enumerate(bundles, 1):
        result = upload_bundle(bundle_path, engagement.base_url, headers, chunk_size=chunk_size)
        if result["status"] == "ok":
            total_created += result["created"]
            print(f"  [{i}/{len(bundles)}] {result['file']} — {result['created']} created ({result['entries']} entries)")
        else:
            issues = extract_issues(result)
            error_records.append({"file": result["file"], "http_status": result["http_status"], "issues": issues})
            us_core_count = sum(1 for iss in issues if iss["layer"] == "us-core")
            print(f"  [{i}/{len(bundles)}] ERROR: {result['file']} — HTTP {result['http_status']} "
                  f"({len(issues) - us_core_count} base-fhir, {us_core_count} us-core issues)")

    if error_records:
        all_issues = [iss for rec in error_records for iss in rec["issues"]]
        us_core_issues = [i for i in all_issues if i["layer"] == "us-core"]
        base_issues = [i for i in all_issues if i["layer"] == "base-fhir"]

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "engagement": engagement.name,
            "server_type": engagement.server_type,
            "fhir_server": engagement.base_url,
            "failed_bundles": len(error_records),
            "total_issues": len(all_issues),
            "base_fhir_issues": len(base_issues),
            "us_core_issues": len(us_core_issues),
            "errors": error_records,
        }
        Path(error_report_path).parent.mkdir(parents=True, exist_ok=True)
        with open(error_report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n{len(error_records)} bundle(s) failed — "
              f"{len(base_issues)} base-FHIR, {len(us_core_issues)} US Core issues.")
        print(f"Validation error report: {error_report_path}")
    else:
        print(f"\nAll bundles uploaded. {total_created} total resources created.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload Synthea FHIR bundles")
    parser.add_argument("--engagement", required=True, help="Path to engagement config JSON")
    parser.add_argument("--synthea-dir", default="data/synthea/fhir")
    parser.add_argument("--error-report", default="data/upload-validation-errors.json")
    parser.add_argument("--only-files", metavar="FILE",
                        help="Text file listing bundle filenames to upload (one per line). "
                             "Use to retry a specific set of bundles.")
    parser.add_argument("--chunk-size", type=int, default=0, metavar="N",
                        help="Split bundles into chunks of N entries each. 0 = no chunking (default). "
                             "Use ~500 to avoid 504 gateway timeouts on large bundles.")
    args = parser.parse_args()

    only_files = None
    if args.only_files:
        with open(args.only_files) as f:
            only_files = [line.strip() for line in f if line.strip()]

    run_upload(args.engagement, args.synthea_dir, args.error_report, only_files, args.chunk_size)
