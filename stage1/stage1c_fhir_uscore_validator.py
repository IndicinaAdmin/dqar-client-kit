"""
Stage 1c — FHIR R4 + US Core conformance testing.

Two sequential sub-passes:

  Sub-pass 1c-i:  Base FHIR R4 (4.0.1) structural conformance (no IG).
                  Finding owner: ETL / integration team. CDAR Tier 2.

  Sub-pass 1c-ii: US Core 6.1.0 profile conformance.
                  Finding owner: clinical informatics + integration team. CDAR Tier 2.

Two backend options (--backend):

  hapi-cli (default) — HAPI FHIR Validator CLI. No FHIR server required.
                       Rung 1/2. Requires Java + validator_cli.jar.
                       Download: https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar
                       Set FHIR_VALIDATOR_JAR env var or pass --validator-jar.

  aidbox             — Aidbox $validate REST API. Rung 3+.
                       --engagement must be a path to an engagement config JSON.
                       Issues classified into 1c-i / 1c-ii by profile reference in
                       the OperationOutcome diagnostics/expression.

Two terminology modes for the hapi-cli backend (--tx-mode):

  local (default) — `-tx n/a`. No outbound connection to a terminology server.
                     Validates structure/profile conformance only — terminology
                     binding errors (wrong code from the wrong ValueSet) are NOT
                     caught. Fast, zero external exposure. Use for routine/CI runs.

  live             — Connects to https://tx.fhir.org. Adds full terminology
                     binding validation on top of structure/profile checks.
                     ~20% slower for this validator version and makes outbound
                     calls to a third-party server. Use for the deeper/periodic
                     assessment pass where catching binding errors matters more
                     than speed or network isolation.

Both modes resolve FHIR R4 + US Core IG content from a pinned, project-local
package cache (FHIR_PACKAGE_CACHE_HOME, default <repo>/.fhir-cache/) rather than
the developer's home directory, so behavior is identical across machines/CI.
Pre-warm it with tools/provision_fhir_cache.sh during the Docker build / CI cache
step — never commit it (it's ~550MB; see .gitignore).

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.engagement import load_engagement, get_fhir_headers

import shutil

import requests


def _resolve_java() -> str:
    """Return a working java binary path, checking Homebrew fallbacks on macOS."""
    candidate = os.environ.get("JAVA_BIN", "java")
    # shutil.which skips stubs that exist but aren't executable JVMs
    if shutil.which(candidate):
        try:
            result = subprocess.run(
                [candidate, "-version"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return candidate
        except Exception:
            pass
    for fallback in [
        "/opt/homebrew/opt/openjdk/bin/java",
        "/usr/local/opt/openjdk/bin/java",
    ]:
        if Path(fallback).exists():
            return fallback
    return candidate  # let the caller surface the error


JAVA_BIN = _resolve_java()
VALIDATOR_JAR = os.environ.get("FHIR_VALIDATOR_JAR", "tools/validator_cli.jar")

# Project-local FHIR package cache (FHIR R4 core + US Core + dependencies, ~550MB).
# Pinned via -Duser.home so every machine/CI runner resolves the same package
# versions instead of depending on whatever happens to be in ~/.fhir/packages.
# Never commit this directory — see .gitignore and tools/provision_fhir_cache.sh.
FHIR_PACKAGE_CACHE_HOME = os.environ.get(
    "FHIR_PACKAGE_CACHE_HOME",
    str(Path(__file__).resolve().parents[1] / ".fhir-cache"),
)

TX_SERVERS = {
    "local": "n/a",
    "live":  "https://tx.fhir.org",
}

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
        lines = [ln for ln in f.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
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
        # Collect up to 3 unique example diagnostics per (code, element) pattern
        examples_map: dict = collections.defaultdict(list)
        for i in rt_issues:
            if i["severity"] not in ("error", "fatal"):
                continue
            key = (i["code"], i["element"] or "")
            diag = (i.get("diagnostics") or "").strip()
            if diag and diag not in examples_map[key] and len(examples_map[key]) < 3:
                examples_map[key].append(diag)

        # information issues count toward summary but are excluded from top_errors
        top_errors = [
            {
                "code": code,
                "element": element,
                "count": count,
                "examples": examples_map[(code, element)],
            }
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
    tx_mode: str = None,
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

    if tx_mode:
        report["tx_mode"] = tx_mode
        if tx_mode == "local":
            report["terminology_binding_validation"] = "skipped (local tx-mode — no terminology server connection)"

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
    tx_mode: str = "local",
) -> subprocess.CompletedProcess:
    cmd = [
        java_bin,
        f"-Duser.home={FHIR_PACKAGE_CACHE_HOME}",
        "-Xmx4g", "-jar", validator_jar,
        "-version", FHIR_VERSION,
        "-output", str(output_json),
        "-tx", TX_SERVERS[tx_mode],
    ] + extra_flags
    if ig:
        cmd += ["-ig", ig]
    cmd += [str(f) for f in ndjson_files]
    # Write stdout/stderr to files instead of pipes. The HAPI CLI writes thousands
    # of lines during IG loading; pipe buffers drain too slowly in text mode and
    # cause the subprocess to stall for minutes. File-based I/O has no buffer limit.
    stdout_file = output_json.with_suffix(".stdout")
    stderr_file = output_json.with_suffix(".stderr")
    with open(stdout_file, "w") as sout, open(stderr_file, "w") as serr:
        proc = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, stdout=sout, stderr=serr, timeout=1800
        )
    stdout_content = stdout_file.read_text(errors="replace") if stdout_file.exists() else ""
    stderr_content = stderr_file.read_text(errors="replace") if stderr_file.exists() else ""
    stdout_file.unlink(missing_ok=True)
    stderr_file.unlink(missing_ok=True)
    return subprocess.CompletedProcess(
        cmd, proc.returncode, stdout=stdout_content, stderr=stderr_content
    )


def _extract_validator_version(proc: subprocess.CompletedProcess) -> str:
    """Parse HAPI CLI version from stdout or stderr: 'FHIR Validation tool Version X.Y.Z'."""
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    for line in combined.splitlines():
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


SAMPLE_MAX = 1_000  # Max records per file sent to the HAPI CLI


def _sample_ndjson(src: Path, dest: Path, max_records: int) -> tuple[int, int]:
    """Write up to max_records lines from src to dest. Returns (written, total)."""
    lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    sample = lines[:max_records]
    dest.write_text("\n".join(sample) + "\n", encoding="utf-8")
    return len(sample), len(lines)


def _run_hapi_backend(
    ndjson_files: list,
    engagement_name: str,
    resource_counts: dict,
    timestamp: str,
    output_dir: Path,
    validator_jar: str,
    java_bin: str,
    tx_mode: str = "local",
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

        # Build sampled file list: files over SAMPLE_MAX are capped to avoid OOM/timeout.
        # Empty files (0 records) are skipped — the HAPI CLI throws FHIRException on them.
        sample_dir = tmp / "sampled"
        sample_dir.mkdir()
        sampled_files = []
        sample_meta: dict[str, tuple[int, int]] = {}  # stem → (sampled, total)
        skipped_empty = []
        for f in ndjson_files:
            total = resource_counts.get(f.stem, 0)
            if total == 0:
                skipped_empty.append(f.stem)
                continue
            if total > SAMPLE_MAX:
                dest = sample_dir / f.name
                written, actual_total = _sample_ndjson(f, dest, SAMPLE_MAX)
                sampled_files.append(dest)
                sample_meta[f.stem] = (written, actual_total)
                print(f"    {f.stem}: sampled {written:,} of {actual_total:,}")
            else:
                sampled_files.append(f)

        if skipped_empty:
            print(f"  Skipped {len(skipped_empty)} empty file(s): {', '.join(skipped_empty)}")

        if sample_meta:
            print(f"  Note: {len(sample_meta)} large file(s) sampled at {SAMPLE_MAX:,} records each")

        for sp in SUB_PASSES:
            print(f"  Sub-pass {sp['stage']}: {sp['label']}...", end=" ", flush=True)

            hapi_out = tmp / f"{sp['stage']}-output.json"
            proc = _run_hapi_cli(
                sampled_files, hapi_out, java_bin, str(jar),
                sp["ig"], sp["extra_flags"], tx_mode,
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
                tx_mode=tx_mode,
            )

            if skipped_empty:
                report["skipped_empty_files"] = skipped_empty

            if sample_meta:
                report["sampled_files"] = {
                    stem: {"sampled": s, "total": t}
                    for stem, (s, t) in sample_meta.items()
                }

            # Store combined stdout+stderr tail for crash diagnosis (HAPI CLI uses stdout for progress)
            combined_out = ((proc.stdout or "").strip() + "\n" + (proc.stderr or "").strip()).strip()
            if combined_out or proc.returncode not in (0, None):
                report["validator_stderr_tail"] = combined_out[-500:]

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
    tx_mode: str = "local",
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
    print(f"  Resources : {sum(resource_counts.values()):,} across {len(ndjson_files)} files")
    if backend == "hapi-cli":
        print(f"  Tx mode   : {tx_mode}"
              + ("  (no terminology server connection)" if tx_mode == "local" else "  (connects to tx.fhir.org)"))
    print()

    if backend == "hapi-cli":
        reports = _run_hapi_backend(
            ndjson_files, engagement_name, resource_counts,
            timestamp, out, validator_jar, java_bin, tx_mode,
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
    parser.add_argument(
        "--tx-mode", default="local", choices=["local", "live"],
        help="hapi-cli backend only. 'local' (default): -tx n/a, no outbound "
             "connection, skips terminology binding checks. 'live': connects to "
             "tx.fhir.org for full terminology binding validation, ~20% slower.",
    )
    args = parser.parse_args()

    run(
        ndjson_dir=args.ndjson_dir,
        engagement=args.engagement,
        output_dir=args.output_dir,
        backend=args.backend,
        validator_jar=args.validator_jar,
        java_bin=args.java_bin,
        tx_mode=args.tx_mode,
    )
