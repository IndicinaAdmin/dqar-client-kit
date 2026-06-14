"""
Maps Stage 1 check results to three-tier DQAR findings.

Tier 1 — Governance Gap    : organizational failure that will recur next measurement period
Tier 2 — Measure Data Gap  : technical data quality failure affecting measure rates now
Tier 3 — Digital Readiness : capability gap vs. MP2029 ECDS mandatory / CMS-0057-F Jan 1 2027
"""

QM_QUALITY_TYPES = {
    "Patient", "Coverage", "Condition", "Observation",
    "Encounter", "Procedure", "MedicationRequest", "MedicationDispense",
    "DiagnosticReport", "Immunization",
}

# Resource types with structured .category / .type codes that ECDS uses for population filtering.
# Distinct from the SSoR source-type vocabulary (EXT 1) — this is resource-type-level, not source-level.
ECDS_CATEGORY_TYPES = {"Observation", "Encounter", "DiagnosticReport"}

# Per-resource narrative context for DEQM-required and quality measure-critical types.
# Used to generate structured "Resource: N records (context)" lines in findings.
RESOURCE_NARRATIVE = {
    # DEQM-required (per Library dataRequirements + named QI-Core default profiles)
    "Coverage":           "DEQM-required for COL/EXM130 and EXM124 measures",
    "Encounter":          "DEQM-required for MRP, COL/EXM130, and VTE/EXM108 measures",
    "Patient":            "DEQM-required for all measures — denominator population anchor",
    "Organization":       "DEQM-required for all measures — MeasureReport.reporter",
    "Practitioner":       "DEQM-required for all measures — Individual MeasureReport attestation",
    # Quality measure-critical but not DEQM-required
    "Condition":          "ECDS quality measures: diabetes (CDC), cardiovascular (CBP), hypertension",
    "Observation":        "ECDS lab-based measures: HbA1c (CDC), cholesterol (CBP, COL), lead screening",
    "MedicationRequest":  "ECDS medication measures: medication non-adherence exclusions, VTE prophylaxis",
    "MedicationDispense": "ECDS pharmacy measures: PDC-Rx, CMR, MPT — proportion days covered",
    "Procedure":          "ECDS procedure-based measures: breast cancer screening (BCS), cervical cancer (COL)",
    "DiagnosticReport":   "ECDS lab reporting: diagnostic results for BCS, COL, lead screening",
    "Immunization":       "ECDS immunization measures: childhood immunization (CIS), influenza (FVA)",
}


def _finding(tier: int, title: str, detail: str, source: str,
             severity: str = "HIGH", lines: list = None) -> dict:
    names = {1: "Governance Gap", 2: "Measure Data Gap", 3: "Digital Readiness Gap"}
    f = {
        "tier": tier,
        "tier_name": names[tier],
        "severity": severity,
        "title": title,
        "detail": detail,
        "source": source,
    }
    if lines:
        f["lines"] = lines
    return f


def _resource_narrative_line(resource_type: str, count: int) -> str:
    """Return 'ResourceType: N records (measure context)' for structured finding lines."""
    context = RESOURCE_NARRATIVE.get(resource_type)
    count_str = f"{count:,} record{'s' if count != 1 else ''}"
    if context:
        return f"{resource_type}: {count_str} ({context})"
    return f"{resource_type}: {count_str}"


def _from_stage1a(r: dict) -> list:
    if not r:
        return []
    findings = []
    checks = {c["check"]: c for c in r.get("checks", [])}

    if not checks.get("capability_declares_export", {}).get("passed"):
        findings.append(_finding(
            tier=3,
            title="Bulk FHIR export not declared in CapabilityStatement",
            detail=(
                "The FHIR server does not declare the $export operation in its CapabilityStatement. "
                "NCQA ECDS mandatory reporting (MY2029) and CMS-0057-F payer-to-payer exchange "
                "(January 1, 2027) both require Bulk Data Access IG STU2 conformance. "
                "Without $export, this plan cannot participate in either program without a "
                "complete FHIR server replacement or upgrade."
            ),
            source="Stage 1a — Check 1: capability_declares_export",
        ))
        return findings  # downstream checks are meaningless without export capability

    if not checks.get("kick_off_accepted", {}).get("passed"):
        findings.append(_finding(
            tier=2,
            title="$export declared but endpoint returns non-202 response",
            detail=(
                "$export is declared in the CapabilityStatement but the endpoint does not return "
                "202 Accepted when triggered. The declaration is non-functional. "
                "This blocks all bulk data use cases including ECDS reporting, continuous data "
                "monitoring, and payer-to-payer exchange."
            ),
            source="Stage 1a — Check 2: kick_off_accepted",
        ))
        return findings

    if not checks.get("content_location_header", {}).get("passed"):
        findings.append(_finding(
            tier=2,
            title="$export does not implement the async polling pattern",
            detail=(
                "$export returns 202 Accepted but does not include a Content-Location header. "
                "Bulk Data Access IG requires Content-Location pointing to a status polling URL. "
                "Without it, bulk export clients cannot track progress or retrieve completed files."
            ),
            source="Stage 1a — Check 3: content_location_header",
            severity="MEDIUM",
        ))

    if checks.get("content_location_header", {}).get("passed") and \
       not checks.get("polling_completes", {}).get("passed"):
        findings.append(_finding(
            tier=2,
            title="Export job fails before completion",
            detail=(
                "The $export job was accepted and a polling URL was returned, but the export "
                "did not complete within the polling window. This indicates a server-side failure "
                "during export execution — likely a resource constraint or query timeout on large populations."
            ),
            source="Stage 1a — Check 4: polling_completes",
        ))

    if not checks.get("output_content_type", {}).get("passed"):
        findings.append(_finding(
            tier=2,
            title="Export files returned with incorrect Content-Type",
            detail=(
                "Export output files do not return application/fhir+ndjson Content-Type. "
                "Bulk FHIR clients rely on this header to identify and parse export files. "
                "Incorrect content types will cause parsing failures in downstream consumers "
                "including ECDS submission pipelines."
            ),
            source="Stage 1a — Check 6: output_content_type",
            severity="MEDIUM",
        ))

    return findings


def _from_stage1b(r: dict) -> list:
    if not r:
        return []
    findings = []
    summary = r.get("summary", {})
    files = r.get("files", [])

    # SUBSETTED resources — FHIR server exported in summary mode
    total_subsetted = summary.get("total_subsetted", 0)
    subsetted_files = summary.get("subsetted_files", [])
    total_records = summary.get("total_records", 0)
    if total_subsetted > 0:
        pct = round(100 * total_subsetted / total_records) if total_records else 0
        file_list = ", ".join(subsetted_files[:6]) + ("…" if len(subsetted_files) > 6 else "")
        findings.append(_finding(
            tier=2,
            title=(
                f"Bulk FHIR export contains SUBSETTED resources — "
                f"Stage 1c conformance validation is suppressed ({total_subsetted:,} of {total_records:,} records, {pct}%)"
            ),
            detail=(
                f"The FHIR server returned {total_subsetted:,} resources ({pct}% of the extract) tagged "
                f"with meta.tag code 'SUBSETTED' (system: hl7.org/fhir/v3/ObservationValue). "
                "SUBSETTED is the FHIR standard signal that a resource was returned in summary mode "
                "— mandatory elements may be intentionally omitted. "
                "The HAPI FHIR validator respects this signal and suppresses all required-element "
                "errors on SUBSETTED resources. As a result, Stage 1c conformance results for this "
                "extract are unreliable: missing identifiers, missing status codes, missing category "
                "bindings, and other US Core required elements will not be flagged. "
                f"Affected files: {file_list}. "
                "Root cause: the FHIR server $export was invoked with _summary=true or the server "
                "applies summary mode by default. Re-run $export without _summary to obtain full "
                "resources and enable accurate conformance assessment."
            ),
            source="Stage 1b — SUBSETTED resource detection (meta.tag.code = SUBSETTED)",
            severity="HIGH",
        ))

    # Empty files — present in export but contain zero records
    empty_files = [f for f in files if f.get("empty", False)]
    if empty_files:
        critical_empty = [
            f["resource_type_declared"] for f in empty_files
            if f.get("resource_type_declared") in QM_QUALITY_TYPES
        ]
        all_names = ", ".join(f["file"] for f in empty_files)
        if critical_empty:
            detail = (
                f"{len(empty_files)} file(s) in the Bulk FHIR export are present but contain "
                f"zero records: {all_names}. "
                "Zero records means this data was not available or was not exported — "
                "affected measures cannot be calculated from this extract alone. "
                "These files also cannot be conformance-validated by the FHIR validator."
            )
            lines = [_resource_narrative_line(rt, 0) for rt in critical_empty]
            from stage1a2_bulk_fhir_extract_preflight import DEQM_REQUIRED
            has_deqm_gap = any(rt in DEQM_REQUIRED for rt in critical_empty)
            findings.append(_finding(
                tier=2,
                title=f"Required resource type(s) have zero records in export ({', '.join(critical_empty)})",
                detail=detail,
                source="Stage 1b — Empty export files",
                severity="HIGH" if has_deqm_gap else "MEDIUM",
                lines=lines,
            ))
        else:
            findings.append(_finding(
                tier=2,
                title=f"Export file(s) present but contain zero records ({len(empty_files)} file(s))",
                detail=(
                    f"The following files are present in the export but contain zero records: {all_names}. "
                    "Zero-record files indicate either a data availability gap or an export pipeline "
                    "filtering issue. These files cannot be conformance-validated."
                ),
                source="Stage 1b — Empty export files",
                severity="MEDIUM",
                lines=[_resource_narrative_line(f["resource_type_declared"], 0) for f in empty_files],
            ))

    encoding_failures = [f for f in files if not f.get("checks", {}).get("utf8_decodable")]
    if encoding_failures:
        names = ", ".join(f["file"] for f in encoding_failures[:3])
        suffix = "..." if len(encoding_failures) > 3 else ""
        findings.append(_finding(
            tier=1,
            title=f"Export files contain non-UTF-8 encoding ({len(encoding_failures)} file(s))",
            detail=(
                f"Files failing UTF-8 decoding: {names}{suffix}. "
                "FHIR Bulk Data Access IG requires UTF-8. Non-UTF-8 output indicates a source "
                "system character set policy that has not been enforced at the ETL layer. "
                "This is a recurring governance failure — the same encoding error will appear "
                "on every export until the pipeline character set configuration is corrected."
            ),
            source="Stage 1b — Check 1: utf8_decodable",
        ))

    json_errors = summary.get("total_json_parse_errors", 0)
    if json_errors > 0:
        findings.append(_finding(
            tier=1,
            title=f"NDJSON files contain malformed JSON lines ({json_errors:,} line(s))",
            detail=(
                f"{json_errors:,} line(s) failed JSON parsing. Each line in an NDJSON file must be "
                "a valid, complete JSON object. Truncated or malformed lines indicate a buffer-flush "
                "or streaming failure in the export pipeline. This is a recurring ETL governance "
                "issue — malformed lines will appear on every export until the pipeline is corrected."
            ),
            source="Stage 1b — Check 3: all_lines_valid_json",
        ))

    mismatches = summary.get("total_resource_type_mismatches", 0)
    if mismatches > 0:
        findings.append(_finding(
            tier=1,
            title=f"Resource type routing mismatch in export pipeline ({mismatches:,} resource(s))",
            detail=(
                f"{mismatches:,} resource(s) appear in the wrong NDJSON file. "
                "The Bulk FHIR spec requires each file to contain only the resource type matching "
                "its filename (Patient.ndjson → Patient resources only). Cross-type routing "
                "indicates a file-routing bug in the export pipeline that will corrupt all "
                "bulk exports and downstream measure execution until corrected."
            ),
            source="Stage 1b — Check 5: filename_matches_type",
            severity="MEDIUM",
        ))

    return findings


def _validator_crashed(r: dict) -> str:
    """Returns a non-empty crash reason string when the validator did not run successfully."""
    if not r:
        return ""
    stderr = r.get("validator_stderr_tail", "")
    if stderr and ("java" in stderr.lower() or "unable to locate" in stderr.lower()):
        for line in stderr.splitlines():
            line = line.strip()
            if line:
                return line
        return "Java Runtime not found"
    # Pure exception errors on unknown resource type = validator crashed before processing any resources
    by_rt = r.get("by_resource_type", [])
    errored = [d for d in by_rt if d.get("errors", 0) > 0]
    if (len(errored) == 1
            and errored[0]["resource_type"] == "unknown"
            and any(e.get("code") == "exception" for e in errored[0].get("top_errors", []))):
        return "Validator exception — no resources were evaluated"
    return ""


def _from_stage1c(r_i: dict, r_ii: dict) -> list:
    if not r_i and not r_ii:
        return []
    findings = []

    # Detect validator crashes and explicit pipeline errors before checking results
    for label, r in [("Stage 1c-I", r_i), ("Stage 1c-II", r_ii)]:
        if not r:
            continue
        crash_reason = _validator_crashed(r)
        if crash_reason:
            findings.append(_finding(
                tier=2,
                title=f"FHIR validator unavailable — {label} results incomplete",
                detail=(
                    f"The FHIR validator could not execute: {crash_reason}. "
                    "No conformance errors were evaluated for this extract. "
                    "Install Java 17+ (adoptium.net) and re-run Stage 1c for a complete assessment. "
                    "This is an infrastructure gap, not a data quality finding."
                ),
                source=label,
                severity="MEDIUM",
            ))
        elif r.get("status") == "ERROR":
            findings.append(_finding(
                tier=2,
                title=f"FHIR validator failed to complete ({label})",
                detail=(
                    f"The FHIR validator did not complete: {r.get('error', 'Unknown error')}. "
                    "Conformance errors that exist in the extract were not evaluated. "
                    "Resolve the validator error and re-run Stage 1c for a complete assessment."
                ),
                source=label,
            ))

    # 1c-i: base FHIR R4 errors (skip if validator crashed)
    if r_i and r_i.get("status") != "ERROR" and not _validator_crashed(r_i):
        s = r_i.get("summary", {})
        error_count = s.get("error_count", 0)
        total = s.get("total_resources", 0)

        if error_count > 0:
            systematic = [
                f"{d['resource_type']} ({d['errors']}/{d['total']})"
                for d in r_i.get("by_resource_type", [])
                if d["resource_type"] in QM_QUALITY_TYPES
                and d.get("total", 0) > 0
                and d.get("errors", 0) / d["total"] > 0.30
            ]

            if systematic:
                findings.append(_finding(
                    tier=1,
                    title="Systematic base FHIR R4 violations on quality measure-critical resource types",
                    detail=(
                        "More than 30% of resources fail base FHIR R4 (4.0.1) structural conformance "
                        f"on: {', '.join(systematic[:5])}{'...' if len(systematic) > 5 else ''}. "
                        "At this error rate the violations are systematic, not edge cases — indicating "
                        "a source-to-FHIR mapping policy failure. These errors will recur on every "
                        "export until the ETL field-level mapping logic is corrected."
                    ),
                    source="Stage 1c-i — Base FHIR R4 structural conformance",
                ))
            else:
                findings.append(_finding(
                    tier=2,
                    title=f"Base FHIR R4 structural violations ({error_count:,} errors across {total:,} resources)",
                    detail=(
                        f"{error_count:,} base FHIR R4 (4.0.1) validation errors. These are structural "
                        "violations below the US Core profile layer — incorrect data types, missing "
                        "required elements, or invalid reference formats. Each error is a potential "
                        "CQL execution failure for any measure reading the affected element."
                    ),
                    source="Stage 1c-i — Base FHIR R4 structural conformance",
                    severity="MEDIUM",
                ))

    # 1c-ii: US Core 6.1.0 errors (skip if validator crashed)
    if r_ii and r_ii.get("status") != "ERROR" and not _validator_crashed(r_ii):
        s = r_ii.get("summary", {})
        error_count = s.get("error_count", 0)
        total = s.get("total_resources", 0)

        if error_count > 0:
            critical_affected = [
                f"{d['resource_type']} ({d['errors']:,})"
                for d in r_ii.get("by_resource_type", [])
                if d["resource_type"] in QM_QUALITY_TYPES and d.get("errors", 0) > 0
            ]

            detail = (
                f"{error_count:,} US Core 6.1.0 profile conformance errors across {total:,} resources. "
            )
            if critical_affected:
                detail += (
                    f"Quality measure-critical types affected: {', '.join(critical_affected[:5])}{'...' if len(critical_affected) > 5 else ''}. "
                )
            detail += (
                "US Core profile conformance is the mandatory semantic contract between the payer's "
                "FHIR server and the CQL execution engine. Non-conformant resources may be excluded "
                "from measure denominators or numerators, directly affecting reported quality measure rates."
            )

            findings.append(_finding(
                tier=2,
                title=f"US Core 6.1.0 profile non-conformance ({error_count:,} errors)",
                detail=detail,
                source="Stage 1c-ii — US Core 6.1.0 profile conformance",
                severity="HIGH" if critical_affected else "MEDIUM",
            ))

            # Flag ECDS-critical categorization errors as Tier 3
            ecds_affected = []
            for d in r_ii.get("by_resource_type", []):
                rt = d["resource_type"]
                if rt not in ECDS_CATEGORY_TYPES:
                    continue
                cat_errors = sum(
                    e["count"] for e in d.get("top_errors", [])
                    if "category" in (e.get("element") or "") or ".type" in (e.get("element") or "")
                )
                if cat_errors > 0:
                    ecds_affected.append(f"{rt} ({cat_errors:,} categorization errors)")

            if ecds_affected:
                findings.append(_finding(
                    tier=3,
                    title="ECDS mandatory categorization gaps on quality measure-critical resource types",
                    detail=(
                        f"Categorization errors on: {', '.join(ecds_affected[:4])}. "
                        "NCQA ECDS measure specifications use Encounter.type and Observation.category "
                        "to filter measure populations. Resources missing these structured codes will "
                        "be excluded from denominators when ECDS replaces Hybrid method in MY2029. "
                        "This is correctable now — it becomes a measure rate failure after the transition."
                    ),
                    source="Stage 1c-ii — Encounter.type / Observation.category",
                    severity="MEDIUM",
                ))

    return findings


def derive_findings(reports: dict) -> list:
    """
    Derives DQAR three-tier findings from Stage 1 check results.
    Returns list of finding dicts, ordered tier 1 → 2 → 3.
    """
    all_findings = (
        _from_stage1a(reports.get("stage1a"))
        + _from_stage1b(reports.get("stage1b"))
        + _from_stage1c(reports.get("stage1c_i"), reports.get("stage1c_ii"))
    )
    return sorted(all_findings, key=lambda f: f["tier"])
