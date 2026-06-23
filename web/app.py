"""
CDAR UC1 — Local Assessment Server

Accepts NDJSON file uploads (individual files or zip/tar.gz),
optionally runs Stage 1a against a live FHIR server URL,
then streams Stage 1b + 1c progress via SSE and serves the HTML report.

Usage:
    pip install -e '.[web]'
    uvicorn web.app:app --reload --port 8000
    open http://localhost:8000
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import uuid
import zipfile
import tarfile
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

_ROOT   = Path(__file__).resolve().parents[1]
_STAGE1 = _ROOT / "stage1"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_STAGE1))

import stage1a_bulk_fhir_export_preflight  as _1a
import stage1a2_bulk_fhir_extract_preflight as _1a2
import stage1b_ndjson_validator            as _1b
import stage1c_fhir_uscore_validator       as _1c
from findings import derive_findings
from report   import render_html
from stage2.anonymize_extract import run as run_stage2

app = FastAPI(title="CDAR UC1 Assessment", docs_url=None, redoc_url=None)

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# In-memory run store: run_id → {"status": ..., "html": ..., "error": ...}
_RUNS: dict[str, dict] = {}

VALIDATOR_JAR = os.environ.get("FHIR_VALIDATOR_JAR", str(_ROOT / "tools" / "validator_cli.jar"))


def _resolve_java() -> str:
    """Return a working java binary, checking Homebrew fallbacks on macOS."""
    import shutil
    import subprocess
    candidate = os.environ.get("JAVA_BIN", "java")
    if shutil.which(candidate):
        try:
            r = subprocess.run([candidate, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return candidate
        except Exception:
            pass
    for fallback in [
        "/opt/homebrew/opt/openjdk/bin/java",
        "/usr/local/opt/openjdk/bin/java",
    ]:
        if Path(fallback).exists():
            return fallback
    return candidate


JAVA_BIN = _resolve_java()
TX_MODE  = os.environ.get("TX_MODE", "local")


# ---------------------------------------------------------------------------
# Upload page
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _TEMPLATES.TemplateResponse(request=request, name="upload.html")


# ---------------------------------------------------------------------------
# Submit assessment
# ---------------------------------------------------------------------------

@app.post("/assess")
async def assess(
    files:         list[UploadFile] = File(default=[]),
    fhir_url:      str              = Form(""),
    server_type:   str              = Form("hapi"),
    eng_name:      str              = Form("client"),
    client_id:     str              = Form(""),
    client_secret: str              = Form(""),
    redact:        bool             = Form(False),
):
    fhir_url = fhir_url.strip()
    if not files and not fhir_url:
        raise HTTPException(status_code=400, detail="Provide files to validate, a FHIR server URL, or both.")

    run_id = str(uuid.uuid4())[:8]
    _RUNS[run_id] = {"status": "running", "html": None, "error": None}

    tmp = Path(tempfile.mkdtemp(prefix=f"dqar-{run_id}-"))
    ndjson_dir = tmp / "ndjson"
    ndjson_dir.mkdir()

    try:
        for upload in files:
            dest = tmp / upload.filename
            content = await upload.read()
            dest.write_bytes(content)

            name = upload.filename.lower()
            if name.endswith(".zip"):
                with zipfile.ZipFile(dest) as zf:
                    for member in zf.namelist():
                        if member.endswith(".ndjson"):
                            zf.extract(member, ndjson_dir)
                            extracted = ndjson_dir / member
                            flat = ndjson_dir / Path(member).name
                            if extracted != flat:
                                flat.write_bytes(extracted.read_bytes())
                                extracted.unlink()
            elif name.endswith((".tar.gz", ".tgz")):
                import gzip as _gzip
                with tarfile.open(dest) as tf:
                    for member in tf.getmembers():
                        basename = Path(member.name).name
                        if basename.startswith("._"):
                            continue
                        if member.name.endswith(".ndjson.gz"):
                            fobj = tf.extractfile(member)
                            if fobj:
                                flat = ndjson_dir / basename[:-3]  # strip .gz
                                flat.write_bytes(_gzip.decompress(fobj.read()))
                        elif member.name.endswith(".ndjson"):
                            tf.extract(member, ndjson_dir)
                            extracted = ndjson_dir / member.name
                            flat = ndjson_dir / basename
                            if extracted != flat:
                                flat.write_bytes(extracted.read_bytes())
                                extracted.unlink()
            elif name.endswith(".ndjson"):
                shutil.copy(dest, ndjson_dir / upload.filename)

        # If files were provided but none were NDJSON, error
        ndjson_files = list(ndjson_dir.glob("*.ndjson"))
        if files and not ndjson_files:
            raise ValueError("No .ndjson files found in the upload. Upload .ndjson files directly or as a .zip / .tar.gz.")

    except Exception as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        _RUNS[run_id] = {"status": "error", "html": None, "error": str(exc)}
        raise HTTPException(status_code=400, detail=str(exc))

    # Store run metadata for the SSE stream to use
    _RUNS[run_id]["tmp"]           = str(tmp)
    _RUNS[run_id]["ndjson_dir"]   = str(ndjson_dir)
    _RUNS[run_id]["fhir_url"]     = fhir_url.strip()
    _RUNS[run_id]["server_type"]  = server_type.strip() if server_type.strip() in ("aidbox", "hapi", "medplum") else "hapi"
    _RUNS[run_id]["eng_name"]     = eng_name.strip() or "client"
    _RUNS[run_id]["client_id"]    = client_id.strip()
    _RUNS[run_id]["client_secret"]= client_secret.strip()
    _RUNS[run_id]["redact"]       = redact

    return {"run_id": run_id}


# ---------------------------------------------------------------------------
# SSE progress stream
# ---------------------------------------------------------------------------

@app.get("/stream/{run_id}")
async def stream(run_id: str):
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="Run not found")

    return StreamingResponse(
        _run_pipeline(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


async def _run_pipeline(run_id: str) -> AsyncGenerator[str, None]:
    run   = _RUNS[run_id]
    tmp   = Path(run["tmp"])
    ndjson_dir    = run["ndjson_dir"]
    fhir_url      = run["fhir_url"]
    server_type   = run["server_type"]
    eng_name      = run["eng_name"]
    client_id     = run["client_id"]
    client_secret = run["client_secret"]
    redact        = run.get("redact", False)
    reports: dict = {}
    b_ok = False

    out_dir = tmp / "reports"
    out_dir.mkdir()

    loop = asyncio.get_event_loop()

    try:
        # ----------------------------------------------------------------
        # Stage 1a (optional — only if FHIR server URL provided)
        # ----------------------------------------------------------------
        if fhir_url:
            yield _sse("progress", json.dumps({"stage": "1a", "msg": f"Stage 1a — connecting to {fhir_url}", "status": "running"}))
            # Map form credentials to the correct engagement fields per server type.
            # Aidbox uses OAuth2 client_credentials (client_id / client_secret).
            # HAPI and others use HTTP Basic auth (basic_user / basic_password).
            if server_type in ("aidbox", "medplum"):
                # Normalize: strip any FHIR sub-path the user may have included.
                # EngagementConfig computes fhir_base from base_url, so the root
                # URL is required (e.g. https://api.medplum.com not .../fhir/R4).
                _base = fhir_url.rstrip("/")
                if server_type == "medplum":
                    for _suffix in ("/fhir/R4", "/fhir/r4"):
                        if _base.endswith(_suffix):
                            _base = _base[: -len(_suffix)]
                elif server_type == "aidbox":
                    for _suffix in ("/fhir",):
                        if _base.endswith(_suffix):
                            _base = _base[: -len(_suffix)]
                eng_config = {
                    "name":          eng_name,
                    "server_type":   server_type,
                    "base_url":      _base,
                    "client_id":     client_id or None,
                    "client_secret": client_secret or None,
                }
            else:
                eng_config = {
                    "name":          eng_name,
                    "server_type":   "hapi",
                    "base_url":      fhir_url,
                    "basic_user":    client_id or None,
                    "basic_password": client_secret or None,
                }
            eng_path = tmp / "engagement.json"
            eng_path.write_text(json.dumps(eng_config))
            export_ndjson_dir = str(tmp / "export_ndjson")
            try:
                r1a = await loop.run_in_executor(None, lambda: _1a.run(
                    engagement_path=str(eng_path),
                    output_path=str(out_dir / f"stage1a-{eng_name}.json"),
                    download_dir=export_ndjson_dir,
                ))
                reports["stage1a"] = r1a
                status = r1a.get("status", "UNKNOWN") if r1a else "UNKNOWN"
                downloaded = r1a.get("downloaded_files", []) if r1a else []
                msg = f"Stage 1a — {status}"
                if downloaded:
                    msg += f" · {len(downloaded)} NDJSON file(s) extracted"
                yield _sse("progress", json.dumps({"stage": "1a", "msg": msg, "status": status}))
                # If Stage 1a downloaded NDJSON and no files were uploaded, use the export
                if downloaded and not list(Path(ndjson_dir).glob("*.ndjson")):
                    import shutil as _shutil
                    for f in downloaded:
                        _shutil.copy(f, ndjson_dir)
                    yield _sse("progress", json.dumps({
                        "stage": "1a", "status": status,
                        "msg": f"↳ {len(downloaded)} exported file(s) queued for Stage 1b/1c validation",
                    }))
            except Exception as exc:
                reports["stage1a"] = {"status": "ERROR", "error": str(exc)}
                yield _sse("progress", json.dumps({"stage": "1a", "msg": f"Stage 1a — ERROR: {exc}", "status": "ERROR"}))
        else:
            reports["stage1a"] = None
            yield _sse("progress", json.dumps({"stage": "1a", "msg": "Stage 1a — skipped (no FHIR server URL provided)", "status": "SKIPPED"}))

        # ----------------------------------------------------------------
        # Stage 1a-ii + 1b + 1c  (skipped if no NDJSON files were uploaded)
        # ----------------------------------------------------------------
        has_ndjson = bool(list(Path(ndjson_dir).glob("*.ndjson")))
        if not has_ndjson:
            reports["stage1a_ii"] = reports["stage1b"] = reports["stage1c_i"] = reports["stage1c_ii"] = None
            for stage in ("1a-ii", "1b", "1c-i", "1c-ii"):
                yield _sse("progress", json.dumps({"stage": stage, "status": "SKIPPED",
                    "msg": f"Stage {stage} — skipped (no files uploaded, Stage 1a-i only)"}))
        else:
            # Stage 1a-ii: extract packaging (quick, runs before 1b)
            try:
                r1a2 = await loop.run_in_executor(None, lambda: _1a2.run(
                    ndjson_dir=ndjson_dir,
                    engagement=eng_name,
                    output_path=str(out_dir / f"stage1a2-{eng_name}.json"),
                ))
                reports["stage1a_ii"] = r1a2
                status = r1a2.get("status", "UNKNOWN") if r1a2 else "UNKNOWN"
                s = r1a2.get("summary", {}) if r1a2 else {}
                yield _sse("progress", json.dumps({
                    "stage": "1a-ii", "status": status,
                    "msg": f"Stage 1a-ii — {s.get('total_resources', 0):,} resources · {s.get('resource_types_found', 0)} types",
                }))
            except Exception as exc:
                reports["stage1a_ii"] = {"status": "ERROR", "error": str(exc)}
                yield _sse("progress", json.dumps({"stage": "1a-ii", "msg": f"Stage 1a-ii — ERROR: {exc}", "status": "ERROR"}))

            yield _sse("progress", json.dumps({"stage": "1b", "msg": "Stage 1b — validating NDJSON structure…", "status": "running"}))
            try:
                r1b = await loop.run_in_executor(None, lambda: _1b.run(
                    ndjson_dir=ndjson_dir,
                    output_path=str(out_dir / f"stage1b-{eng_name}.json"),
                ))
                reports["stage1b"] = r1b
                s = r1b.get("summary", {})
                msg = (f"Stage 1b — {s.get('files_passed', 0)}/{s.get('files_checked', 0)} files passed · "
                       f"{s.get('total_records', 0):,} records")
                status = "PASS" if s.get("files_failed", 0) == 0 else "FAIL"
                yield _sse("progress", json.dumps({"stage": "1b", "msg": msg, "status": status}))
                b_ok = status == "PASS"
            except Exception as exc:
                reports["stage1b"] = {"status": "ERROR", "error": str(exc)}
                yield _sse("progress", json.dumps({"stage": "1b", "msg": f"Stage 1b — ERROR: {exc}", "status": "ERROR"}))
                b_ok = False

            if not b_ok:
                reports["stage1c_i"] = reports["stage1c_ii"] = None
                yield _sse("progress", json.dumps({
                    "stage": "1c", "status": "BLOCKED",
                    "msg": "Stage 1c — blocked (fix Stage 1b failures first)",
                }))
            else:
                jar_ok = Path(VALIDATOR_JAR).exists()
                java_ok = False
                if jar_ok:
                    import subprocess as _sp
                    try:
                        jr = _sp.run([JAVA_BIN, "-version"], capture_output=True, timeout=10)
                        java_ok = jr.returncode == 0
                    except Exception:
                        java_ok = False

                if not jar_ok or not java_ok:
                    msg = (
                        f"HAPI Validator JAR not found at {VALIDATOR_JAR}"
                        if not jar_ok else
                        f"Java runtime not found ('{JAVA_BIN}' not executable). "
                        "Install Java 17+ to use the HAPI CLI backend — "
                        "download from https://adoptium.net/"
                    )
                    reports["stage1c_i"] = reports["stage1c_ii"] = {
                        "status": "ERROR",
                        "error": msg,
                    }
                    yield _sse("progress", json.dumps({
                        "stage": "1c", "status": "ERROR",
                        "msg": f"Stage 1c — {msg}",
                    }))
                else:
                    yield _sse("progress", json.dumps({
                        "stage": "1c-i", "status": "running",
                        "msg": "Stage 1c-I — Base FHIR R4 validation (3–5 min)…",
                    }))
                    yield _sse("progress", json.dumps({
                        "stage": "1c-ii", "status": "running",
                        "msg": "Stage 1c-II — US Core 6.1.0 validation queued…",
                    }))
                    try:
                        r1c = await loop.run_in_executor(None, lambda: _1c.run(
                            ndjson_dir    = ndjson_dir,
                            engagement    = eng_name,
                            output_dir    = str(out_dir),
                            backend       = "hapi-cli",
                            validator_jar = VALIDATOR_JAR,
                            java_bin      = JAVA_BIN,
                            tx_mode       = TX_MODE,
                        ))
                        reports["stage1c_i"]  = r1c[0] if len(r1c) > 0 else None
                        reports["stage1c_ii"] = r1c[1] if len(r1c) > 1 else None
                        for sub, key in [("1c-i", "stage1c_i"), ("1c-ii", "stage1c_ii")]:
                            r = reports[key]
                            if r:
                                ec = r.get("summary", {}).get("error_count", 0)
                                st = "PASS" if ec == 0 else "FAIL"
                                yield _sse("progress", json.dumps({
                                    "stage": sub, "status": st,
                                    "msg": f"Stage {sub} — {ec:,} errors",
                                }))
                    except Exception as exc:
                        reports["stage1c_i"]  = {"status": "ERROR", "error": str(exc)}
                        reports["stage1c_ii"] = None
                        yield _sse("progress", json.dumps({
                        "stage": "1c-i", "status": "ERROR",
                        "msg": f"Stage 1c — ERROR: {exc}",
                    }))

        # ----------------------------------------------------------------
        # Findings + HTML report
        # ----------------------------------------------------------------
        yield _sse("progress", json.dumps({"stage": "report", "msg": "Generating findings report…"}))

        findings = derive_findings(reports)
        combined = {
            "report_type":  "dqar-stage1-assessment",
            "engagement":   eng_name,
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "stage1a":      reports.get("stage1a"),
            "stage1a_ii":   reports.get("stage1a_ii"),
            "stage1b":      reports.get("stage1b"),
            "stage1c_i":    reports.get("stage1c_i"),
            "stage1c_ii":   reports.get("stage1c_ii"),
            "findings":     findings,
        }
        _RUNS[run_id]["combined"] = combined
        _RUNS[run_id]["status"]   = "done"

        # ------------------------------------------------------------------
        # Stage 2 — PHI redaction (Path B only, opt-in via the upload form)
        # ------------------------------------------------------------------
        redacted_ready = False
        if redact and has_ndjson and b_ok:
            yield _sse("progress", json.dumps({"stage": "stage2", "status": "running",
                "msg": "Stage 2 — redacting PHI for Sonian delivery…"}))
            try:
                redacted_dir = Path(tempfile.mkdtemp(prefix=f"dqar-redacted-{run_id}-"))
                await loop.run_in_executor(None, lambda: run_stage2(
                    ndjson_dir=ndjson_dir,
                    output_dir=str(redacted_dir),
                    engagement=eng_name,
                    output_path=str(out_dir / f"stage2-{eng_name}.json"),
                    fhir_server_url=fhir_url,
                    source_system_type=server_type,
                ))
                bundle_fd, bundle_path = tempfile.mkstemp(
                    prefix=f"dqar-redacted-{run_id}-", suffix=".tar.gz")
                os.close(bundle_fd)
                with tarfile.open(bundle_path, "w:gz") as tf:
                    for item in redacted_dir.iterdir():
                        # Never ship dotfiles (e.g. a stray salt file) in the
                        # deliverable — only the redacted extract + its summary.
                        if not item.name.startswith("."):
                            tf.add(item, arcname=item.name)
                shutil.rmtree(redacted_dir, ignore_errors=True)
                _RUNS[run_id]["redacted_bundle"] = bundle_path
                redacted_ready = True
                yield _sse("progress", json.dumps({"stage": "stage2", "status": "PASS",
                    "msg": "Stage 2 — anonymized extract ready for download"}))
            except Exception as exc:
                yield _sse("progress", json.dumps({"stage": "stage2", "status": "ERROR",
                    "msg": f"Stage 2 — ERROR: {exc}"}))
        elif redact:
            yield _sse("progress", json.dumps({"stage": "stage2", "status": "SKIPPED",
                "msg": "Stage 2 — skipped (no NDJSON uploaded, or Stage 1b has failures)"}))

        f_count = len(findings)
        t_counts = {1: 0, 2: 0, 3: 0}
        for f in findings:
            t_counts[f["tier"]] += 1

        yield _sse("done", json.dumps({
            "run_id":   run_id,
            "findings": f_count,
            "tier1":    t_counts[1],
            "tier2":    t_counts[2],
            "tier3":    t_counts[3],
            "redacted": redacted_ready,
        }))

    except Exception as exc:
        _RUNS[run_id]["status"] = "error"
        _RUNS[run_id]["error"]  = str(exc)
        yield _sse("error", json.dumps({"msg": str(exc)}))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Serve completed report
# ---------------------------------------------------------------------------

@app.get("/report/{run_id}", response_class=HTMLResponse)
async def report(run_id: str):
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["status"] == "error":
        raise HTTPException(status_code=500, detail=run.get("error", "Unknown error"))
    if run["status"] != "done" or not run.get("combined"):
        raise HTTPException(status_code=202, detail="Assessment still running")
    redacted_url = f"/redacted/{run_id}" if run.get("redacted_bundle") else ""
    ndjson_dir   = Path(run.get("ndjson_dir", ""))
    ndjson_url   = f"/ndjson/{run_id}" if ndjson_dir.exists() and any(ndjson_dir.glob("*.ndjson")) else ""
    return HTMLResponse(content=render_html(run["combined"], redacted_url=redacted_url, ndjson_url=ndjson_url))


# ---------------------------------------------------------------------------
# Serve Stage 2 anonymized extract (Path B only — present only if --redact
# was requested and the run produced one)
# ---------------------------------------------------------------------------

@app.get("/ndjson/{run_id}")
async def download_ndjson(run_id: str):
    """Return a zip of straight .ndjson files (no gzip inside) for the run's extract."""
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    ndjson_dir = Path(run.get("ndjson_dir", ""))
    files = sorted(ndjson_dir.glob("*.ndjson")) if ndjson_dir.exists() else []
    if not files:
        raise HTTPException(status_code=404, detail="No NDJSON files available for this run")

    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    buf.seek(0)

    eng_name = run.get("eng_name", "extract")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{eng_name}-ndjson.zip"'},
    )


@app.get("/redacted/{run_id}")
async def redacted(run_id: str):
    run = _RUNS.get(run_id)
    if not run or not run.get("redacted_bundle"):
        raise HTTPException(status_code=404, detail="No anonymized extract for this run")
    eng_name = run.get("eng_name", "client")
    return FileResponse(
        run["redacted_bundle"],
        media_type="application/gzip",
        filename=f"{eng_name}-redacted.tar.gz",
    )
