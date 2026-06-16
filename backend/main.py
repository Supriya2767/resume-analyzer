# main.py - FastAPI Application Entry Point
#
# FastAPI is a modern Python web framework.
# It automatically creates interactive API docs at http://localhost:8000/docs
# It validates request/response data using Python type hints + Pydantic.

import os
import shutil
import logging
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from parser import extract_text_from_pdf, parse_resume
from ats import calculate_ats_score
from jd_match import match_job_description
from database import save_analysis, get_all_analyses

# ── Logging (configure once here; all modules inherit it) ─────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("main")

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Resume Analyzer API",
    description="Upload resumes, get ATS scores, match job descriptions.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 5 MB upload size limit
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


# ── Request Models ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    resume_text: str
    filename: str


class JDMatchRequest(BaseModel):
    resume_text: str
    job_description: str


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "Resume Analyzer API is running", "version": "2.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a PDF resume.
    1. Validate content-type and file extension.
    2. Guard against oversized uploads.
    3. Save with a uuid prefix to avoid filename collisions.
    4. Extract text with pdfplumber.
    5. Parse with NLP.
    6. Return structured data.
    """
    # Validate extension
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Read into memory to check size before writing to disk
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    # Save with a unique prefix to prevent overwriting previous uploads
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(save_path, "wb") as f:
        f.write(content)
    log.info("Saved upload: %s (%d bytes)", save_path, len(content))

    # Extract text
    raw_text = extract_text_from_pdf(save_path)
    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract text from this PDF. "
                "The file may be image-based (scanned). "
                "Please use a text-based PDF."
            ),
        )

    # Parse
    parsed = parse_resume(raw_text)
    log.info("Parsed resume for: %s", parsed.get("name", "Unknown"))

    return {
        "success":     True,
        "filename":    file.filename,
        "raw_text":    raw_text,
        "parsed_data": parsed,
    }


@app.post("/analyze-resume")
async def analyze_resume(req: AnalyzeRequest):
    """Calculate ATS score for the provided resume text."""
    if not req.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text cannot be empty.")

    ats = calculate_ats_score(req.resume_text)
    log.info("ATS score for '%s': %.1f", req.filename, ats["ats_score"])

    save_analysis(
        filename=req.filename,
        ats_score=ats["ats_score"],
        match_percentage=0,
    )

    return {"success": True, "ats_result": ats}


@app.post("/match-job-description")
async def match_jd(req: JDMatchRequest):
    """Compare resume text against a job description."""
    if not req.resume_text.strip():
        raise HTTPException(status_code=400, detail="resume_text cannot be empty.")
    if not req.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description cannot be empty.")

    result = match_job_description(
        resume_text=req.resume_text,
        job_description=req.job_description,
    )
    log.info("JD match result: %.1f%%", result["match_percentage"])

    return {"success": True, "match_result": result}


@app.get("/history")
async def get_history():
    """Return all past analyses from SQLite."""
    return {"analyses": get_all_analyses()}