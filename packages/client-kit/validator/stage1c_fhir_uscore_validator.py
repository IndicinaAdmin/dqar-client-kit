"""
Stage 1c — FHIR R4 + US Core conformance testing.

Two sequential sub-passes:

  Sub-pass 1c-i:  Base FHIR R4 (4.0.1) structural conformance (no IG).
                  Finding owner: ETL / integration team. DQAR Tier 2.

  Sub-pass 1c-ii: US Core 6.1.0 profile conformance.
                  Finding owner: clinical informatics + integration team. DQAR Tier 2.

Two backend options (--backend):

  hapi-cli (default) — HAPI FHIR Validator CLI. No FHIR server required.
                       Rung 1/2. Requires Java + validator_cli.jar.
                       Download: https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar
                       Set FHIR_VALIDATOR_JAR env var or pass --validator-jar.

  aidbox             — Aidbox $validate REST API. Rung 3+.
                       --engagement must be a path to an engagement config JSON.
                       Issues classified into 1c-i / 1c-ii by profile reference in
                       the OperationOutcome diagnostics/expression.

Outputs (written to --output-dir, default data/):
  stage1c-i-{engagement}.json   — base FHIR R4 results
  stage1c-ii-{engagement}.json  — US Core 6.1.0 results
"""

import argparse
import collections
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.engagement import load_engagement, get_fhir_headers

import requests

JAVA_BIN = os.environ.get("JAVA_BIN", "java")
VALIDATOR_JAR = os.environ.get("FHIR_VALIDATOR_JAR", "tools/validator_cli.jar")
FHIR_VERSION = "4.0.1"
US_CORE_IG = "hl7.fhir.us.core#6.1.0"
US_CORE_VERSION = "6.1.0"
US_CORE_PREFIX = "http://hl7.org/fhir/us/core"

SUB_PASSES = [
    {
        "stage":       "1c-i",
        "label":       "Base FHIR R4 (no IG)",
        "ig":          None,
        "extra_flags": ["-no-extensible-binding-warnings"],
    },
    {
        "stage":       "1c-ii",
        "label":       f"US Core {US_CORE_VERSION}",
        "ig":          US_CORE_IG,
        "extra_flags": [],
    },
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve_engagement_name(engagement_arg: str) -> str:
    """Accept either an engagement config path (reads .name) or a plain string."""
    p = Path(engagement_arg)
    if p.exists() and p.suffix == ".json":
        try:
            return json.loads(p.read_text())["name"]
        except Exception:
            pass
    return engagement_arg


def _count_resources(ndjson_files: list) -> dict:
    """Line count per ndjson file (= resource count)."""
    counts = {}
    for f in ndjson_files:
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        counts[f.stem] = len(lines)
    return counts


def _resource_type_from_issue(issue: dict, valid_stems: set) -> str:
    """
    Infer resource type from a HAPI OperationOutcome issue.
    Tries expression first ("Patient.birthDate" → "Patient"),
    then location strings ("Patient.ndjson line 5" → "Patient").
    """
    for expr in issue.get("expression", []):
        segment = expr.split(".")[0].split("[")[0]
        if segment in valid_stems:
            return segment
    for loc in issue.get("location", []):
        for stem in valid_stems:
            if stem in loc:
                return stem
    return "unknown"


def _by_resource_type(issues: list, resource_counts: dict) -> list:
    grouped = collections.defaultdict(list)
    for issue in issues:
        grouped[issue["resource_type"]].append(issue)

    all_rts = sorted(set(resource_counts) | set(grouped))
    result = []
    for rt in all_rts:
        rt_issues = grouped.get(rt, [])
        errors = sum(1 for i in rt_issues if i["severity"] in ("error", "fatal"))
        warnings = sum(1 for i in rt_issues if i["severity"] == "warning")

        error_counter = collections.Counter(
            (i["code"], i["element"] or "")
            for i in rt_issues if i["severity"] in ("error", "fatal")
        )
        # information issues count toward summary but are excluded from top_errors
        top_errors = [
            {"code": code, "element": element, "count": count}
            for (code, element), count in error_counter.most_common(10)
        ]

        result.append({
            "resource_type": rt,
            "total": resource_counts.get(rt, 0),
            "errors": errors,
            "warnings": warnings,
            "top_errors": top_errors,
        })
    return result


def _build_report(
    sub_pass: dict,
    engagement_name: str,
    issues: list,
    resource_counts: dict,
    timestamp: str,
    validator: str,
    validator_version: str = None,
) -> dict:
    errors = sum(1 for i in issues if i["severity"] in ("error", "fatal"))
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    info_count = sum(1 for i in issues if i["severity"] == "information")

    report = {
        "report_type": "fhir-conformance",
        "stage": sub_pass["stage"],
        "validator": validator,
        "fhir_version": FHIR_VERSION,
        "engagement": engagement_name,
        "run_timestamp": timestamp,
        "summary": {
            "total_resources": sum(resource_counts.values()),
            "error_count": errors,
            "warning_count": warnings,
            "information_count": info_count,
        },
        "by_resource_type": _by_resource_type(issues, resource_counts),
    }

    if validator_version:
        report["validator_version"] = validator_version

    if sub_pass["ig"]:
        report["ig_version"] = sub_pass["ig"]
        report["us_core_version"] = US_CORE_VERSION

    return report


# ---------------------------------------------------------------------------
# HAPI CLI backend
# ---------------------------------------------------------------------------

def _run_hapi_cli(
    ndjson_files: list,
    output_json: Path,
    java_bin: str,
    validator_jar: str,
    ig: str,
    extra_flags: list,
) -> subprocess.CompletedProcess:
    cmd = [
        java_bin, "-jar", validator_jar,
        "-version", FHIR_VERSION,
        "-output", str(output_json),
    ] + extra_flags
    if ig:
        cmd += ["-ig", ig]
    cmd += [str(f) for f in ndjson_files]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=1800)


def _extract_validator_version(proc: subprocess.CompletedProcess) -> str:
    """Parse HAPI CLI version from stderr: 'FHIR Validation tool Version X.Y.Z'."""
    for line in (proc.stderr or "").splitlines():
        if "Version" in line:
            parts = line.split("Version", 1)
            if len(parts) > 1:
                return parts[1].strip().split()[0]
    return "unknown"


def _parse_hapi_output(output_json: Path, valid_stems: set) -> list:
    """
    Parse HAPI CLI OperationOutcome JSON output into a flat issue list.
    Returns a synthetic fatal issue if the output file is absent (CLI crash).
    """
    if not output_json.exists():
        return [{
            "severity": "fatal",
            "code": "exception",
            "element": None,
            "diagnostics": "HAPI CLI produced no output — check stderr in report",
            "resource_type": "unknown",
        }]

    data = json.loads(output_json.read_text())
    outcomes = data if isinstance(data, list) else [data]

    issues = []
    for outcome in outcomes:
        if outcome.get("resourceType") != "OperationOutcome":
            continue
        for issue in outcome.get("issue", []):
            severity = issue.get("severity")
            if severity not in ("error", "warning", "fatal", "information"):
                continue
            expression = issue.get("expression", [])
            issues.append({
                "severity": severity,
                "code": issue.get("code", ""),
                "element": expression[0] if expression else None,
                "diagnostics": issue.get("diagnostics", ""),
                "resource_type": _resource_type_from_issue(issue, valid_stems),
            })
    return issues


def _run_hapi_backend(
    ndjson_files: list,
    engagement_name: str,
    resource_counts: dict,
    timestamp: str,
    output_dir: Path,
    validator_jar: str,
    java_bin: str,
) -> list:
    jar = Path(validator_jar)
    if not jar.exists():
        print(
            f"HAPI Validator CLI not found at {jar}.\n"
            f"Download: https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar\n"
            f"Or set FHIR_VALIDATOR_JAR env var."
        )
        sys.exit(1)

    valid_stems = {f.stem for f in ndjson_files}
    reports = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        validator_version = None

        for sp in SUB_PASSES:
            print(f"  Sub-pass {sp['stage']}: {sp['label']}...", end=" ", flush=True)

            hapi_out = tmp / f"{sp['stage']}-output.json"
            proc = _run_hapi_cli(
                ndjson_files, hapi_out, java_bin, str(jar),
                sp["ig"], sp["extra_flags"],
            )

            if validator_version is None:
                validator_version = _extract_validator_version(proc)

            issues = _parse_hapi_output(hapi_out, valid_stems)
            errors = sum(1 for i in issues if i["severity"] in ("error", "fatal"))
            warnings = sum(1 for i in issues if i["severity"] == "warning")
            print(f"{errors} errors, {warnings} warnings")

            report = _build_report(
                sp, engagement_name, issues, resource_counts,
                timestamp, validator="hapi-cli", validator_version=validator_version,
            )

            # Include stderr tail on non-zero exit so normal runs stay clean
            if proc.returncode not in (0, None) and proc.stderr:
                report["validator_stderr_tail"] = proc.stderr[-500:]

            report_path = output_dir / f"stage{sp['stage']}-{engagement_name}.json"
            report_path.write_text(json.dumps(report, indent=2))
            print(f"    Report: {report_path}")
            reports.append(report)

    return reports


# ---------------------------------------------------------------------------
# Aidbox $validate backend
# ---------------------------------------------------------------------------

def _classify_issue_layer(issue: dict) -> str:
    """
    Classify an OperationOutcome issue as 'us-core' or 'base-fhir' by checking
    whether any US Core profile URL appears in the diagnostics or expression.
    """
    text = " ".join([
        issue.get("diagnostics", ""),
        json.dumps(issue.get("details", {})),
        " ".join(issue.get("expression", [])),
        " ".join(issue.get("location", [])),
    ])
    return "us-core" if US_CORE_PREFIX in text else "base-fhir"


def _validate_resource_api(resource: dict, base_url: str, headers: dict, valid_stems: set) -> list:
    """POST resource to $validate and return classified issues."""
    rt = resource.get("resourceType", "Resource")
    url = f"{base_url}/fhir/{rt}/$validate"

    try:
        response = requests.post(url, json=resource, headers=headers, timeout=30)
    except requests.Timeout:
        return [{
            "severity": "error", "code": "timeout", "element": None,
            "diagnostics": f"$validate timed out for {rt}",
            "resource_type": rt, "layer": "base-fhir",
        }]

    if response.status_code not in (200, 400, 422):
        return [{
            "severity": "error", "code": "http-error", "element": None,
            "diagnostics": f"$validate returned HTTP {response.status_code}",
            "resource_type": rt, "layer": "base-fhir",
        }]

    try:
        outcome = response.json()
    except Exception:
        return []

    issues = []
    for issue in outcome.get("issue", []):
        severity = issue.get("severity")
        if severity not in ("error", "warning", "fatal", "information"):
            continue
        expression = issue.get("expression", [])
        issues.append({
            "severity": severity,
            "code": issue.get("code", ""),
            "element": expression[0] if expression else None,
            "diagnostics": issue.get("diagnostics", ""),
            "resource_type": _resource_type_from_issue(issue, valid_stems),
            "layer": _classify_issue_layer(issue),
        })
    return issues


def _run_aidbox_backend(
    ndjson_files: list,
    engagement_name: str,
    resource_counts: dict,
    timestamp: str,
    output_dir: Path,
    engagement_path: str,
) -> list:
    engagement = load_engagement(engagement_path)
    headers = get_fhir_headers(engagement)
    valid_stems = {f.stem for f in ndjson_files}

    print(f"  Server: {engagement.base_url} ({engagement.server_type})")

    all_issues = []
    for ndjson_file in ndjson_files:
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

        file_issues = []
        for resource in resources:
            file_issues.extend(_validate_resource_api(resource, engagement.base_url, headers, valid_stems))

        all_issues.extend(file_issues)
        base_count = sum(1 for i in file_issues if i["layer"] == "base-fhir")
        us_core_count = sum(1 for i in file_issues if i["layer"] == "us-core")
        print(f"{len(resources)} resources — {base_count} base-fhir, {us_core_count} us-core issues")

    # Split classified issues into the two sub-pass reports
    layer_map = {"1c-i": "base-fhir", "1c-ii": "us-core"}
    reports = []
    for sp in SUB_PASSES:
        sp_issues = [i for i in all_issues if i.get("layer") == layer_map[sp["stage"]]]

        report = _build_report(
            sp, engagement_name, sp_issues, resource_counts,
            timestamp, validator="aidbox",
        )

        report_path = output_dir / f"stage{sp['stage']}-{engagement_name}.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"    Report: {report_path}")
        reports.append(report)

    return reports


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run(
    ndjson_dir: str = "data/export",
    engagement: str = "unknown",
    output_dir: str = "data",
    backend: str = "hapi-cli",
    validator_jar: str = VALIDATOR_JAR,
    java_bin: str = JAVA_BIN,
) -> list:
    ndjson_path = Path(ndjson_dir)
    ndjson_files = sorted(ndjson_path.glob("*.ndjson"))
    if not ndjson_files:
        print(f"No .ndjson files found in {ndjson_dir}")
        sys.exit(1)

    engagement_name = _resolve_engagement_name(engagement)
    resource_counts = _count_resources(ndjson_files)
    timestamp = datetime.now(timezone.utc).isoformat()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Stage 1c — FHIR R4 + US Core conformance testing")
    print(f"  Engagement: {engagement_name}")
    print(f"  Backend   : {backend}")
    print(f"  NDJSON dir: {ndjson_path}")
    print(f"  Resources : {sum(resource_counts.values()):,} across {len(ndjson_files)} files\n")

    if backend == "hapi-cli":
        reports = _run_hapi_backend(
            ndjson_files, engagement_name, resource_counts,
            timestamp, out, validator_jar, java_bin,
        )
    elif backend == "aidbox":
        if not Path(engagement).exists():
            print(
                f"--backend aidbox requires --engagement to be a path to an engagement "
                f"config JSON file. Got: '{engagement}'"
            )
            sys.exit(1)
        reports = _run_aidbox_backend(
            ndjson_files, engagement_name, resource_counts,
            timestamp, out, engagement,
        )
    else:
        print(f"Unknown backend '{backend}'. Choose hapi-cli or aidbox.")
        sys.exit(1)

    print(f"\nStage 1c complete.")
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 1c: FHIR R4 + US Core conformance testing"
    )
    parser.add_argument(
        "--ndjson-dir", default="data/export",
        help="Directory containing exported ndjson files (default: data/export)",
    )
    parser.add_argument(
        "--engagement", default="unknown",
        help="Engagement name or path to engagement config JSON. "
             "A config path is required when using --backend aidbox.",
    )
    parser.add_argument(
        "--backend", default="hapi-cli", choices=["hapi-cli", "aidbox"],
        help="Conformance testing backend (default: hapi-cli)",
    )
    parser.add_argument(
        "--output-dir", default="data",
        help="Directory for output reports (default: data/)",
    )
    parser.add_argument(
        "--validator-jar", default=VALIDATOR_JAR,
        help=f"Path to HAPI Validator CLI JAR — hapi-cli backend only (default: {VALIDATOR_JAR})",
    )
    parser.add_argument(
        "--java-bin", default=JAVA_BIN,
        help=f"Java binary — hapi-cli backend only (default: {JAVA_BIN})",
    )
    args = parser.parse_args()

    run(
        ndjson_dir=args.ndjson_dir,
        engagement=args.engagement,
        output_dir=args.output_dir,
        backend=args.backend,
        validator_jar=args.validator_jar,
        java_bin=args.java_bin,
    )
