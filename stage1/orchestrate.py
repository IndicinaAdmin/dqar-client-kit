"""
DQAR Stage 1 Assessment — single entry point.

Sequences Stage 1a → 1b → 1c, derives three-tier DQAR findings,
and writes a combined JSON report plus a client-facing HTML report.

Usage:
  # Full run (live FHIR server + local NDJSON):
  python stage1/orchestrate.py \\
      --engagement config/engagements/hapi-r4.json \\
      --ndjson-dir data/export

  # Offline mode (skip Stage 1a — no live server needed):
  python stage1/orchestrate.py \\
      --ndjson-dir data/export \\
      --skip-1a

  # Aidbox $validate backend for Stage 1c:
  python stage1/orchestrate.py \\
      --engagement config/engagements/aidbox-dev.json \\
      --ndjson-dir data/export \\
      --backend aidbox

Outputs (written to --output-dir, default data/reports/):
  {engagement}-{YYYYMMDD-HHMM}.json   combined machine-readable report
  {engagement}-{YYYYMMDD-HHMM}.html   client-facing HTML findings report
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT   = Path(__file__).resolve().parents[1]   # project root
_STAGE1 = Path(__file__).resolve().parent        # stage1/
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_STAGE1))

import stage1a_bulk_fhir_export_preflight as _1a
import stage1b_ndjson_validator           as _1b
import stage1c_fhir_uscore_validator      as _1c
from findings import derive_findings
from report   import render_html
from shared.engagement import load_engagement


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def _stage_ok(r, *, error_key="error_count") -> bool:
    """Return True if the stage result indicates no blocking failures."""
    if r is None:
        return True  # skipped stages don't block
    if "error" in r:
        return False
    s = r.get("summary", {})
    if error_key in s:
        return s[error_key] == 0
    if "files_failed" in s:
        return s["files_failed"] == 0
    explicit = r.get("status", "")
    return explicit in ("PASS", "SKIPPED", "")


def _stage_label(r, *, error_key="error_count") -> str:
    if r is None:
        return "SKIPPED"
    if "error" in r:
        return f"ERROR: {r['error'][:80]}"
    explicit = r.get("status")
    if explicit:
        return explicit
    s = r.get("summary", {})
    if error_key in s:
        ec = s[error_key]
        return "PASS" if ec == 0 else f"FAIL ({ec:,} errors)"
    if "files_failed" in s:
        ff = s["files_failed"]
        return "PASS" if ff == 0 else f"FAIL ({ff} files)"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run(
    engagement_path: str  = None,
    ndjson_dir: str       = "data/export",
    output_dir: str       = "data/reports",
    skip_1a: bool         = False,
    backend: str          = "hapi-cli",
    validator_jar: str    = "tools/validator_cli.jar",
    java_bin: str         = "java",
) -> dict:

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Resolve engagement name
    engagement_name = "offline"
    if engagement_path:
        try:
            engagement_name = load_engagement(engagement_path).name
        except Exception:
            engagement_name = Path(engagement_path).stem

    timestamp = datetime.now(timezone.utc)
    stamp     = timestamp.strftime("%Y%m%d-%H%M")

    _banner(engagement_name, ndjson_dir, backend, out)

    reports: dict = {}

    # -----------------------------------------------------------------------
    # Stage 1a — Bulk FHIR API conformance
    # -----------------------------------------------------------------------
    if skip_1a or not engagement_path:
        _section("Stage 1a — SKIPPED (offline mode or no --engagement)")
        reports["stage1a"] = None
    else:
        _section("Stage 1a — Bulk FHIR API conformance")
        path_1a = str(out / f"stage1a-{engagement_name}.json")
        try:
            reports["stage1a"] = _1a.run(engagement_path=engagement_path, output_path=path_1a)
        except SystemExit:
            reports["stage1a"] = {"status": "ERROR", "error": "Stage 1a exited with error — see output above"}
        except Exception as exc:
            reports["stage1a"] = {"status": "ERROR", "error": str(exc)}
            print(f"  Stage 1a error: {exc}")

    # -----------------------------------------------------------------------
    # Stage 1b — NDJSON structural validation
    # -----------------------------------------------------------------------
    _section("Stage 1b — NDJSON structural validation")
    path_1b = str(out / f"stage1b-{engagement_name}.json")
    try:
        reports["stage1b"] = _1b.run(ndjson_dir=ndjson_dir, output_path=path_1b)
        b_ok = _stage_ok(reports["stage1b"])
    except SystemExit:
        reports["stage1b"] = {"status": "ERROR", "error": "Stage 1b exited — check that NDJSON files exist"}
        b_ok = False
    except Exception as exc:
        reports["stage1b"] = {"status": "ERROR", "error": str(exc)}
        b_ok = False
        print(f"  Stage 1b error: {exc}")

    # -----------------------------------------------------------------------
    # Stage 1c — FHIR R4 + US Core 6.1.0 conformance
    # -----------------------------------------------------------------------
    if not b_ok:
        _section("Stage 1c — BLOCKED (Stage 1b has failures)")
        print("  Structural errors in the NDJSON files would produce misleading conformance results.")
        print("  Fix Stage 1b issues first, then re-run.\n")
        reports["stage1c_i"]  = None
        reports["stage1c_ii"] = None
    else:
        _section("Stage 1c — FHIR R4 + US Core 6.1.0 conformance")
        try:
            r1c = _1c.run(
                ndjson_dir    = ndjson_dir,
                engagement    = engagement_path or engagement_name,
                output_dir    = str(out),
                backend       = backend,
                validator_jar = validator_jar,
                java_bin      = java_bin,
            )
            if isinstance(r1c, list):
                reports["stage1c_i"]  = r1c[0] if len(r1c) > 0 else None
                reports["stage1c_ii"] = r1c[1] if len(r1c) > 1 else None
            else:
                reports["stage1c_i"]  = r1c
                reports["stage1c_ii"] = None
        except SystemExit:
            reports["stage1c_i"]  = {"status": "ERROR", "error": "Stage 1c exited — check validator JAR and Java"}
            reports["stage1c_ii"] = None
        except Exception as exc:
            reports["stage1c_i"]  = {"status": "ERROR", "error": str(exc)}
            reports["stage1c_ii"] = None
            print(f"  Stage 1c error: {exc}")

    # -----------------------------------------------------------------------
    # DQAR findings
    # -----------------------------------------------------------------------
    findings = derive_findings(reports)

    # -----------------------------------------------------------------------
    # Combined JSON report
    # -----------------------------------------------------------------------
    combined = {
        "report_type":  "dqar-stage1-assessment",
        "engagement":   engagement_name,
        "generated_at": timestamp.isoformat(),
        "stage1a":      reports.get("stage1a"),
        "stage1b":      reports.get("stage1b"),
        "stage1c_i":    reports.get("stage1c_i"),
        "stage1c_ii":   reports.get("stage1c_ii"),
        "findings":     findings,
    }
    json_path = out / f"{engagement_name}-{stamp}.json"
    json_path.write_text(json.dumps(combined, indent=2))

    # -----------------------------------------------------------------------
    # HTML report
    # -----------------------------------------------------------------------
    html_path = out / f"{engagement_name}-{stamp}.html"
    try:
        html_path.write_text(render_html(combined), encoding="utf-8")
        html_ok = True
    except ImportError as exc:
        print(f"\n  HTML report skipped: {exc}")
        html_ok = False
    except Exception as exc:
        print(f"\n  HTML report error: {exc}")
        html_ok = False

    # -----------------------------------------------------------------------
    # Terminal summary
    # -----------------------------------------------------------------------
    _print_summary(engagement_name, reports, findings)

    print(f"  JSON : {json_path}")
    if html_ok:
        print(f"  HTML : {html_path}")
    print()

    return combined


# ---------------------------------------------------------------------------
# Terminal output helpers
# ---------------------------------------------------------------------------

def _banner(name: str, ndjson: str, backend: str, out: Path) -> None:
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Indicina DQAR — Stage 1 Assessment                     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Engagement : {name}")
    print(f"  NDJSON dir : {ndjson}")
    print(f"  Backend    : {backend}")
    print(f"  Output dir : {out}")
    print()


def _section(label: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")


def _print_summary(name: str, reports: dict, findings: list) -> None:
    r1a   = reports.get("stage1a")
    r1b   = reports.get("stage1b")
    r1c_i = reports.get("stage1c_i")
    r1c_ii= reports.get("stage1c_ii")

    print()
    W = 58  # inner width between ║ characters
    def _row(prefix: str, value: str) -> str:
        inner = f"  {prefix:<13}{value[:W - 15]:<{W - 15}}"
        return f"║{inner:<{W}}║"

    print("╔" + "═" * W + "╗")
    print(_row("", f"DQAR Stage 1 Summary — {name}"))
    print("╠" + "═" * W + "╣")
    print(_row("Stage 1a",    _stage_label(r1a)))
    print(_row("Stage 1b",    _stage_label(r1b)))
    print(_row("Stage 1c-i",  _stage_label(r1c_i)))
    print(_row("Stage 1c-ii", _stage_label(r1c_ii)))
    print("╠" + "═" * W + "╣")

    if not findings:
        print(_row("Findings", "NONE — all checks passed"))
    else:
        tier_counts = {1: 0, 2: 0, 3: 0}
        for f in findings:
            tier_counts[f["tier"]] += 1
        print(_row("Findings", f"{len(findings)} total"))
        print(_row("  Tier 1",  f"Governance gap          {tier_counts[1]}"))
        print(_row("  Tier 2",  f"Measure data gap        {tier_counts[2]}"))
        print(_row("  Tier 3",  f"Digital readiness gap   {tier_counts[3]}"))

    print("╚" + "═" * W + "╝")
    print()

    if findings:
        print("  Findings:")
        for f in findings:
            sev = f["severity"]
            print(f"  [{f['tier']}] [{sev:6s}] {f['title']}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DQAR Stage 1 Assessment — Bulk FHIR API + NDJSON + US Core conformance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full run against a live FHIR server:
  python stage1/orchestrate.py --engagement config/engagements/hapi-r4.json --ndjson-dir data/export

  # Offline — just validate local NDJSON (no server needed):
  python stage1/orchestrate.py --ndjson-dir data/export --skip-1a

  # Aidbox backend (Rung 3+):
  python stage1/orchestrate.py --engagement config/engagements/aidbox-dev.json --backend aidbox
""",
    )
    parser.add_argument(
        "--engagement", default=None,
        help="Path to engagement config JSON (required for Stage 1a; optional for offline mode)",
    )
    parser.add_argument(
        "--ndjson-dir", default="data/export",
        help="Directory containing exported NDJSON files (default: data/export)",
    )
    parser.add_argument(
        "--output-dir", default="data/reports",
        help="Directory for JSON + HTML reports (default: data/reports)",
    )
    parser.add_argument(
        "--skip-1a", action="store_true",
        help="Skip Stage 1a (Bulk FHIR API check); run 1b + 1c against local NDJSON only",
    )
    parser.add_argument(
        "--backend", default="hapi-cli", choices=["hapi-cli", "aidbox"],
        help="Stage 1c conformance backend (default: hapi-cli). aidbox requires --engagement.",
    )
    parser.add_argument(
        "--validator-jar", default="tools/validator_cli.jar",
        help="Path to HAPI Validator CLI JAR (hapi-cli backend only)",
    )
    parser.add_argument(
        "--java-bin", default="java",
        help="Java binary (hapi-cli backend only)",
    )
    args = parser.parse_args()

    run(
        engagement_path = args.engagement,
        ndjson_dir      = args.ndjson_dir,
        output_dir      = args.output_dir,
        skip_1a         = args.skip_1a,
        backend         = args.backend,
        validator_jar   = args.validator_jar,
        java_bin        = args.java_bin,
    )
