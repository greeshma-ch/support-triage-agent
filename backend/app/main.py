"""
FastAPI backend for the Multi-Domain Support Triage Agent.

Endpoints:
  GET  /api/health              - liveness check
  GET  /api/companies           - list indexed corpora
  POST /api/companies/upload    - upload .md files for a company (multipart)
  DELETE /api/companies/{name}  - remove a company's corpus
  POST /api/triage              - triage a single ticket
  POST /api/triage/batch        - triage a CSV of tickets, return CSV
"""

import io
import csv
import os

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import retriever
from .pipeline import process_ticket

app = FastAPI(title="Support Triage Agent API", version="1.0.0")

# Allow the deployed frontend (Vercel) + local dev to call this API.
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in allowed_origins.split(",")] if allowed_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    # Seed the bundled example corpora (hackerrank/claude/visa) on first boot.
    retriever.seed_from_disk()

class TriageRequest(BaseModel):
    issue: str
    subject: str = ""
    company: str = ""


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/companies")
def get_companies():
    return {"companies": retriever.list_companies()}


@app.post("/api/companies/upload")
async def upload_company(company: str = Form(...), files: list[UploadFile] = File(...)):
    if not company.strip():
        raise HTTPException(400, "Company name is required.")

    docs = []
    for f in files:
        if not f.filename.lower().endswith((".md", ".txt")):
            continue
        content = (await f.read()).decode("utf-8", errors="ignore")
        docs.append((f.filename, content))

    if not docs:
        raise HTTPException(400, "No valid .md/.txt files were uploaded.")

    chunk_count = retriever.add_documents(company, docs)
    return {
        "company": retriever.slugify(company),
        "files_indexed": len(docs),
        "chunks_indexed": chunk_count,
    }


@app.delete("/api/companies/{name}")
def delete_company(name: str):
    deleted = retriever.delete_company(name)
    if deleted == 0:
        raise HTTPException(404, f"No corpus found for '{name}'.")
    return {"company": retriever.slugify(name), "chunks_deleted": deleted}


@app.post("/api/triage")
def triage(req: TriageRequest):
    if not req.issue.strip():
        raise HTTPException(400, "Issue text is required.")
    try:
        return process_ticket(req.issue, req.subject, req.company)
    except ValueError as e:
        # Typically a missing GEMINI_API_KEY
        raise HTTPException(500, str(e))


@app.post("/api/triage/batch")
async def triage_batch(file: UploadFile = File(...)):
    """Accepts a CSV with columns issue,subject,company and returns a results CSV."""
    raw = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    reader.fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

    rows = []
    for row in reader:
        result = process_ticket(
            row.get("issue", ""), row.get("subject", ""), row.get("company", "")
        )
        rows.append(result)

    output = io.StringIO()
    fieldnames = [
        "issue", "subject", "company", "response", "product_area",
        "status", "request_type", "justification", "confidence", "escalation_reason",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=triage_results.csv"},
    )
