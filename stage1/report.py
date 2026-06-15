"""
Renders the DQAR Stage 1 HTML report from a combined assessment report dict.
Requires jinja2: pip install -e '.[report]'
"""

from datetime import datetime, timezone
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def render_html(report: dict) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        raise ImportError(
            "jinja2 is required for HTML reports.\n"
            "Install it: pip install -e '.[report]'"
        )

    import json as _json

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["fmt"] = lambda x: f"{x:,}" if isinstance(x, int) else (x or "—")

    ctx = _build_context(report)
    ctx["report_json"] = _json.dumps(report, indent=2)
    return env.get_template("report.html").render(**ctx)


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------

def _build_context(report: dict) -> dict:
    ts = report.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(ts)
        date_str = dt.strftime("%B %d, %Y")
        time_str = dt.strftime("%H:%M UTC")
    except Exception:
        date_str, time_str = ts, ""

    s1a = report.get("stage1a")
    s1a_ii = report.get("stage1a_ii")
    s1b = report.get("stage1b")
    s1c_i = report.get("stage1c_i")
    s1c_ii = report.get("stage1c_ii")

    stage_cards = [
        _card_1a_i(s1a),
        _card_1a_ii(s1a_ii),
        _card_1b(s1b),
        _card_1c(s1c_i, "1c-i", "Base FHIR R4 (4.0.1)"),
        _card_1c(s1c_ii, "1c-ii", "US Core 6.1.0"),
    ]

    findings = report.get("findings", [])
    tier1 = [f for f in findings if f["tier"] == 1]
    tier2 = [f for f in findings if f["tier"] == 2]
    tier3 = [f for f in findings if f["tier"] == 3]

    overall = "PASS" if not findings else "FINDINGS"
    # Degrade to INCOMPLETE if 1c didn't run, errored, or validator crashed
    if s1c_i is None and s1b and s1b.get("summary", {}).get("files_failed", 0) > 0:
        overall = "INCOMPLETE"
    if (s1c_i and s1c_i.get("status") == "ERROR") or (s1c_ii and s1c_ii.get("status") == "ERROR"):
        overall = "INCOMPLETE"
    if _validator_crash_reason(s1c_i) or _validator_crash_reason(s1c_ii):
        overall = "INCOMPLETE"

    # Merged 1c table: one row per resource type combining 1c-i and 1c-ii error counts
    rt_table = _merge_1c_by_rt(s1c_i, s1c_ii)

    return {
        "engagement": report.get("engagement", "Unknown"),
        "date_str": date_str,
        "time_str": time_str,
        "overall": overall,
        "stage_cards": stage_cards,
        "findings": findings,
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
        "stage1a_checks": s1a.get("checks", []) if s1a and "checks" in s1a else [],
        "stage1a_server": s1a.get("fhir_server", "") if s1a else "",
        "stage1a2_checks": s1a_ii.get("checks", []) if s1a_ii and "checks" in s1a_ii else [],
        "stage1a2_summary": s1a_ii.get("summary", {}) if s1a_ii else {},
        "stage1a2_resource_types": s1a_ii.get("resource_types", []) if s1a_ii else [],
        "no_findings_detail": _no_findings_detail(stage_cards),
        "stage1b_files": s1b.get("files", []) if s1b else [],
        "stage1b_summary": s1b.get("summary", {}) if s1b else {},
        "stage1c_i_summary": s1c_i.get("summary", {}) if s1c_i else {},
        "stage1c_ii_summary": s1c_ii.get("summary", {}) if s1c_ii else {},
        "stage1c_skipped_empty": (
            (s1c_i.get("skipped_empty_files") if s1c_i else None) or
            (s1c_ii.get("skipped_empty_files") if s1c_ii else None) or []
        ),
        "rt_table": rt_table,
    }


def _status(r, key_errors="error_count") -> str:
    if r is None:
        return "SKIPPED"
    if "error" in r:
        return "ERROR"
    explicit = r.get("status")
    if explicit in ("PASS", "FAIL", "SKIPPED", "BLOCKED", "ERROR", "N/A"):
        return explicit
    # Infer from summary
    s = r.get("summary", {})
    if key_errors in s:
        return "PASS" if s[key_errors] == 0 else "FAIL"
    if "files_failed" in s:
        return "PASS" if s["files_failed"] == 0 else "FAIL"
    return "UNKNOWN"


def _card_1a_i(r) -> dict:
    if r is None:
        return {"stage": "1a-i", "label": "Bulk FHIR API Server", "status": "N/A", "detail": "No FHIR server URL provided"}
    st = _status(r)
    checks = r.get("checks", [])
    passed = sum(1 for c in checks if c.get("passed"))
    return {
        "stage": "1a-i",
        "label": "Bulk FHIR API Server",
        "status": st,
        "detail": f"{passed}/{len(checks)} checks passed",
        "server": r.get("fhir_server", ""),
    }


def _card_1a_ii(r) -> dict:
    if r is None:
        return {"stage": "1a-ii", "label": "Bulk FHIR Extract Packaging", "status": "N/A", "detail": "No files uploaded"}
    st = _status(r)
    if st == "ERROR":
        return {"stage": "1a-ii", "label": "Bulk FHIR Extract Packaging", "status": "ERROR",
                "detail": r.get("error", "Extract packaging check failed")}
    s = r.get("summary", {})
    total = s.get("total_resources", 0)
    types = s.get("resource_types_found", 0)
    return {
        "stage": "1a-ii",
        "label": "Bulk FHIR Extract Packaging",
        "status": st,
        "detail": f"{total:,} resources · {types} resource types",
    }


def _no_findings_detail(stage_cards: list) -> str:
    labels = {
        "1a-i":  "Bulk FHIR API server conformance",
        "1a-ii": "Bulk FHIR extract packaging",
        "1b":    "NDJSON structural validation",
        "1c-i":  "base FHIR R4 conformance",
        "1c-ii": "US Core 6.1.0 profile conformance",
    }
    parts = [labels[c["stage"]] for c in stage_cards
             if c.get("status") == "PASS" and c["stage"] in labels]
    tested = [labels[c["stage"]] for c in stage_cards
              if c.get("status") not in ("N/A", "SKIPPED", None) and c["stage"] in labels]
    if not tested:
        return "No stages ran. Upload NDJSON files or provide a FHIR server URL."
    if not parts:
        return "No passing stages to report."
    return (f"This extract passes {', '.join(parts)}. "
            "Proceed to Stage 2 anonymization and Stage 3 semantic assessment.")


def _card_1b(r) -> dict:
    if r is None:
        return {"stage": "1b", "label": "NDJSON Structural", "status": "SKIPPED", "detail": "Not run"}
    st = _status(r)
    s = r.get("summary", {})
    checked = s.get("files_checked", 0)
    failed = s.get("files_failed", 0)
    records = s.get("total_records", 0)
    return {
        "stage": "1b",
        "label": "NDJSON Structural Validation",
        "status": st,
        "detail": f"{checked - failed}/{checked} files passed · {records:,} records",
    }


def _card_1c(r, stage_id: str, label: str) -> dict:
    if r is None:
        return {"stage": stage_id, "label": label, "status": "BLOCKED", "detail": "Stage 1b must pass first"}
    # Detect Java / validator crash before inferring status from error counts
    crash_reason = _validator_crash_reason(r)
    if crash_reason:
        return {
            "stage": stage_id,
            "label": label,
            "status": "ERROR",
            "detail": f"Validator unavailable: {crash_reason}",
        }
    st = _status(r)
    if st == "ERROR":
        return {
            "stage": stage_id,
            "label": label,
            "status": "ERROR",
            "detail": r.get("error", "Validator did not complete"),
        }
    s = r.get("summary", {})
    errors = s.get("error_count", 0)
    warnings = s.get("warning_count", 0)
    total = s.get("total_resources", 0)
    return {
        "stage": stage_id,
        "label": label,
        "status": st,
        "detail": f"{total:,} resources · {errors:,} errors · {warnings:,} warnings",
    }


def _validator_crash_reason(r: dict) -> str:
    """Returns a crash reason string when the validator did not run successfully."""
    if not r:
        return ""
    stderr = r.get("validator_stderr_tail", "")
    if stderr and ("java" in stderr.lower() or "unable to locate" in stderr.lower()):
        for line in stderr.splitlines():
            line = line.strip()
            if line:
                return line
        return "Java Runtime not found"
    by_rt = r.get("by_resource_type", [])
    errored = [d for d in by_rt if d.get("errors", 0) > 0]
    if (len(errored) == 1
            and errored[0]["resource_type"] == "unknown"
            and any(e.get("code") == "exception" for e in errored[0].get("top_errors", []))):
        return "Validator exception — no resources were evaluated"
    return ""


def _merge_1c_by_rt(r_i, r_ii) -> list:
    """Combine 1c-i and 1c-ii by_resource_type into a single merged table."""
    table = {}
    if r_i:
        for row in r_i.get("by_resource_type", []):
            rt = row["resource_type"]
            table[rt] = {
                "resource_type": rt,
                "total": row.get("total", 0),
                "errors_i": row.get("errors", 0),
                "warnings_i": row.get("warnings", 0),
                "top_errors_i": row.get("top_errors", []),
                "errors_ii": 0,
                "warnings_ii": 0,
                "top_errors_ii": [],
            }
    if r_ii:
        for row in r_ii.get("by_resource_type", []):
            rt = row["resource_type"]
            if rt not in table:
                table[rt] = {
                    "resource_type": rt,
                    "total": row.get("total", 0),
                    "errors_i": 0,
                    "warnings_i": 0,
                    "top_errors_i": [],
                }
            table[rt]["errors_ii"] = row.get("errors", 0)
            table[rt]["warnings_ii"] = row.get("warnings", 0)
            table[rt]["top_errors_ii"] = row.get("top_errors", [])

    # Sort: quality measure-critical types first, then alphabetical
    from findings import QM_QUALITY_TYPES
    rows = list(table.values())
    rows.sort(key=lambda r: (0 if r["resource_type"] in QM_QUALITY_TYPES else 1, r["resource_type"]))
    return rows
