"""
FastAPI Server
==============
REST API backend for the Regulatory Circular Analyzer.
Serves static HTML/CSS/JS files and exposes API endpoints for:
  - Document upload and extraction
  - Regulatory paragraph analysis (with SSE streaming)
  - Excel export
  - Auth (simple role-based login)
  - Admin prompt management
  - Maker/Checker workflow
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from core.logger import get_logger

logger = get_logger(__name__)

# Ensure project root is on path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.document_extractor import DocumentExtractor
from services.paragraph_splitter import ParagraphSplitter
from services.regulatory_analyzer import RegulatoryAnalyzer
from services.excel_exporter import ExcelExporter
from services.database import (
    init_db,
    get_user_by_username, get_user_by_id,
    save_document, get_history, get_excel, get_document,
    get_db_prompt, save_prompt, delete_prompt, get_all_prompts,
    submit_for_review, get_checker_queue, claim_document,
    approve_document, reject_document, update_document_excel,
    get_unassigned_count, update_paragraph_result, update_document_results,
    merge_paragraphs, split_paragraph, reorder_paragraphs,
    delete_paragraph
)
import bcrypt
from core.schemas import RegulatoryParagraphAnalysis
from core.prompts import get_default_system_prompt, get_default_user_prompt_template
from config.settings import get_settings, KNOWN_OLLAMA_MODELS

# ------------------------------------------------------------------ #
#  App setup                                                         #
# ------------------------------------------------------------------ #
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Regulatory Circular Analyzer",
    description="GenAI-powered regulatory document analysis API",
    version="1.0.0",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).parent / "static"

# In-memory store for analysis jobs (session_id → state)
_analysis_store: dict[str, dict[str, Any]] = {}

# ------------------------------------------------------------------ #
#  Health check                                                      #
# ------------------------------------------------------------------ #
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ------------------------------------------------------------------ #
#  Config / model info                                               #
# ------------------------------------------------------------------ #
@app.get("/api/config")
async def get_config():
    """Return current LLM configuration and available Ollama models."""
    s = get_settings()
    return {
        "current_model":    s.llm_model,
        "litellm_base_url": s.litellm_base_url,
        "temperature":      s.llm_temperature,
        "known_models":     KNOWN_OLLAMA_MODELS,
    }


# ------------------------------------------------------------------ #
#  Auth endpoints (simple role-based login)                          #
# ------------------------------------------------------------------ #
@app.post("/api/auth/login")
async def login(body: dict):
    """
    Login with username and password.
    Body: { username: str, password: str }
    """
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Verify using native bcrypt (handles passlib's legacy hashes perfectly)
    try:
        is_valid = bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8'))
    except Exception:
        is_valid = False
        
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Remove password hash before returning
    del user["password_hash"]
    
    return {"user": user}


@app.get("/api/auth/user/{user_id}")
async def get_user(user_id: str):
    """Return user info by ID."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"user": user}


# ------------------------------------------------------------------ #
#  Admin — Prompt management                                         #
# ------------------------------------------------------------------ #
@app.get("/api/admin/prompts")
async def admin_get_prompts():
    """Return current prompts (from DB if admin-edited, else code defaults)."""
    db_prompts = get_all_prompts()
    return {
        "system": {
            "content": db_prompts.get("system") or get_default_system_prompt(),
            "is_custom": "system" in db_prompts,
        },
        "user": {
            "content": db_prompts.get("user") or get_default_user_prompt_template(),
            "is_custom": "user" in db_prompts,
        },
    }


@app.put("/api/admin/prompts")
async def admin_update_prompt(body: dict):
    """
    Save or update a prompt.
    Body: { prompt_type: 'system' | 'user', content: str, user_id: str }
    """
    prompt_type = body.get("prompt_type", "").strip()
    content = body.get("content", "").strip()
    user_id = body.get("user_id", "")

    if prompt_type not in ("system", "user"):
        raise HTTPException(status_code=400, detail="prompt_type must be 'system' or 'user'.")
    if not content:
        raise HTTPException(status_code=400, detail="Prompt content cannot be empty.")

    result = save_prompt(prompt_type, content, user_id)
    return {"status": "ok", **result}


@app.delete("/api/admin/prompts/{prompt_type}")
async def admin_reset_prompt(prompt_type: str):
    """Delete custom prompt to restore code default."""
    if prompt_type not in ("system", "user"):
        raise HTTPException(status_code=400, detail="prompt_type must be 'system' or 'user'.")
    deleted = delete_prompt(prompt_type)
    return {"status": "ok", "deleted": deleted}


# ------------------------------------------------------------------ #
#  Upload endpoint                                                   #
# ------------------------------------------------------------------ #
@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Accept a PDF or DOCX file, extract its text, split into paragraphs,
    and return the result as JSON.
    """
    allowed = {".pdf", ".docx"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Please upload .pdf or .docx."
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        extractor = DocumentExtractor()
        meta = extractor.extract_with_metadata(file_bytes, file.filename)
        #logger.info(f"Successfully extracted document '{file.filename}'. Metadata keys: {list(meta.keys())}")
        logger.info(f"Successfully extracted document '{file.filename}'. Metadata text: {meta['text']}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Extraction failed: {e}")

    try:
        splitter = ParagraphSplitter()
        paragraphs = splitter.split(meta["text"])
        logger.info(f"Successfully split document '{file.filename}'. Paragraphs: {paragraphs}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Paragraph splitting failed: {e}")

    return {
        "file_name": meta["file_name"],
        "file_size_kb": meta["file_size_kb"],
        "format": meta["format"],
        "page_count": meta["page_count"],
        "metadata": meta["metadata"],
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
        "text_preview": meta["text"][:2000],
    }


# ------------------------------------------------------------------ #
#  Analyze — start job & stream via SSE                             #
# ------------------------------------------------------------------ #
async def run_analysis_job(session_id: str):
    store = _analysis_store.get(session_id)
    if not store:
        return
    store["status"] = "running"
    paragraphs = store["paragraphs"]
    total = store["total"]
    analyzer = RegulatoryAnalyzer()

    try:
        logger.info(f"Starting background analysis job for session {session_id} with {total} paragraphs")
        for idx, paragraph in enumerate(paragraphs, start=1):
            if store["status"] == "cancelled":
                logger.info(f"Job {session_id} cancelled at paragraph {idx}")
                break
                
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    analyzer.analyze_paragraph,
                    paragraph, idx, total
                )
                result_dict = result.model_dump()
            except Exception as exc:
                result_dict = {
                    "paragraph_text": paragraph,
                    "para_type": "Error",
                    "has_effective_date": "No",
                    "effective_date": None,
                    "business_unit": "Unknown",
                    "theme": "Unknown",
                    "control_object_name": "Unknown",
                    "actionable": f"Analysis failed: {exc}",
                    "level_1": "Unknown",
                    "level_2": "Unknown",
                    "level_3": "Unknown",
                }

            is_skipped = (result_dict.get("para_type") == "Information Para" and result_dict.get("actionable") == "Not Applicable")
            
            if not is_skipped:
                store["results"].append(result_dict)
                
            store["current"] = idx
            
            store["events"].append({
                "type": "progress",
                "current": idx,
                "total": total,
                "result": result_dict,
                "skipped": is_skipped
            })

        if store["status"] == "running":
            logger.info(f"Background analysis job {session_id} completed successfully")
            store["status"] = "complete"

    except Exception as e:
        logger.error(f"Background analysis job {session_id} failed: {e}", exc_info=True)
        store["status"] = "error"
        store["error"] = str(e)


@app.post("/api/analyze/start")
async def start_analysis(body: dict, background_tasks: BackgroundTasks):
    """
    Start an analysis job. Returns a session_id to poll via SSE.
    Body: { paragraphs: [...], max_paragraphs?: int }
    """
    paragraphs: list[str] = body.get("paragraphs", [])
    max_p: int = body.get("max_paragraphs", 0)

    if not paragraphs:
        raise HTTPException(status_code=400, detail="No paragraphs provided.")

    if max_p and max_p > 0:
        paragraphs = paragraphs[:max_p]

    session_id = str(uuid.uuid4())
    logger.info(f"Created new analysis session {session_id} for {len(paragraphs)} paragraphs")
    _analysis_store[session_id] = {
        "status": "pending",
        "paragraphs": paragraphs,
        "results": [],
        "events": [],
        "total": len(paragraphs),
        "current": 0,
        "error": None,
    }
    background_tasks.add_task(run_analysis_job, session_id)
    return {"session_id": session_id, "total": len(paragraphs)}


@app.post("/api/analyze/cancel/{session_id}")
async def cancel_analysis(session_id: str):
    """Cancel a running analysis job."""
    store = _analysis_store.get(session_id)
    if store and store["status"] in ["pending", "running"]:
        store["status"] = "cancelled"
    return {"status": "ok"}


@app.get("/api/analyze/stream/{session_id}")
async def stream_analysis(session_id: str):
    """
    SSE endpoint — streams analysis events as each paragraph is processed.
    Events:
      - { type: "progress", current, total, result }
      - { type: "complete", results }
      - { type: "error", message }
      - { type: "cancelled" }
    """
    if session_id not in _analysis_store:
        raise HTTPException(status_code=404, detail="Session not found.")

    async def event_generator():
        store = _analysis_store[session_id]
        total = store["total"]
        yielded = 0

        while True:
            # Yield any new events that haven't been streamed yet
            while yielded < len(store["events"]):
                event_data = store["events"][yielded]
                yielded += 1
                yield {"data": json.dumps(event_data)}

            if store["status"] == "complete":
                yield {
                    "data": json.dumps({
                        "type": "complete",
                        "results": store["results"],
                        "total": total,
                    })
                }
                break
            elif store["status"] == "error":
                yield {"data": json.dumps({"type": "error", "message": store.get("error", "Unknown error")})}
                break
            elif store["status"] == "cancelled":
                yield {"data": json.dumps({"type": "cancelled"})}
                break

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


# ------------------------------------------------------------------ #
#  Auto-save Draft endpoint                                          #
# ------------------------------------------------------------------ #
@app.post("/api/document/save_draft")
async def save_draft(body: dict):
    """
    Save the analysis results as a draft to the database.
    Body: { results: [...], document_name: str, user_id: str, paragraphs: [...] }
    """
    raw_results: list[dict] = body.get("results", [])
    doc_name: str = body.get("document_name", "Regulatory_Analysis")
    user_id: str = body.get("user_id", "")
    paragraphs: list[str] = body.get("paragraphs", [])

    if not raw_results:
        raise HTTPException(status_code=400, detail="No results provided.")

    try:
        results = [RegulatoryParagraphAnalysis(**r) for r in raw_results]
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid result format: {e}")

    try:
        doc_id = str(uuid.uuid4())
        save_document(
            doc_id=doc_id,
            file_name=doc_name,
            circular_name=doc_name,
            paragraph_count=len(results),
            excel_blob=None,  # No Excel generation during Maker flow
            submitted_by=user_id or None,
            analysis_results=raw_results,
            paragraphs=paragraphs,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Draft saving failed: {e}")

    return {"status": "ok", "doc_id": doc_id}


# ------------------------------------------------------------------ #
#  Export endpoint                                                   #
# ------------------------------------------------------------------ #
@app.post("/api/export")
async def export_excel(body: dict):
    """
    Generate a styled Excel file from analysis results.
    Body: { results: [...], document_name?: str, authority_id?: str, effective_date?: str,
            user_id?: str, paragraphs?: [...] }
    """
    raw_results: list[dict] = body.get("results", [])
    doc_name: str = body.get("document_name", "Regulatory_Analysis")
    auth_id: str = body.get("authority_id", "")
    eff_date: str = body.get("effective_date", "")
    user_id: str = body.get("user_id", "")
    paragraphs: list[str] = body.get("paragraphs", [])
    existing_doc_id: str = body.get("doc_id", "")

    if not raw_results:
        raise HTTPException(status_code=400, detail="No results provided.")

    # Reconstruct Pydantic objects
    try:
        results = [RegulatoryParagraphAnalysis(**r) for r in raw_results]
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid result format: {e}")

    try:
        exporter = ExcelExporter()
        excel_bytes = exporter.export(
            results,
            document_name=doc_name,
            authority_id=auth_id,
            effective_date=eff_date
        )

        if existing_doc_id:
            # Update the existing draft
            update_document_excel(existing_doc_id, excel_bytes, json.dumps(raw_results))
            doc_id = existing_doc_id
        else:
            # Save to database history (fallback if not auto-saved)
            doc_id = str(uuid.uuid4())
            save_document(
                doc_id=doc_id,
                file_name=doc_name,
                circular_name=auth_id or doc_name,
                paragraph_count=len(results),
                excel_blob=excel_bytes,
                submitted_by=user_id or None,
                analysis_results_json=json.dumps(raw_results),
                paragraphs_json=json.dumps(paragraphs) if paragraphs else None,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {e}")

    safe_name = Path(doc_name).stem + "_Analysis.xlsx"
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Document-Id": doc_id,
        },
    )


# ------------------------------------------------------------------ #
#  Maker / Document Endpoints                                        #
# ------------------------------------------------------------------ #
@app.get("/api/document/{doc_id}/results")
async def get_document_results(doc_id: str):
    """Get the analysis results and paragraphs for a document."""
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {
        "id": doc["id"],
        "file_name": doc["file_name"],
        "circular_name": doc["circular_name"],
        "status": doc["status"],
        "results": json.loads(doc["analysis_results_json"]) if doc.get("analysis_results_json") else [],
        "paragraphs": json.loads(doc["paragraphs_json"]) if doc.get("paragraphs_json") else [],
    }

@app.put("/api/document/{doc_id}/paragraph/{idx}")
async def edit_paragraph_result(doc_id: str, idx: int, body: dict):
    """Maker or Checker manually edits a single paragraph result."""
    # Server-side guard: block Approve/Reject if paragraph needs regeneration
    if body.get("status") in ("Approved", "Rejected"):
        doc = get_document(doc_id)
        if doc and doc.get("analysis_results_json"):
            results = json.loads(doc["analysis_results_json"])
            if 0 <= idx < len(results) and results[idx].get("needs_regeneration"):
                raise HTTPException(
                    status_code=400,
                    detail="This paragraph was modified (merged/split). Please regenerate it before approving or rejecting."
                )
    ok = update_paragraph_result(doc_id, idx, body)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update paragraph.")
    return {"status": "ok"}

@app.delete("/api/document/{doc_id}/paragraph/{idx}")
async def api_delete_paragraph(doc_id: str, idx: int):
    """Delete a paragraph row so it won't appear in the exported Excel."""
    ok = delete_paragraph(doc_id, idx)
    if not ok:
        raise HTTPException(status_code=400, detail="Delete failed. Check paragraph index.")
    return await get_document_results(doc_id)

@app.post("/api/document/{doc_id}/paragraph/{idx}/regenerate")
async def regenerate_paragraph(doc_id: str, idx: int):
    """Regenerate analysis for a single paragraph via LLM."""
    doc = get_document(doc_id)
    if not doc or not doc.get("paragraphs_json") or not doc.get("analysis_results_json"):
        raise HTTPException(status_code=404, detail="Document or paragraphs not found.")
    
    paragraphs = json.loads(doc["paragraphs_json"])
    if not (0 <= idx < len(paragraphs)):
        raise HTTPException(status_code=400, detail="Invalid paragraph index.")
        
    paragraph_text = paragraphs[idx]
    
    # Run analysis synchronously for a single paragraph
    analyzer = RegulatoryAnalyzer()
    try:
        # Since we're in an async context, run blocking code in executor
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            analyzer.analyze_paragraph,
            paragraph_text, idx + 1, len(paragraphs)
        )
        result_dict = result.model_dump()
        
        # Determine if it's skipped
        is_skipped = (result_dict.get("para_type") == "Information Para" and result_dict.get("actionable") == "Not Applicable")
        
        # Update the database and clear needs_regeneration flag
        result_dict["needs_regeneration"] = False
        update_paragraph_result(doc_id, idx, result_dict)
        
        return {"status": "ok", "result": result_dict, "skipped": is_skipped}
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------ #
#  Paragraph Merge / Split / Reorder                                  #
# ------------------------------------------------------------------ #

@app.post("/api/document/{doc_id}/paragraphs/merge")
async def api_merge_paragraphs(doc_id: str, body: dict):
    """Merge 2+ paragraphs into one. Does NOT automatically run LLM analysis."""
    indices = body.get("indices", [])
    if len(indices) < 2:
        raise HTTPException(status_code=400, detail="At least 2 paragraph indices required.")

    result = merge_paragraphs(doc_id, indices)
    if not result:
        raise HTTPException(status_code=400, detail="Merge failed. Check paragraph indices.")

    # Return full updated results
    return await get_document_results(doc_id)


@app.post("/api/document/{doc_id}/paragraphs/split")
async def api_split_paragraph(doc_id: str, body: dict):
    """Split a paragraph into multiple parts. Does NOT automatically run LLM analysis."""
    idx = body.get("index")
    new_parts = body.get("new_parts")
    if idx is None or not new_parts:
        raise HTTPException(status_code=400, detail="index and new_parts are required.")

    parts = split_paragraph(doc_id, int(idx), new_parts)
    if not parts:
        raise HTTPException(status_code=400, detail="Split failed. Check index and parts.")

    return await get_document_results(doc_id)


@app.post("/api/document/{doc_id}/paragraphs/reorder")
async def api_reorder_paragraphs(doc_id: str, body: dict):
    """Reorder paragraphs (no LLM call needed)."""
    new_order = body.get("new_order", [])
    if not new_order:
        raise HTTPException(status_code=400, detail="new_order is required.")

    ok = reorder_paragraphs(doc_id, new_order)
    if not ok:
        raise HTTPException(status_code=400, detail="Reorder failed. Check new_order values.")

    return await get_document_results(doc_id)


@app.post("/api/maker/submit/{doc_id}")
async def maker_submit(doc_id: str, body: dict):
    """Maker submits a document for Checker review."""
    user_id = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    ok = submit_for_review(doc_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "ok", "doc_id": doc_id}


# ------------------------------------------------------------------ #
#  Checker — Queue, Approve, Reject, Re-analyze                     #
# ------------------------------------------------------------------ #
@app.get("/api/checker/pending_count")
async def checker_pending_count():
    """Return the count of unassigned documents pending review."""
    return {"count": get_unassigned_count()}

@app.get("/api/checker/queue")
async def checker_queue(user_id: str):
    """Return all documents pending review."""
    return get_checker_queue(user_id)


@app.post("/api/checker/claim/{doc_id}")
async def checker_claim(doc_id: str, body: dict):
    """Checker claims an unassigned document."""
    user_id = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    ok = claim_document(doc_id, user_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Document cannot be claimed.")
    return {"status": "claimed", "doc_id": doc_id}


@app.post("/api/checker/approve/{doc_id}")
async def checker_approve(doc_id: str, body: dict):
    """Checker approves a document, generating the Excel file."""
    user_id = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
        
    # First verify doc exists and load its results
    doc = get_document(doc_id)
    if not doc or not doc.get("analysis_results_json"):
        raise HTTPException(status_code=404, detail="Document or results not found.")
        
    raw_results = json.loads(doc["analysis_results_json"])
    
    # Check for unregenerated or invalid paragraphs before parsing
    for idx, r in enumerate(raw_results):
        if r.get("needs_regeneration"):
            raise HTTPException(
                status_code=400, 
                detail=f"Paragraph {idx + 1} was modified but not regenerated. Please click '🔄 Regen' before approving."
            )
        if not r.get("para_type"):
            raise HTTPException(
                status_code=400, 
                detail=f"Paragraph {idx + 1} is missing analysis data. Please edit it or click '🔄 Regen'."
            )
            
    try:
        results = [RegulatoryParagraphAnalysis(**r) for r in raw_results]
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid result format: {e}")

    # Generate Excel
    try:
        exporter = ExcelExporter()
        excel_bytes = exporter.export(
            results,
            document_name=doc["file_name"],
            authority_id=doc.get("circular_name", doc["file_name"])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {e}")

    # Mark as approved and update the Excel blob
    ok = approve_document(doc_id, user_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Document cannot be approved.")
        
    update_document_excel(doc_id, excel_bytes)
    
    return {"status": "approved", "doc_id": doc_id}


@app.post("/api/checker/reject/{doc_id}")
async def checker_reject(doc_id: str, body: dict):
    """Checker rejects a document with a comment."""
    user_id = body.get("user_id", "")
    comment = body.get("comment", "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    if not comment:
        raise HTTPException(status_code=400, detail="Rejection comment is required.")
    ok = reject_document(doc_id, user_id, comment)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "rejected", "doc_id": doc_id}


@app.post("/api/checker/reanalyze/{doc_id}")
async def checker_reanalyze(doc_id: str, body: dict):
    """
    Re-run analysis on stored paragraphs for a document.
    Returns a session_id for SSE streaming, and stores the doc_id for later update.
    """
    user_id = body.get("user_id", "")
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not doc.get("paragraphs_json"):
        raise HTTPException(status_code=400, detail="No stored paragraphs to re-analyze.")

    paragraphs = json.loads(doc["paragraphs_json"])

    session_id = str(uuid.uuid4())
    _analysis_store[session_id] = {
        "status": "pending",
        "paragraphs": paragraphs,
        "results": [],
        "total": len(paragraphs),
        "current": 0,
        "error": None,
        "doc_id": doc_id,  # track which document this re-analysis belongs to
    }
    return {"session_id": session_id, "total": len(paragraphs), "doc_id": doc_id}


@app.post("/api/checker/reanalyze/{doc_id}/save")
async def checker_save_reanalysis(doc_id: str, body: dict):
    """
    Save re-analyzed results back to the document.
    Body: { results: [...], authority_id?: str, effective_date?: str }
    """
    raw_results = body.get("results", [])
    auth_id = body.get("authority_id", "")
    eff_date = body.get("effective_date", "")

    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        results = [RegulatoryParagraphAnalysis(**r) for r in raw_results]
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid result format: {e}")

    exporter = ExcelExporter()
    excel_bytes = exporter.export(
        results,
        document_name=doc["file_name"],
        authority_id=auth_id,
        effective_date=eff_date,
    )

    update_document_excel(doc_id, excel_bytes, json.dumps(raw_results))
    return {"status": "ok", "doc_id": doc_id}


# ------------------------------------------------------------------ #
#  History endpoints                                                 #
# ------------------------------------------------------------------ #
@app.get("/api/history")
async def fetch_history(user_id: str = "", role: str = ""):
    """Return the history of all processed documents."""
    return get_history(user_id=user_id or None, role=role or None)

@app.get("/api/history/{doc_id}/download")
async def download_history_excel(doc_id: str):
    """Download the generated Excel file for a past document."""
    excel_blob = get_excel(doc_id)
    if not excel_blob:
        raise HTTPException(status_code=404, detail="Excel file not found.")

    return StreamingResponse(
        iter([excel_blob]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Analysis_{doc_id[:8]}.xlsx"'},
    )


# ------------------------------------------------------------------ #
#  Static file serving — must be LAST                               #
# ------------------------------------------------------------------ #
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
