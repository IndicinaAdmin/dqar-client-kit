"""
Stage 1b — Resource conformance validator.

Posts each resource from the exported NDJSON files to the FHIR server's
$validate operation and classifies the returned OperationOutcome issues as:
  base-fhir  — core FHIR R4 constraint violation
  us-core    — US Core 6.1.0 profile violation

Works against any engagement (Aidbox or HAPI) — both implement $validate
and return OperationOutcome. Run against multiple engagements to compare
server behaviour on the same dataset.

Output: data/stage1b-{engagement-name}.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.engagement import load_engagement, get_fhir_headers

import requests

US_CORE_PREFIX = "http://hl7.org/fhir/us/core"


def _classify_issue(issue: dict) -> str:
    text = " ".join([
        issue.get("diagnostics", ""),
        json.dumps(issue.get("details", {})),
        " ".join(issue.get("expression", [])),
        " ".join(issue.get("location", [])),
    ])
    return "us-core" if US_CORE_PREFIX in text else "base-fhir"


def validate_resource(resource: dict, base_url: str, headers: dict) -> list[dict]:
    """POST resource to $validate and return classified issues."""
    rt = resource.get("resourceType", "Resource")
    url = f"{base_url}/fhir/{rt}/$validate"

    try:
        response = requests.post(url, json=resource, headers=headers, timeout=30)
    except requests.Timeout:
        return [{"severity": "error", "layer": "base-fhir", "code": "timeout",
                 "diagnostics": f"$validate request timed out for {rt}",
                 "expression": [], "resource_id": resource.get("id")}]

    if response.status_code not in (200, 400, 422):
        return [{"severity": "error", "layer": "base-fhir", "code": "http-error",
                 "diagnostics": f"$validate returned HTTP {response.status_code}",
                 "expression": [], "resource_id": resource.get("id")}]

    try:
        outcome = response.json()
    except Exception:
        return []

    issues = []
    for issue in outcome.get("issue", []):
        if issue.get("severity") not in ("error", "warning", "fatal"):
            continue
        issues.append({
            "resource_id": resource.get("id"),
            "severity": issue.get("severity"),
            "layer": _classify_issue(issue),
            "code": issue.get("code", ""),
            "diagnostics": issue.get("diagnostics", ""),
            "expression": issue.get("expression", []),
        })
    return issues


def run(
    engagement_path: str,
    ndjson_dir: str = "data/export",
    output_path: str = None,
) -> dict:
    engagement = load_engagement(engagement_path)
    ndjson_dir = Path(ndjson_dir)

    if output_path is None:
        output_path = f"data/stage1b-{engagement.name}.json"

    files = sorted(ndjson_dir.glob("*.ndjson"))
    if not files:
        print(f"No .ndjson files found in {ndjson_dir}")
        sys.exit(1)

    print(f"Stage 1b — Resource conformance validation")
    print(f"  Engagement : {engagement.name} ({engagement.server_type})")
    print(f"  Server     : {engagement.base_url}")
    print(f"  NDJSON dir : {ndjson_dir}\n")

    headers = get_fhir_headers(engagement)
    file_results = []
    total_base = 0
    total_uscore = 0
    total_resources = 0

    for ndjson_file in files:
        resource_type = ndjson_file.stem
        print(f"  {resource_type}...", end=" ", flush=True)

        resources = []
        with open(ndjson_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        resources.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        all_issues = []
        for resource in resources:
            all_issues.extend(validate_resource(resource, engagement.base_url, headers))

        base_count = sum(1 for i in all_issues if i["layer"] == "base-fhir")
        uscore_count = sum(1 for i in all_issues if i["layer"] == "us-core")
        total_base += base_count
        total_uscore += uscore_count
        total_resources += len(resources)

        print(f"{len(resources)} resources — {base_count} base-fhir, {uscore_count} us-core issues")

        file_results.append({
            "resource_type": resource_type,
            "file": ndjson_file.name,
            "record_count": len(resources),
            "issue_counts": {"base_fhir": base_count, "us_core": uscore_count},
            "issues": all_issues,
        })

    report = {
        "report_type": "fhir-validation",
        "stage": "1b",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engagement": engagement.name,
        "server_type": engagement.server_type,
        "fhir_server": engagement.base_url,
        "ndjson_dir": str(ndjson_dir.resolve()),
        "summary": {
            "total_resources": total_resources,
            "base_fhir_issues": total_base,
            "us_core_issues": total_uscore,
            "total_issues": total_base + total_uscore,
        },
        "files": file_results,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nStage 1b complete: {total_resources} resources, "
          f"{total_base} base-fhir issues, {total_uscore} us-core issues")
    print(f"Report: {output_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 1b: Resource conformance via $validate")
    parser.add_argument("--engagement", required=True, help="Path to engagement config JSON")
    parser.add_argument("--ndjson-dir", default="data/export")
    parser.add_argument("--output", default=None,
                        help="Output path (default: data/stage1b-{engagement-name}.json)")
    args = parser.parse_args()

    run(args.engagement, args.ndjson_dir, args.output)
