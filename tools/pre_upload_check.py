"""
Pre-upload checks for Synthea FHIR transaction bundles.

Two checks:
  1. Bundle structure — flags POST entries that have a resource.id set.
     These are idempotency hazards: POST tries to INSERT every time, so
     retries after a timeout cause duplicate-key errors. The uploader
     converts them to PUT automatically, but this check documents the issue.

  2. US Core conformance — runs the HL7 FHIR Validator against every resource
     extracted from the bundles, flagging violations before they cause upload
     failures.

Requires the HL7 FHIR Validator CLI JAR at tools/validator_cli.jar
(or set FHIR_VALIDATOR_JAR env var). Download from:
  https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

JAVA_BIN = os.environ.get("JAVA_BIN", "/opt/homebrew/opt/java/bin/java")
VALIDATOR_JAR = os.environ.get("FHIR_VALIDATOR_JAR", "tools/validator_cli.jar")
FHIR_VERSION = "4.0.1"
US_CORE_IG = "hl7.fhir.us.core#6.1.0"
US_CORE_PREFIX = "http://hl7.org/fhir/us/core"


# ---------------------------------------------------------------------------
# Check 1: bundle structure
# ---------------------------------------------------------------------------

def check_bundle_structure(bundle_path: Path) -> list[dict]:
    """
    Returns an issue for every POST entry that also has resource.id set.
    These should be PUT /{resourceType}/{id} to be idempotent.
    """
    with open(bundle_path) as f:
        bundle = json.load(f)

    issues = []
    for i, entry in enumerate(bundle.get("entry", [])):
        req = entry.get("request", {})
        resource = entry.get("resource", {})
        if req.get("method") == "POST" and resource.get("id"):
            rt = resource.get("resourceType", "Unknown")
            rid = resource.get("id")
            issues.append({
                "check": "structure",
                "entry_index": i,
                "resource_type": rt,
                "resource_id": rid,
                "severity": "warning",
                "message": (
                    f"Entry {i} uses POST {rt} but resource.id={rid} is set. "
                    f"Should be PUT {rt}/{rid} for idempotent uploads."
                ),
            })
    return issues


# ---------------------------------------------------------------------------
# Check 2: US Core conformance (HL7 FHIR Validator)
# ---------------------------------------------------------------------------

def _classify_issue(issue: dict) -> str:
    text = " ".join([
        issue.get("diagnostics", ""),
        json.dumps(issue.get("details", {})),
        " ".join(issue.get("expression", [])),
        " ".join(issue.get("location", [])),
    ])
    return "us-core" if US_CORE_PREFIX in text else "base-fhir"


def check_conformance(bundle_path: Path, validator_jar: Path) -> list[dict]:
    """
    Extract all resources from the bundle, run the HL7 FHIR Validator
    against them, and return classified issues.
    """
    with open(bundle_path) as f:
        bundle = json.load(f)

    resources = [
        entry["resource"]
        for entry in bundle.get("entry", [])
        if "resource" in entry
    ]

    if not resources:
        return []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_files = []
        for i, resource in enumerate(resources):
            rid = resource.get("id", str(i))
            rt = resource.get("resourceType", "Resource")
            rpath = tmpdir / f"{i}_{rt}_{rid}.json"
            with open(rpath, "w") as f:
                json.dump(resource, f)
            input_files.append((rpath, resource))

        output_path = tmpdir / "results.json"
        cmd = [
            JAVA_BIN, "-jar", str(validator_jar),
            "-version", FHIR_VERSION,
            "-ig", US_CORE_IG,
            "-output", str(output_path),
        ] + [str(p) for p, _ in input_files]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if not output_path.exists():
            return [{
                "check": "conformance",
                "severity": "error",
                "layer": "base-fhir",
                "resource_type": None,
                "resource_id": None,
                "message": f"Validator produced no output. stderr: {proc.stderr[-300:]}",
            }]

        with open(output_path) as f:
            data = json.load(f)

        issues = []
        outcomes = data if isinstance(data, list) else [data]
        for outcome in outcomes:
            if outcome.get("resourceType") != "OperationOutcome":
                continue
            for issue in outcome.get("issue", []):
                if issue.get("severity") not in ("error", "warning", "fatal"):
                    continue
                # Match back to resource via location/expression referencing the temp filename
                matched_rt, matched_id = None, None
                for loc in issue.get("location", []) + issue.get("expression", []):
                    for rpath, resource in input_files:
                        if rpath.stem in loc:
                            matched_rt = resource.get("resourceType")
                            matched_id = resource.get("id")
                            break

                issues.append({
                    "check": "conformance",
                    "severity": issue.get("severity"),
                    "layer": _classify_issue(issue),
                    "resource_type": matched_rt,
                    "resource_id": matched_id,
                    "message": issue.get("diagnostics", ""),
                })

        return issues


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_pre_upload_check(
    synthea_dir: str = "data/synthea/fhir",
    output_path: str = "data/pre-upload-check.json",
    skip_conformance: bool = False,
    validator_jar: str = VALIDATOR_JAR,
) -> dict:
    bundle_dir = Path(synthea_dir)
    bundles = sorted(bundle_dir.glob("*.json"))

    if not bundles:
        print(f"No bundles found in {bundle_dir}")
        sys.exit(1)

    jar = Path(validator_jar)
    if not skip_conformance and not jar.exists():
        print(
            f"HL7 FHIR Validator JAR not found at {jar}. "
            "Run with --skip-conformance to do structure checks only, or download:\n"
            "  https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar"
        )
        sys.exit(1)

    print(f"Pre-upload check: {len(bundles)} bundles in {bundle_dir}")
    if skip_conformance:
        print("  (conformance check skipped — no validator JAR)\n")
    else:
        print(f"  IG: {US_CORE_IG}  |  FHIR: {FHIR_VERSION}\n")

    file_results = []
    total_structure = 0
    total_conformance = 0

    for i, bundle_path in enumerate(bundles, 1):
        print(f"  [{i}/{len(bundles)}] {bundle_path.name}...", end=" ", flush=True)

        structure_issues = check_bundle_structure(bundle_path)
        conformance_issues = check_conformance(bundle_path, jar) if not skip_conformance else []

        all_issues = structure_issues + conformance_issues
        total_structure += len(structure_issues)
        total_conformance += len(conformance_issues)

        print(
            f"{len(structure_issues)} structure, {len(conformance_issues)} conformance"
            if all_issues else "OK"
        )

        if all_issues:
            file_results.append({
                "file": bundle_path.name,
                "issues": all_issues,
            })

    report = {
        "report_type": "pre-upload-check",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "synthea_dir": str(bundle_dir.resolve()),
        "ig_version": US_CORE_IG,
        "fhir_version": FHIR_VERSION,
        "bundles_checked": len(bundles),
        "bundles_with_issues": len(file_results),
        "summary": {
            "structure_issues": total_structure,
            "conformance_issues": total_conformance,
            "total_issues": total_structure + total_conformance,
        },
        "files": file_results,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nPre-upload check complete.")
    print(f"  {total_structure} structure issues, {total_conformance} conformance issues")
    print(f"  {len(file_results)}/{len(bundles)} bundles have issues")
    print(f"Report: {output_path}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-upload bundle checks")
    parser.add_argument("--synthea-dir", default="data/synthea/fhir")
    parser.add_argument("--output", default="data/pre-upload-check.json")
    parser.add_argument("--skip-conformance", action="store_true",
                        help="Run structure checks only (no HL7 validator needed)")
    parser.add_argument("--validator-jar", default=VALIDATOR_JAR)
    args = parser.parse_args()

    run_pre_upload_check(
        synthea_dir=args.synthea_dir,
        output_path=args.output,
        skip_conformance=args.skip_conformance,
        validator_jar=args.validator_jar,
    )
