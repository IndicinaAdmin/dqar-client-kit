"""
Stage 1a — NDJSON structural validator.

Checks (in order, stops per-file on UTF-8 failure):
  1. utf8_decodable        — file opens as UTF-8 without errors
  2. no_empty_lines_only   — file has at least one non-blank line (empty = data gap)
  3. all_lines_valid_json  — every non-blank line parses as JSON (catches truncated lines)
  4. resource_type_present — every parsed object has a resourceType field
  5. filename_matches_type — resourceType values match the filename stem
                             (e.g. Patient.ndjson must contain only Patient resources)

Output: data/stage1a-report.json — aggregate counts only, zero PHI.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def check_file(ndjson_path: Path) -> dict:
    declared_type = ndjson_path.stem  # e.g. "Patient" from "Patient.ndjson"

    result = {
        "file": ndjson_path.name,
        "resource_type_declared": declared_type,
        "record_count": 0,
        "empty": False,
        "checks": {
            "utf8_decodable": False,
            "no_empty_lines_only": False,
            "all_lines_valid_json": False,
            "resource_type_present": False,
            "filename_matches_type": False,
        },
        "issue_counts": {
            "utf8_errors": 0,
            "json_parse_errors": 0,
            "missing_resource_type": 0,
            "resource_type_mismatches": 0,
        },
        "passed": False,
    }

    # 1. UTF-8 decodable
    try:
        raw = ndjson_path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        result["issue_counts"]["utf8_errors"] = 1
        return result

    result["checks"]["utf8_decodable"] = True

    # 2. Non-empty
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        result["empty"] = True
        return result

    result["checks"]["no_empty_lines_only"] = True

    # 3. All lines valid JSON (json.loads catches truncated lines)
    parsed = []
    json_errors = 0
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            json_errors += 1

    result["issue_counts"]["json_parse_errors"] = json_errors
    result["checks"]["all_lines_valid_json"] = json_errors == 0

    if not parsed:
        return result

    # 4. resourceType present on every resource
    missing_rt = sum(1 for obj in parsed if "resourceType" not in obj)
    result["issue_counts"]["missing_resource_type"] = missing_rt
    result["checks"]["resource_type_present"] = missing_rt == 0

    # 5. Filename stem matches actual resourceType values
    mismatches = sum(
        1 for obj in parsed
        if obj.get("resourceType") and obj["resourceType"] != declared_type
    )
    result["issue_counts"]["resource_type_mismatches"] = mismatches
    result["checks"]["filename_matches_type"] = mismatches == 0

    result["record_count"] = len(parsed)
    result["passed"] = all(result["checks"].values())
    return result


def run(
    ndjson_dir: str = "data/export",
    output_path: str = "data/stage1a-report.json",
) -> dict:
    ndjson_dir = Path(ndjson_dir)
    files = sorted(ndjson_dir.glob("*.ndjson"))

    if not files:
        print(f"No .ndjson files found in {ndjson_dir}")
        sys.exit(1)

    print(f"Stage 1a — NDJSON structural validation")
    print(f"  {len(files)} files in {ndjson_dir}\n")

    file_results = []
    total_records = 0
    files_passed = 0
    files_empty = 0

    for ndjson_file in files:
        result = check_file(ndjson_file)
        file_results.append(result)
        total_records += result["record_count"]

        if result["empty"]:
            files_empty += 1
            status = "EMPTY"
        elif result["passed"]:
            files_passed += 1
            status = "PASS"
        else:
            failed_checks = [k for k, v in result["checks"].items() if not v]
            status = f"FAIL ({', '.join(failed_checks)})"

        print(f"  {result['file']:35s}  {result['record_count']:>6} records  {status}")

    files_failed = len(files) - files_passed - files_empty

    report = {
        "report_type": "ndjson-structural",
        "stage": "1a",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ndjson_dir": str(ndjson_dir.resolve()),
        "summary": {
            "files_checked": len(files),
            "files_passed": files_passed,
            "files_failed": files_failed,
            "files_empty": files_empty,
            "total_records": total_records,
            "total_json_parse_errors": sum(
                r["issue_counts"]["json_parse_errors"] for r in file_results
            ),
            "total_missing_resource_type": sum(
                r["issue_counts"]["missing_resource_type"] for r in file_results
            ),
            "total_resource_type_mismatches": sum(
                r["issue_counts"]["resource_type_mismatches"] for r in file_results
            ),
        },
        "files": file_results,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nStage 1a complete: {files_passed} passed, {files_failed} failed, {files_empty} empty")
    print(f"Report: {output_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 1a: NDJSON structural validation")
    parser.add_argument("--ndjson-dir", default="data/export")
    parser.add_argument("--output", default="data/stage1a-report.json")
    args = parser.parse_args()

    run(args.ndjson_dir, args.output)
