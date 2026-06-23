"""
tests/generate_fixtures.py
CDAR UC1 — Fixture generation and pipeline integration test runner.

Creates 13 test fixture directories under tests/fixtures/, each with specific
mutations applied to the source NDJSON files. Runs Stage 1a-ii and Stage 1b
on every fixture; runs Stage 1c (1c-i + 1c-ii) only on fixtures 10, 11, 12
and only if the HAPI validator jar is present.

Results written to: tests/fixture_results.json
Analysis written to: tests/FIXTURE_ANALYSIS.md
"""

import io
import json
import os
import shutil
import sys
import textwrap
from contextlib import redirect_stdout
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE1_DIR = REPO_ROOT / "stage1"
SOURCE_DIR = REPO_ROOT / "tests" / "fixtures" / "source"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
OUTPUT_DIR = REPO_ROOT / "tests"
RESULTS_JSON = OUTPUT_DIR / "fixture_results.json"
ANALYSIS_MD = OUTPUT_DIR / "FIXTURE_ANALYSIS.md"
HAPI_JAR = STAGE1_DIR / "hapi-validator.jar"
# The actual jar is named validator_cli.jar; also check both locations.
VALIDATOR_CLI_JAR = REPO_ROOT / "tools" / "validator_cli.jar"

sys.path.insert(0, str(STAGE1_DIR))

import stage1a2_bulk_fhir_extract_preflight as stage1a2
import stage1b_ndjson_validator as stage1b
import stage1c_fhir_uscore_validator as stage1c

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_files() -> dict[str, bytes]:
    """Load all source NDJSON files as raw bytes, keyed by filename."""
    return {f.name: f.read_bytes() for f in sorted(SOURCE_DIR.glob("*.ndjson"))}


def _write_fixture(fixture_dir: Path, files: dict[str, bytes]) -> None:
    """Write a dict of {filename: bytes} into fixture_dir (recreated clean)."""
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    fixture_dir.mkdir(parents=True)
    for name, content in files.items():
        (fixture_dir / name).write_bytes(content)


def _read_ndjson_lines(raw_bytes: bytes) -> list[bytes]:
    """Split raw bytes into non-empty lines (preserving bytes, no decode)."""
    return [ln for ln in raw_bytes.split(b"\n") if ln.strip()]


def _corrupt_utf8_in_line(line_bytes: bytes) -> bytes:
    """Replace one byte near the middle of a JSON string value with 0x80 (invalid UTF-8 lead byte)."""
    mid = len(line_bytes) // 2
    return line_bytes[:mid] + bytes([0x80]) + line_bytes[mid + 1:]


def _count_lines(raw_bytes: bytes) -> int:
    return len([ln for ln in raw_bytes.split(b"\n") if ln.strip()])


def _remove_key_from_all(raw_bytes: bytes, key: str) -> bytes:
    """Remove a JSON key from every record in an NDJSON file."""
    lines = _read_ndjson_lines(raw_bytes)
    result = []
    for ln in lines:
        try:
            obj = json.loads(ln)
            obj.pop(key, None)
            result.append(json.dumps(obj, separators=(",", ":")))
        except json.JSONDecodeError:
            result.append(ln.decode("utf-8", errors="replace"))
    return ("\n".join(result) + "\n").encode("utf-8")


def _remove_key_from_n(raw_bytes: bytes, key: str, n: int) -> bytes:
    """Remove a JSON key from the first n records."""
    lines = _read_ndjson_lines(raw_bytes)
    result = []
    modified = 0
    for ln in lines:
        try:
            obj = json.loads(ln)
            if modified < n:
                obj.pop(key, None)
                modified += 1
            result.append(json.dumps(obj, separators=(",", ":")))
        except json.JSONDecodeError:
            result.append(ln.decode("utf-8", errors="replace"))
    return ("\n".join(result) + "\n").encode("utf-8")


def _remove_keys_from_all(raw_bytes: bytes, keys: list[str]) -> bytes:
    """Remove multiple JSON keys from every record."""
    lines = _read_ndjson_lines(raw_bytes)
    result = []
    for ln in lines:
        try:
            obj = json.loads(ln)
            for k in keys:
                obj.pop(k, None)
            result.append(json.dumps(obj, separators=(",", ":")))
        except json.JSONDecodeError:
            result.append(ln.decode("utf-8", errors="replace"))
    return ("\n".join(result) + "\n").encode("utf-8")


def _remove_keys_from_n(raw_bytes: bytes, keys: list[str], n: int) -> bytes:
    """Remove multiple JSON keys from first n records."""
    lines = _read_ndjson_lines(raw_bytes)
    result = []
    modified = 0
    for ln in lines:
        try:
            obj = json.loads(ln)
            if modified < n:
                for k in keys:
                    obj.pop(k, None)
                modified += 1
            result.append(json.dumps(obj, separators=(",", ":")))
        except json.JSONDecodeError:
            result.append(ln.decode("utf-8", errors="replace"))
    return ("\n".join(result) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------

def build_fixture_01(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-01-baseline-clean: all files unchanged."""
    return dict(src)


def build_fixture_02(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-02-1b-utf8-encoding: corrupt 3 Patient.ndjson lines with invalid UTF-8."""
    files = dict(src)
    lines = _read_ndjson_lines(files["Patient.ndjson"])
    # Corrupt lines at indices 0, 5, 10
    corrupt_indices = [0, 5, 10]
    for i in corrupt_indices:
        if i < len(lines):
            lines[i] = _corrupt_utf8_in_line(lines[i])
    # Write in binary mode — these bytes are NOT valid UTF-8
    files["Patient.ndjson"] = b"\n".join(lines) + b"\n"
    return files


def build_fixture_03(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-03-1b-invalid-json: truncate 5 Condition.ndjson lines at ~40 chars."""
    files = dict(src)
    lines = _read_ndjson_lines(files["Condition.ndjson"])
    # Truncate the first 5 lines at position 40
    truncate_indices = list(range(min(5, len(lines))))
    for i in truncate_indices:
        lines[i] = lines[i][:40]  # cuts mid-JSON
    files["Condition.ndjson"] = b"\n".join(lines) + b"\n"
    return files


def build_fixture_04(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-04-1b-missing-resourcetype: remove resourceType from 5 Encounter records."""
    files = dict(src)
    files["Encounter.ndjson"] = _remove_key_from_n(files["Encounter.ndjson"], "resourceType", 5)
    return files


def build_fixture_05(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-05-1b-filename-mismatch: replace Procedure.ndjson with Observation records."""
    files = dict(src)
    # Build valid Observation records to replace Procedure content
    obs_lines = _read_ndjson_lines(files["Observation.ndjson"])
    # Take up to 9 Observation records (same count as Procedure)
    obs_bytes = b"\n".join(obs_lines[:9]) + b"\n"
    files["Procedure.ndjson"] = obs_bytes
    return files


def build_fixture_06(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-06-1b-empty-files: empty Coverage.ndjson + add empty DiagnosticReport.ndjson."""
    files = dict(src)
    files["Coverage.ndjson"] = b""  # 0 bytes
    files["DiagnosticReport.ndjson"] = b""  # 0 bytes
    return files


def build_fixture_07(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-07-1b-mixed-types: append 3 Observation records to Condition.ndjson."""
    files = dict(src)
    obs_lines = _read_ndjson_lines(files["Observation.ndjson"])
    appended = b"\n".join(obs_lines[:3])
    files["Condition.ndjson"] = files["Condition.ndjson"].rstrip(b"\n") + b"\n" + appended + b"\n"
    return files


def build_fixture_08(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-08-1a2-no-patient: all source files except Patient.ndjson."""
    return {k: v for k, v in src.items() if k != "Patient.ndjson"}


def build_fixture_09(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-09-1a2-missing-core-types: remove Condition.ndjson and Observation.ndjson."""
    return {k: v for k, v in src.items() if k not in ("Condition.ndjson", "Observation.ndjson")}


def build_fixture_10(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-10-1c-base-r4-errors: strip required base R4 fields."""
    files = dict(src)
    # Observation.ndjson: remove status (1..1)
    files["Observation.ndjson"] = _remove_key_from_all(files["Observation.ndjson"], "status")
    # MedicationRequest.ndjson: remove status and intent (both 1..1)
    files["MedicationRequest.ndjson"] = _remove_keys_from_all(
        files["MedicationRequest.ndjson"], ["status", "intent"]
    )
    # Encounter.ndjson: remove status and class from first 10 records
    tmp = _remove_key_from_n(files["Encounter.ndjson"], "status", 10)
    files["Encounter.ndjson"] = _remove_key_from_n(tmp, "class", 10)
    return files


def build_fixture_11(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-11-1c-uscore-errors: remove US Core required fields."""
    files = dict(src)
    # Patient: remove identifier array (required by US Core Patient)
    files["Patient.ndjson"] = _remove_key_from_all(files["Patient.ndjson"], "identifier")
    # Condition: remove category (required by US Core Condition)
    files["Condition.ndjson"] = _remove_key_from_all(files["Condition.ndjson"], "category")
    # Observation: remove category (MUST SUPPORT by US Core Observation)
    files["Observation.ndjson"] = _remove_key_from_all(files["Observation.ndjson"], "category")
    # Encounter: remove type (ECDS-critical)
    files["Encounter.ndjson"] = _remove_key_from_all(files["Encounter.ndjson"], "type")
    return files


def build_fixture_12(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-12-1c-combined-violations: combine fixture-10 + fixture-11 mutations."""
    files = dict(src)
    # 10 mutations
    files["Observation.ndjson"] = _remove_key_from_all(files["Observation.ndjson"], "status")
    files["MedicationRequest.ndjson"] = _remove_keys_from_all(
        files["MedicationRequest.ndjson"], ["status", "intent"]
    )
    tmp = _remove_key_from_n(files["Encounter.ndjson"], "status", 10)
    files["Encounter.ndjson"] = _remove_key_from_n(tmp, "class", 10)
    # 11 mutations (on top of 10)
    files["Patient.ndjson"] = _remove_key_from_all(files["Patient.ndjson"], "identifier")
    files["Condition.ndjson"] = _remove_key_from_all(files["Condition.ndjson"], "category")
    files["Observation.ndjson"] = _remove_key_from_all(files["Observation.ndjson"], "category")
    # Encounter already mutated; also remove type
    files["Encounter.ndjson"] = _remove_key_from_all(files["Encounter.ndjson"], "type")
    return files


def build_fixture_13(src: dict[str, bytes]) -> dict[str, bytes]:
    """fixture-13-1b-all-structural-errors: combine multiple 1b error types."""
    files = dict(src)
    # UTF-8 errors in Patient (3 lines corrupted)
    lines = _read_ndjson_lines(files["Patient.ndjson"])
    for i in [0, 5, 10]:
        if i < len(lines):
            lines[i] = _corrupt_utf8_in_line(lines[i])
    files["Patient.ndjson"] = b"\n".join(lines) + b"\n"
    # Invalid JSON in Condition (5 lines truncated)
    cond_lines = _read_ndjson_lines(files["Condition.ndjson"])
    for i in range(min(5, len(cond_lines))):
        cond_lines[i] = cond_lines[i][:40]
    files["Condition.ndjson"] = b"\n".join(cond_lines) + b"\n"
    # Missing resourceType in Encounter (5 records)
    files["Encounter.ndjson"] = _remove_key_from_n(files["Encounter.ndjson"], "resourceType", 5)
    # Empty Coverage
    files["Coverage.ndjson"] = b""
    return files


# ---------------------------------------------------------------------------
# Fixture registry
# ---------------------------------------------------------------------------

FIXTURES = [
    {
        "name":     "fixture-01-baseline-clean",
        "builder":  build_fixture_01,
        "run_1c":   True,
        "expected": {"1a2": "PASS", "1b": "PASS"},
        "injected": "No mutations — all source files copied verbatim.",
        "notes":    "Baseline: all stages should pass.",
    },
    {
        "name":     "fixture-02-1b-utf8-encoding",
        "builder":  build_fixture_02,
        "run_1c":   False,
        "expected": {"1a2": "PASS", "1b": "FAIL"},
        "injected": "Patient.ndjson: 3 lines contain 0x80 byte (invalid UTF-8).",
        "notes":    "Stage 1b should fail utf8_decodable for Patient.",
    },
    {
        "name":     "fixture-03-1b-invalid-json",
        "builder":  build_fixture_03,
        "run_1c":   False,
        "expected": {"1a2": "PASS", "1b": "FAIL"},
        "injected": "Condition.ndjson: first 5 lines truncated at position 40.",
        "notes":    "Stage 1b should fail all_lines_valid_json for Condition.",
    },
    {
        "name":     "fixture-04-1b-missing-resourcetype",
        "builder":  build_fixture_04,
        "run_1c":   False,
        "expected": {"1a2": "PASS", "1b": "FAIL"},
        "injected": "Encounter.ndjson: resourceType removed from first 5 records.",
        "notes":    "Stage 1b should fail resource_type_present for Encounter.",
    },
    {
        "name":     "fixture-05-1b-filename-mismatch",
        "builder":  build_fixture_05,
        "run_1c":   False,
        "expected": {"1a2": "FAIL", "1b": "FAIL"},
        "injected": "Procedure.ndjson: replaced with Observation records (resourceType=Observation).",
        "notes":    "1b should fail filename_matches_type. 1a2 may also flag mixed types.",
    },
    {
        "name":     "fixture-06-1b-empty-files",
        "builder":  build_fixture_06,
        "run_1c":   False,
        "expected": {"1a2": "PASS", "1b": "WARN"},
        "injected": "Coverage.ndjson: 0 bytes. DiagnosticReport.ndjson: 0 bytes added.",
        "notes":    "Stage 1b marks empty files; not a hard FAIL. 1a2 may still pass.",
    },
    {
        "name":     "fixture-07-1b-mixed-types",
        "builder":  build_fixture_07,
        "run_1c":   False,
        "expected": {"1a2": "FAIL", "1b": "FAIL"},
        "injected": "Condition.ndjson: 3 Observation records appended (two types in one file).",
        "notes":    "1b should fail filename_matches_type. 1a2 should fail single_type_per_file.",
    },
    {
        "name":     "fixture-08-1a2-no-patient",
        "builder":  build_fixture_08,
        "run_1c":   False,
        "expected": {"1a2": "FAIL", "1b": "PASS"},
        "injected": "Patient.ndjson omitted from extract.",
        "notes":    "1a2 should fail patient_file_present.",
    },
    {
        "name":     "fixture-09-1a2-missing-core-types",
        "builder":  build_fixture_09,
        "run_1c":   False,
        "expected": {"1a2": "FAIL", "1b": "PASS"},
        "injected": "Condition.ndjson and Observation.ndjson omitted.",
        "notes":    "1a2 should fail hedis_core_types_present.",
    },
    {
        "name":     "fixture-10-1c-base-r4-errors",
        "builder":  build_fixture_10,
        "run_1c":   True,
        "expected": {"1a2": "PASS", "1b": "PASS", "1c-i": "FAIL"},
        "injected": (
            "Observation.ndjson: status stripped from all records. "
            "MedicationRequest.ndjson: status+intent stripped from all records. "
            "Encounter.ndjson: status+class stripped from first 10 records."
        ),
        "notes":    "1c-i should catch missing required base R4 fields.",
    },
    {
        "name":     "fixture-11-1c-uscore-errors",
        "builder":  build_fixture_11,
        "run_1c":   True,
        "expected": {"1a2": "PASS", "1b": "PASS", "1c-ii": "FAIL"},
        "injected": (
            "Patient.ndjson: identifier removed from all records. "
            "Condition.ndjson: category removed from all records. "
            "Observation.ndjson: category removed from all records. "
            "Encounter.ndjson: type removed from all records."
        ),
        "notes":    "1c-ii should catch US Core profile violations.",
    },
    {
        "name":     "fixture-12-1c-combined-violations",
        "builder":  build_fixture_12,
        "run_1c":   True,
        "expected": {"1a2": "PASS", "1b": "PASS", "1c-i": "FAIL", "1c-ii": "FAIL"},
        "injected": "Combined mutations from fixture-10 (base R4) and fixture-11 (US Core).",
        "notes":    "Both 1c-i and 1c-ii should fail.",
    },
    {
        "name":     "fixture-13-1b-all-structural-errors",
        "builder":  build_fixture_13,
        "run_1c":   False,
        "expected": {"1a2": "PASS", "1b": "FAIL"},
        "injected": (
            "Patient.ndjson: UTF-8 corruption in 3 lines. "
            "Condition.ndjson: 5 lines truncated at 40 chars. "
            "Encounter.ndjson: resourceType removed from 5 records. "
            "Coverage.ndjson: emptied to 0 bytes."
        ),
        "notes":    "Multiple 1b failure modes in one extract.",
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _capture(fn, *args, **kwargs):
    """Call fn(*args, **kwargs), capturing stdout. Returns (result, captured_stdout)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


def _resolve_jar():
    """Return path to HAPI validator JAR if found, else None."""
    if HAPI_JAR.exists():
        return str(HAPI_JAR)
    if VALIDATOR_CLI_JAR.exists():
        return str(VALIDATOR_CLI_JAR)
    return None


def _1b_overall(report: dict) -> str:
    """Determine overall 1b status string from a stage1b report dict."""
    s = report.get("summary", {})
    failed = s.get("files_failed", 0)
    empty = s.get("files_empty", 0)
    if failed > 0:
        return "FAIL"
    if empty > 0:
        return "EMPTY"
    return "PASS"


def _1c_status(report: dict) -> str:
    """Determine 1c pass/fail from a stage1c sub-pass report dict."""
    errors = report.get("summary", {}).get("error_count", 0)
    return "FAIL" if errors > 0 else "PASS"


def run_fixture(fixture_def: dict, jar_path, out_base: Path) -> dict:
    name = fixture_def["name"]
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")

    # Build and write fixture
    src = _source_files()
    files = fixture_def["builder"](src)
    fixture_dir = FIXTURES_DIR / name
    _write_fixture(fixture_dir, files)

    # Output directory for reports
    rpt_dir = out_base / name
    rpt_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "fixture": name,
        "injected": fixture_def["injected"],
        "expected": fixture_def["expected"],
        "notes": fixture_def["notes"],
        "stages": {},
    }

    # --- Stage 1a-ii ---
    print(f"\n  [1a-ii] Running stage1a2...")
    rpt_1a2_path = str(rpt_dir / "stage1a2.json")
    try:
        rpt_1a2, _ = _capture(
            stage1a2.run,
            ndjson_dir=str(fixture_dir),
            engagement=name,
            output_path=rpt_1a2_path,
        )
        status_1a2 = rpt_1a2.get("status", "UNKNOWN")
        failed_checks_1a2 = [c["check"] for c in rpt_1a2.get("checks", []) if not c["passed"]]
        result["stages"]["1a2"] = {
            "status": status_1a2,
            "failed_checks": failed_checks_1a2,
            "report_path": rpt_1a2_path,
        }
        print(f"         → {status_1a2}" + (f"  failed: {failed_checks_1a2}" if failed_checks_1a2 else ""))
    except SystemExit as e:
        result["stages"]["1a2"] = {"status": "ERROR", "error": f"sys.exit({e.code})"}
        print(f"         → ERROR (sys.exit {e.code})")
    except Exception as e:
        result["stages"]["1a2"] = {"status": "ERROR", "error": str(e)}
        print(f"         → ERROR: {e}")

    # --- Stage 1b ---
    print(f"\n  [1b]   Running stage1b...")
    rpt_1b_path = str(rpt_dir / "stage1b.json")
    try:
        rpt_1b, _ = _capture(
            stage1b.run,
            ndjson_dir=str(fixture_dir),
            output_path=rpt_1b_path,
        )
        status_1b = _1b_overall(rpt_1b)
        files_failed = rpt_1b.get("summary", {}).get("files_failed", 0)
        files_empty = rpt_1b.get("summary", {}).get("files_empty", 0)
        result["stages"]["1b"] = {
            "status": status_1b,
            "files_failed": files_failed,
            "files_empty": files_empty,
            "report_path": rpt_1b_path,
            "file_details": [
                {
                    "file": fr["file"],
                    "passed": fr.get("passed"),
                    "empty": fr.get("empty"),
                    "failed_checks": [k for k, v in fr.get("checks", {}).items() if not v],
                    "issue_counts": fr.get("issue_counts", {}),
                }
                for fr in rpt_1b.get("files", [])
                if not fr.get("passed") or fr.get("empty")
            ],
        }
        print(f"         → {status_1b}  (failed={files_failed}, empty={files_empty})")
    except SystemExit as e:
        result["stages"]["1b"] = {"status": "ERROR", "error": f"sys.exit({e.code})"}
        print(f"         → ERROR (sys.exit {e.code})")
    except Exception as e:
        result["stages"]["1b"] = {"status": "ERROR", "error": str(e)}
        print(f"         → ERROR: {e}")

    # --- Stage 1c ---
    should_run_1c = fixture_def["run_1c"]
    if should_run_1c and jar_path is None:
        result["stages"]["1c-i"] = {"status": "SKIPPED", "reason": "HAPI validator JAR not found"}
        result["stages"]["1c-ii"] = {"status": "SKIPPED", "reason": "HAPI validator JAR not found"}
        print(f"\n  [1c]   SKIPPED — HAPI validator JAR not found")
    elif should_run_1c:
        print(f"\n  [1c]   Running stage1c (jar: {jar_path})...")
        rpt_1c_dir = str(rpt_dir / "stage1c")
        Path(rpt_1c_dir).mkdir(parents=True, exist_ok=True)
        try:
            # Count resource lines for each file (stage1c can use this)
            fixture_files = sorted(Path(str(fixture_dir)).glob("*.ndjson"))
            resource_counts = {}
            for f in fixture_files:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    resource_counts[f.stem] = len([ln for ln in content.splitlines() if ln.strip()])
                except Exception:
                    resource_counts[f.stem] = 0

            rpts_1c, _ = _capture(
                stage1c.run,
                ndjson_dir=str(fixture_dir),
                engagement=name,
                output_dir=rpt_1c_dir,
                backend="hapi-cli",
                validator_jar=jar_path,
            )
            for rpt in rpts_1c:
                stage_key = rpt.get("stage", "unknown")
                err_count = rpt.get("summary", {}).get("error_count", 0)
                warn_count = rpt.get("summary", {}).get("warning_count", 0)
                status_1c = _1c_status(rpt)
                result["stages"][stage_key] = {
                    "status": status_1c,
                    "error_count": err_count,
                    "warning_count": warn_count,
                    "by_resource_type": rpt.get("by_resource_type", []),
                    "report_path": str(rpt_dir / "stage1c" / f"stage{stage_key}-{name}.json"),
                }
                print(f"         [{stage_key}] → {status_1c}  (errors={err_count}, warnings={warn_count})")
        except SystemExit as e:
            result["stages"]["1c-i"] = {"status": "ERROR", "error": f"sys.exit({e.code})"}
            result["stages"]["1c-ii"] = {"status": "ERROR", "error": f"sys.exit({e.code})"}
            print(f"         → ERROR (sys.exit {e.code})")
        except Exception as e:
            result["stages"]["1c-i"] = {"status": "ERROR", "error": str(e)}
            result["stages"]["1c-ii"] = {"status": "ERROR", "error": str(e)}
            print(f"         → ERROR: {e}")
    else:
        result["stages"]["1c-i"] = {"status": "NOT_RUN"}
        result["stages"]["1c-ii"] = {"status": "NOT_RUN"}

    return result


# ---------------------------------------------------------------------------
# Text summary table
# ---------------------------------------------------------------------------

def print_summary_table(all_results: list[dict]) -> str:
    header = f"{'Fixture':<40}  {'1a-ii':<8}  {'1b':<8}  {'1c-i':<8}  {'1c-ii':<8}  Notes"
    separator = "-" * 110
    lines = [header, separator]
    for r in all_results:
        name = r["fixture"]
        stages = r["stages"]
        s_1a2 = stages.get("1a2", {}).get("status", "---")
        s_1b  = stages.get("1b",  {}).get("status", "---")
        s_1ci = stages.get("1c-i",  {}).get("status", "---")
        s_1cii = stages.get("1c-ii", {}).get("status", "---")
        notes = r.get("notes", "")[:60]
        lines.append(f"{name:<40}  {s_1a2:<8}  {s_1b:<8}  {s_1ci:<8}  {s_1cii:<8}  {notes}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analysis writer
# ---------------------------------------------------------------------------

def write_analysis(all_results: list[dict], jar_found: bool) -> None:
    lines = []
    lines.append("# CDAR UC1 — Fixture Pipeline Analysis")
    lines.append("")
    lines.append("Generated by `tests/generate_fixtures.py`.")
    lines.append(
        f"HAPI Validator JAR: {'found' if jar_found else 'NOT FOUND — Stage 1c results are SKIPPED'}."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## Summary Table")
    lines.append("")
    lines.append("```")
    lines.append(print_summary_table(all_results))
    lines.append("```")
    lines.append("")
    lines.append("Status key: PASS / FAIL / EMPTY / SKIPPED / NOT_RUN / ERROR")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-fixture detail
    lines.append("## Per-Fixture Analysis")
    lines.append("")

    false_negatives = []  # list of (fixture_name, stage, description)
    unexpected_results = []

    for r in all_results:
        name = r["fixture"]
        injected = r["injected"]
        expected = r.get("expected", {})
        notes = r.get("notes", "")
        stages = r["stages"]

        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"**Injected errors:** {injected}")
        lines.append("")
        lines.append(f"**Notes:** {notes}")
        lines.append("")

        # Results table for this fixture
        lines.append("| Stage | Status | Detail |")
        lines.append("|-------|--------|--------|")

        for stage_key in ["1a2", "1b", "1c-i", "1c-ii"]:
            sd = stages.get(stage_key, {})
            status = sd.get("status", "---")

            detail_parts = []
            if stage_key == "1a2" and sd.get("failed_checks"):
                detail_parts.append(f"failed checks: {', '.join(sd['failed_checks'])}")
            if stage_key == "1b":
                fc = sd.get("files_failed", 0)
                fe = sd.get("files_empty", 0)
                if fc or fe:
                    detail_parts.append(f"{fc} file(s) failed, {fe} empty")
                file_details = sd.get("file_details", [])
                for fd in file_details:
                    failed_checks = fd.get("failed_checks", [])
                    if failed_checks:
                        detail_parts.append(f"{fd['file']}: {', '.join(failed_checks)}")
            if stage_key in ("1c-i", "1c-ii"):
                ec = sd.get("error_count")
                wc = sd.get("warning_count")
                if ec is not None:
                    detail_parts.append(f"{ec} errors, {wc} warnings")
                reason = sd.get("reason")
                if reason:
                    detail_parts.append(reason)

            detail_str = "; ".join(detail_parts) if detail_parts else "—"
            lines.append(f"| {stage_key} | **{status}** | {detail_str} |")

            # Evaluate expected vs actual
            exp_status = expected.get(stage_key)
            if exp_status and status not in ("NOT_RUN", "SKIPPED", "ERROR"):
                # Normalize: EMPTY treated as special pass-ish for 1b
                actual = status
                if stage_key == "1b" and exp_status == "WARN" and actual == "EMPTY":
                    pass  # treat as expected
                elif exp_status != actual:
                    # Check if this is a false negative (expected FAIL, got PASS)
                    if exp_status == "FAIL" and actual == "PASS":
                        false_negatives.append((name, stage_key,
                            f"Expected FAIL but got PASS — pipeline did not detect injected error"))
                    else:
                        unexpected_results.append((name, stage_key,
                            f"Expected {exp_status}, got {actual}"))

        lines.append("")

        # Stage 1b file-level breakdown
        b1_details = stages.get("1b", {}).get("file_details", [])
        if b1_details:
            lines.append("**Stage 1b file-level failures:**")
            lines.append("")
            for fd in b1_details:
                fn = fd["file"]
                fc = fd.get("failed_checks", [])
                ic = fd.get("issue_counts", {})
                status_str = "EMPTY" if fd.get("empty") else ("FAIL" if fc else "PASS")
                lines.append(f"- `{fn}` — **{status_str}**")
                if fc:
                    lines.append(f"  - Failed checks: {', '.join(fc)}")
                if any(v > 0 for v in ic.values()):
                    lines.append(f"  - Issue counts: {ic}")
            lines.append("")

        # 1c breakdown by resource type
        for sp_key in ["1c-i", "1c-ii"]:
            sp_data = stages.get(sp_key, {})
            brt = sp_data.get("by_resource_type", [])
            if brt:
                errored = [b for b in brt if b.get("errors", 0) > 0]
                if errored:
                    lines.append(f"**Stage {sp_key} errors by resource type:**")
                    lines.append("")
                    for b in errored:
                        lines.append(f"- `{b['resource_type']}`: {b['errors']} errors, {b['warnings']} warnings")
                        for te in b.get("top_errors", [])[:3]:
                            lines.append(f"  - [{te['code']}] `{te['element']}` × {te['count']}: {te.get('examples', [''])[0][:120]}")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # False negatives section
    lines.append("## False Negatives (Pipeline Missed Injected Errors)")
    lines.append("")
    if false_negatives:
        lines.append("The following injected errors were NOT detected by the pipeline:")
        lines.append("")
        for fn_name, fn_stage, fn_desc in false_negatives:
            lines.append(f"- **{fn_name}** / Stage {fn_stage}: {fn_desc}")
        lines.append("")
    else:
        lines.append("No false negatives detected — all injected errors were caught by the expected stage.")
        lines.append("")

    # Unexpected results section
    lines.append("## Unexpected Results")
    lines.append("")
    if unexpected_results:
        for ur_name, ur_stage, ur_desc in unexpected_results:
            lines.append(f"- **{ur_name}** / Stage {ur_stage}: {ur_desc}")
        lines.append("")
    else:
        lines.append("No unexpected results detected.")
        lines.append("")

    # Recommendations section
    lines.append("## Recommendations for Code Changes")
    lines.append("")

    recs = []

    # Check fixture-02: UTF-8 detection
    f02 = next((r for r in all_results if "02" in r["fixture"]), None)
    if f02:
        s1b = f02["stages"].get("1b", {}).get("status")
        if s1b == "PASS":
            recs.append(
                "**Stage 1b — UTF-8 detection (fixture-02):** "
                "The validator currently uses `read_bytes().decode('utf-8')` which raises `UnicodeDecodeError` "
                "on a true encoding failure. The test showed this does NOT catch mid-line byte corruption if "
                "the file is otherwise valid UTF-8 structure. Consider stricter validation: validate each line "
                "independently, or scan for non-UTF-8 byte sequences line by line."
            )

    # Check fixture-04: missing resourceType
    f04 = next((r for r in all_results if "04" in r["fixture"]), None)
    if f04:
        s1b = f04["stages"].get("1b", {}).get("status")
        if s1b == "PASS":
            recs.append(
                "**Stage 1b — Missing resourceType detection (fixture-04):** "
                "Records without `resourceType` are currently not causing a file-level FAIL in the "
                "overall 1b status. Review the `resource_type_present` check logic — the check sets "
                "`passed=False` only when ALL checks pass, but the overall stage status may still read PASS "
                "if other files compensate. The issue count is tracked but may not surface clearly."
            )

    # Check fixture-05: filename mismatch — check both 1a2 and 1b
    f05 = next((r for r in all_results if "05" in r["fixture"]), None)
    if f05:
        s1a2 = f05["stages"].get("1a2", {}).get("status")
        s1b = f05["stages"].get("1b", {}).get("status")
        if s1a2 == "PASS":
            recs.append(
                "**Stage 1a2 — Filename/content mismatch (fixture-05):** "
                "When Procedure.ndjson contains Observation records, 1a2 parses the content and sees "
                "Observation resources (not Procedure). This means 1a2 counts Observation but has no Procedure. "
                "The `single_type_per_file` check in 1a2 fires only if multiple types appear in ONE file — "
                "it does not fire when the filename stem doesn't match the content type. "
                "Recommend adding a `filename_matches_content` check to stage1a2 that cross-references "
                "filename stems against detected resource types per file."
            )

    # Check fixture-06: empty files behavior
    f06 = next((r for r in all_results if "06" in r["fixture"]), None)
    if f06:
        s1b = f06["stages"].get("1b", {}).get("status")
        if s1b not in ("FAIL", "EMPTY"):
            recs.append(
                "**Stage 1b — Empty file handling (fixture-06):** "
                "Empty files are currently tracked separately from failures. An empty Coverage.ndjson "
                "represents a complete absence of coverage data — this should arguably be a WARN or FAIL "
                "for required resource types. Consider adding a check in 1a2 that counts empty files and "
                "flags empty files for DEQM-required resource types as a finding."
            )

    # Check fixture-07: mixed types
    f07 = next((r for r in all_results if "07" in r["fixture"]), None)
    if f07:
        s1a2 = f07["stages"].get("1a2", {}).get("status")
        if s1a2 == "PASS":
            recs.append(
                "**Stage 1a2 — Mixed resource types in file (fixture-07):** "
                "When Condition.ndjson contains appended Observation records, 1a2 should flag "
                "`single_type_per_file` as FAIL. Verify that this check is actually triggered. "
                "If 1a2 passes here, the `multi_type_files` detection loop may not iterate "
                "all files correctly, or the result is not propagating to the overall status."
            )

    # 1c-specific recs if JAR found
    if jar_found:
        f10 = next((r for r in all_results if "10" in r["fixture"]), None)
        if f10:
            s1ci = f10["stages"].get("1c-i", {}).get("status")
            if s1ci == "PASS":
                recs.append(
                    "**Stage 1c-i — Missing required R4 fields (fixture-10):** "
                    "Stripping `status` from Observation and `status`+`intent` from MedicationRequest "
                    "should produce HAPI R4 errors. If 1c-i passed, investigate whether HAPI CLI "
                    "is actually validating the resources or whether the JAR version is too lenient. "
                    "Try running the validator manually on a single stripped Observation record."
                )
        f11 = next((r for r in all_results if "11" in r["fixture"]), None)
        if f11:
            s1cii = f11["stages"].get("1c-ii", {}).get("status")
            if s1cii == "PASS":
                recs.append(
                    "**Stage 1c-ii — US Core required fields (fixture-11):** "
                    "Removing Patient.identifier and Condition.category should produce US Core 6.1.0 "
                    "conformance errors. If 1c-ii passed, verify that the US Core 6.1.0 IG is being "
                    "correctly loaded by HAPI (`-ig hl7.fhir.us.core#6.1.0`). "
                    "Also confirm that the test resources have the appropriate US Core profile URLs "
                    "in `meta.profile` — HAPI may not auto-apply US Core profiles without them."
                )
    else:
        recs.append(
            "**Stage 1c — HAPI Validator JAR not found:** "
            f"No JAR was found at `{HAPI_JAR}` or `{VALIDATOR_CLI_JAR}`. "
            "Stage 1c (1c-i and 1c-ii) was skipped for all fixtures. "
            "To run conformance tests: download `validator_cli.jar` from "
            "https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar "
            f"and place it at `{VALIDATOR_CLI_JAR}` (or `{HAPI_JAR}`)."
        )

    # General recommendations
    recs.append(
        "**Stage 1b — Overall PASS/FAIL aggregation:** "
        "Currently `stage1b.run()` prints per-file results and returns a report dict, but the script "
        "uses `files_failed > 0` to determine overall FAIL. Ensure the pipeline's orchestrator layer "
        "`stage1/orchestrate.py` applies the same aggregation logic so the overall pipeline halts "
        "correctly on 1b failures before Stage 1c."
    )

    recs.append(
        "**Stage 1a2 — Cross-referencing filename vs. content resource type:** "
        "The current `single_type_per_file` check catches files with multiple types but not the case "
        "where a file has exactly one type that doesn't match the filename. Adding a dedicated "
        "`filename_matches_content` check would catch fixture-05-style mislabeling."
    )

    if recs:
        for i, rec in enumerate(recs, 1):
            lines.append(f"{i}. {rec}")
            lines.append("")
    else:
        lines.append("No specific code changes recommended — all checks performed as expected.")
        lines.append("")

    ANALYSIS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nAnalysis written to: {ANALYSIS_MD}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("CDAR UC1 — Fixture Generator + Pipeline Test Runner")
    print(f"Source: {SOURCE_DIR}")
    print(f"Fixtures: {FIXTURES_DIR}")
    print()

    jar_path = _resolve_jar()
    jar_found = jar_path is not None
    if jar_found:
        print(f"HAPI Validator JAR: {jar_path}")
    else:
        print(f"HAPI Validator JAR: NOT FOUND — Stage 1c will be skipped")
        print(f"  Checked: {HAPI_JAR}")
        print(f"  Checked: {VALIDATOR_CLI_JAR}")

    all_results = []
    for fixture_def in FIXTURES:
        # Override run_1c if no JAR
        if not jar_found:
            fixture_def = dict(fixture_def)  # don't mutate global
            fixture_def["run_1c"] = False
        result = run_fixture(fixture_def, jar_path, OUTPUT_DIR / "reports")
        all_results.append(result)

    # Write results JSON
    RESULTS_JSON.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nResults written to: {RESULTS_JSON}")

    # Print summary table
    print("\n" + "=" * 110)
    print("SUMMARY TABLE")
    print("=" * 110)
    table = print_summary_table(all_results)
    print(table)

    # Write analysis
    write_analysis(all_results, jar_found)

    return all_results


if __name__ == "__main__":
    main()
