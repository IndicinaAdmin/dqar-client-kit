"""
Stage 1a — Bulk FHIR API conformance.

Tests the server's $export implementation against the SMART Bulk Data
Access IG (https://hl7.org/fhir/uv/bulkdata/):

  1. capability_declares_export  — $export present in CapabilityStatement
  2. kick_off_accepted           — GET $export returns 202 Accepted
  3. content_location_header     — 202 response includes Content-Location
  4. polling_completes           — polling the status URL eventually returns 200
  5. manifest_valid              — manifest has output[] and requiresAccessToken
  6. output_content_type         — output file URLs return application/fhir+ndjson

Skipped automatically (status SKIPPED) if check 1 finds $export not declared
in CapabilityStatement — checks 2–6 are meaningless without it.

Output: data/stage1a-{engagement-name}.json
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.engagement import load_engagement, get_fhir_headers

import requests

POLL_INTERVAL_SECONDS = 5
POLL_MAX_ATTEMPTS = 12  # 1 min total


def _check(name: str, passed: bool, detail: str = "") -> dict:
    return {"check": name, "passed": passed, "detail": detail}


def _check_capability(fhir_base: str, headers: dict) -> tuple:
    """
    Query CapabilityStatement and verify $export is declared.
    Returns (export_declared: bool, detail: str).
    """
    try:
        response = requests.get(
            f"{fhir_base}/metadata",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        capability = response.json()
    except Exception as exc:
        return False, f"CapabilityStatement request failed: {exc}"

    for rest_entry in capability.get("rest", []):
        for op in rest_entry.get("operation", []):
            if op.get("name") == "export":
                return True, "$export operation declared in CapabilityStatement"

    return False, "$export not declared in CapabilityStatement"


def run(
    engagement_path: str,
    output_path: str = None,
) -> dict:
    engagement = load_engagement(engagement_path)

    if output_path is None:
        output_path = f"data/stage1a-{engagement.name}.json"

    print(f"Stage 1a — Bulk FHIR API conformance")
    print(f"  Engagement: {engagement.name} ({engagement.server_type})")
    print(f"  Server    : {engagement.base_url}\n")

    headers = get_fhir_headers(engagement)
    checks = []

    # -----------------------------------------------------------------------
    # Check 1: CapabilityStatement declares $export
    # -----------------------------------------------------------------------
    print("  [1/6] CapabilityStatement declares $export...", end=" ", flush=True)
    export_declared, cap_detail = _check_capability(engagement.fhir_base, headers)
    checks.append(_check("capability_declares_export", export_declared, cap_detail))
    print("OK" if export_declared else "SKIP")

    if not export_declared:
        report = _build_report(engagement, "SKIPPED", checks)
        report["reason"] = cap_detail + " — checks 2–6 skipped"
        _write(report, output_path)
        print(f"\nStage 1a SKIPPED — $export not declared in CapabilityStatement")
        print(f"Report: {output_path}")
        return report

    # -----------------------------------------------------------------------
    # Check 2: Kick off $export
    # -----------------------------------------------------------------------
    print("  [2/6] Kicking off $export...", end=" ", flush=True)
    try:
        kick_off = requests.get(
            f"{engagement.fhir_base}/$export",
            headers={**headers, "Prefer": "respond-async"},
            timeout=30,
        )
        accepted = kick_off.status_code == 202
        checks.append(_check("kick_off_accepted", accepted,
                              f"HTTP {kick_off.status_code}"))
        print("OK" if accepted else f"FAIL (HTTP {kick_off.status_code})")
    except Exception as exc:
        checks.append(_check("kick_off_accepted", False, str(exc)))
        print(f"FAIL ({exc})")
        report = _build_report(engagement, "FAIL", checks)
        _write(report, output_path)
        return report

    # -----------------------------------------------------------------------
    # Check 3: Content-Location header
    # -----------------------------------------------------------------------
    content_location = kick_off.headers.get("Content-Location")
    checks.append(_check("content_location_header", bool(content_location),
                          content_location or "header absent"))
    print(f"  [3/6] Content-Location: {'present' if content_location else 'MISSING'}")

    if not content_location:
        report = _build_report(engagement, "FAIL", checks)
        _write(report, output_path)
        return report

    # -----------------------------------------------------------------------
    # Check 4: Poll for completion
    # -----------------------------------------------------------------------
    print(f"  [4/6] Polling status URL...", end=" ", flush=True)
    status_response = None
    for attempt in range(POLL_MAX_ATTEMPTS):
        status_response = requests.get(content_location, headers=headers, timeout=30)
        if status_response.status_code == 200:
            break
        if status_response.status_code == 202:
            time.sleep(POLL_INTERVAL_SECONDS)
        else:
            break

    polling_ok = status_response is not None and status_response.status_code == 200
    checks.append(_check("polling_completes", polling_ok,
                          f"final status HTTP {status_response.status_code if status_response else 'no response'}"))
    print("OK" if polling_ok else "FAIL")

    if not polling_ok:
        report = _build_report(engagement, "FAIL", checks)
        _write(report, output_path)
        return report

    # -----------------------------------------------------------------------
    # Check 5: Manifest structure
    # -----------------------------------------------------------------------
    try:
        manifest = status_response.json()
    except Exception:
        checks.append(_check("manifest_valid", False, "response not valid JSON"))
        report = _build_report(engagement, "FAIL", checks)
        _write(report, output_path)
        return report

    has_output = "output" in manifest
    has_requires_token = "requiresAccessToken" in manifest
    manifest_ok = has_output and has_requires_token
    checks.append(_check("manifest_valid", manifest_ok,
                          f"output={'present' if has_output else 'MISSING'}, "
                          f"requiresAccessToken={'present' if has_requires_token else 'MISSING'}"))
    print(f"  [5/6] Manifest: {'OK' if manifest_ok else 'FAIL'}")

    # -----------------------------------------------------------------------
    # Check 6: Output file content-type
    # -----------------------------------------------------------------------
    output_files = manifest.get("output", [])[:3]  # spot-check first 3
    ct_ok = True
    ct_detail = []
    for entry in output_files:
        url = entry.get("url")
        if not url:
            continue
        try:
            head = requests.head(url, headers=headers, timeout=15)
            ct = head.headers.get("Content-Type", "")
            ok = "fhir+ndjson" in ct or "ndjson" in ct
            ct_ok = ct_ok and ok
            ct_detail.append(f"{entry.get('type')}: {ct or 'no content-type'}")
        except Exception as exc:
            ct_ok = False
            ct_detail.append(str(exc))

    checks.append(_check("output_content_type", ct_ok, "; ".join(ct_detail)))
    print(f"  [6/6] Output Content-Type: {'OK' if ct_ok else 'FAIL'}")

    overall = "PASS" if all(c["passed"] for c in checks) else "FAIL"
    report = _build_report(engagement, overall, checks)
    _write(report, output_path)
    print(f"\nStage 1a complete: {overall}")
    print(f"Report: {output_path}")
    return report


def _build_report(engagement, status: str, checks: list) -> dict:
    return {
        "report_type": "bulk-fhir-conformance",
        "stage": "1a",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engagement": engagement.name,
        "server_type": engagement.server_type,
        "fhir_server": engagement.base_url,
        "status": status,
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "passed": sum(1 for c in checks if c["passed"]),
            "failed": sum(1 for c in checks if not c["passed"]),
        },
    }


def _write(report: dict, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 1a: Bulk FHIR API conformance")
    parser.add_argument("--engagement", required=True, help="Path to engagement config JSON")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    run(args.engagement, args.output)
