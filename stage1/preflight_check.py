import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.engagement import load_engagement, get_fhir_headers

import requests

REQUIRED_RESOURCE_TYPES = [
    "Patient", "Coverage", "Organization", "Practitioner",
    "PractitionerRole", "Location", "Condition", "Observation",
    "Encounter", "Procedure", "MedicationRequest", "MedicationDispense",
    "DiagnosticReport", "Immunization", "ServiceRequest",
    "ExplanationOfBenefit", "Provenance", "AuditEvent"
]


def fetch_capability_statement(base_url: str, headers: dict) -> dict:
    response = requests.get(
        f"{base_url}/fhir/metadata",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def parse_supported_resources(capability: dict) -> dict:
    supported = {}
    for rest_entry in capability.get("rest", []):
        for resource in rest_entry.get("resource", []):
            rt = resource.get("type")
            interactions = [i.get("code") for i in resource.get("interaction", [])]
            supported[rt] = {
                "interactions": interactions,
                "export_supported": "search-type" in interactions,
            }
    return supported


def check_bulk_export_support(capability: dict) -> bool:
    for rest_entry in capability.get("rest", []):
        for op in rest_entry.get("operation", []):
            if op.get("name") == "export":
                return True
    return False


def run_preflight(engagement_path: str, output_path: str = "preflight-report.json") -> dict:
    engagement = load_engagement(engagement_path)
    print(f"Connecting to {engagement.base_url} ({engagement.server_type})...")

    headers = get_fhir_headers(engagement)
    capability = fetch_capability_statement(engagement.base_url, headers)
    supported = parse_supported_resources(capability)
    export_supported = check_bulk_export_support(capability)

    resource_checks = []
    for rt in REQUIRED_RESOURCE_TYPES:
        present = rt in supported
        resource_checks.append({
            "resource_type": rt,
            "present": present,
            "export_supported": supported.get(rt, {}).get("export_supported", False),
            "interactions": supported.get(rt, {}).get("interactions", []),
            "status": "OK" if present else "MISSING",
        })

    missing = [r for r in resource_checks if not r["present"]]

    report = {
        "report_type": "preflight",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engagement": engagement.name,
        "server_type": engagement.server_type,
        "fhir_server": engagement.base_url,
        "fhir_version": capability.get("fhirVersion"),
        "bulk_export_supported": export_supported,
        "required_resource_types_checked": len(REQUIRED_RESOURCE_TYPES),
        "missing_resource_types": len(missing),
        "resource_checks": resource_checks,
        "status": "PASS" if not missing else "GAPS_FOUND",
        "gaps": [r["resource_type"] for r in missing],
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Preflight complete. Status: {report['status']}")
    print(f"Report written to {output_path}")
    if missing:
        print(f"Missing resource types: {report['gaps']}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FHIR server preflight check")
    parser.add_argument("--engagement", required=True, help="Path to engagement config JSON")
    parser.add_argument("--output", default="preflight-report.json")
    args = parser.parse_args()

    run_preflight(args.engagement, args.output)
