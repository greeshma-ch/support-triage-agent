"""
Main entry point for the support triage agent.

Reads support_tickets/support_tickets.csv, processes each ticket through
the classifier → retriever → agent pipeline, and writes results to
support_tickets/output.csv.

Usage:
    python code/main.py
"""

import os
import sys
import csv
import time
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

# Ensure code/ is importable
sys.path.insert(0, os.path.dirname(__file__))

from retriever import build_index, query as retriever_query
from classifier import (
    escalate_immediately,
    infer_company,
    classify_request_type,
    validate_status,
    validate_request_type,
)
from agent import process_ticket

# ─── Paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent          # code/
REPO_ROOT = _HERE.parent               # repo root
INPUT_CSV  = REPO_ROOT / "support_tickets" / "support_tickets.csv"
OUTPUT_CSV = REPO_ROOT / "support_tickets" / "output.csv"

# Load env vars — path is relative to this file, CWD-independent
load_dotenv(_HERE.parent / ".env")

# Output CSV columns — must match exactly
OUTPUT_COLUMNS = [
    "issue", "subject", "company",
    "response", "product_area", "status",
    "request_type", "justification",
]


def load_input_tickets() -> pd.DataFrame:
    """Load support tickets from CSV."""
    df = pd.read_csv(INPUT_CSV)
    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    # Fill NaN with empty strings
    df = df.fillna("")
    return df


def init_output_csv():
    """Create/reset the output CSV with headers."""
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()


def append_row(row_dict: dict):
    """Append a single row to output.csv immediately."""
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writerow(row_dict)


def process_single_ticket(idx: int, row: pd.Series) -> dict:
    """
    Process a single ticket through the full pipeline:
    classifier -> retriever -> agent -> validation.
    """
    issue = str(row.get("issue", "")).strip()
    subject = str(row.get("subject", "")).strip()
    company = str(row.get("company", "")).strip()

    # ── Step 1: Check for immediate escalation ───────────────────────────
    if escalate_immediately(issue):
        # Determine company even for escalated tickets
        if not company or company.lower() in ("none", ""):
            company = infer_company(issue, subject)

        # Still retrieve docs for context in the escalation response
        docs = retriever_query(issue, company)
        result = process_ticket(issue, subject, company, docs)

        # Force escalation status
        result["status"] = "escalated"

        return {
            "issue": issue,
            "subject": subject,
            "company": company,
            "response": " Escalate to a human",
            "product_area": result.get("product_area", "general_support"),
            "status": "escalated",
            "request_type": validate_request_type(result.get("request_type", "product_issue")),
            "justification": result.get("justification", "Escalated: high-risk keywords detected."),
        }

    # ── Step 2: Infer company if missing ─────────────────────────────────
    if not company or company.lower() in ("none", ""):
        company = infer_company(issue, subject)

    # ── Step 3: Retrieve relevant documentation ──────────────────────────
    docs = retriever_query(issue, company)

    # ── Step 4: Process through LLM agent ────────────────────────────────
    result = process_ticket(issue, subject, company, docs)

    # ── Step 5: Validate and fix output fields ───────────────────────────
    status = validate_status(result.get("status", "escalated"))
    request_type = validate_request_type(result.get("request_type", "product_issue"))

    # Cross-check: classifier may override request_type
    classifier_type = classify_request_type(issue, result.get("response", ""))
    # Use classifier's "invalid" or "bug" if it detects them -- they're safety-critical
    if classifier_type in ("invalid", "bug") and request_type == "product_issue":
        request_type = classifier_type

    return {
        "issue": issue,
        "subject": subject,
        "company": company,
        "response": result.get("response", " Escalate to a human"),
        "product_area": result.get("product_area", "general_support"),
        "status": status,
        "request_type": request_type,
        "justification": result.get("justification", "Processed by automated triage."),
    }


def _worker(idx: int, row_dict: dict) -> tuple[int, dict]:
    """Thread worker: process one ticket and return (index, result)."""
    # Convert dict back to Series for process_single_ticket
    row = pd.Series(row_dict)
    result = process_single_ticket(idx, row)
    return idx, result


def main():
    """Main entry point -- orchestrate the full triage pipeline."""
    print("=" * 60)
    print("  SUPPORT TICKET TRIAGE AGENT")
    print("=" * 60)
    print()

    # ── Step 1: Build/verify the vector index ────────────────────────────
    print("[1/4] Initializing RAG retriever...")
    build_index()
    print()

    # ── Step 2: Load input tickets ───────────────────────────────────────
    print("[2/4] Loading support tickets...")
    df = load_input_tickets()
    total = len(df)
    print(f"  Found {total} tickets in {INPUT_CSV}")
    print()

    # ── Step 3: Init output CSV ──────────────────────────────────────────
    init_output_csv()
    print()

    # ── Step 4: Process tickets sequentially ─────────────────────────────
    print("[3/4] Processing tickets...")
    stats = {"replied": 0, "escalated": 0}
    type_stats = {"product_issue": 0, "feature_request": 0, "bug": 0, "invalid": 0}

    for idx in tqdm(range(total), desc="Tickets", unit="ticket"):
        row = df.iloc[idx]
        try:
            result = process_single_ticket(idx, row)
        except Exception as e:
            result = {
                "issue": str(row.get("issue", "")),
                "subject": str(row.get("subject", "")),
                "company": str(row.get("company", "")),
                "response": " Escalate to a human",
                "product_area": "general_support",
                "status": "escalated",
                "request_type": "product_issue",
                "justification": f"Worker error: {str(e)[:100]}",
            }

        append_row(result)

        # Track stats
        stats[result["status"]] = stats.get(result["status"], 0) + 1
        type_stats[result["request_type"]] = type_stats.get(result["request_type"], 0) + 1

        # Progress print
        tqdm.write(
            f"  #{idx + 1:3d} | {result['status']:>9s} | "
            f"{result['product_area']:<25s} | {result['request_type']:<15s} | "
            f"{result.get('subject', '')[:40]}"
        )

    print()

    # ── Step 5: Print summary ────────────────────────────────────────────
    print("[4/4] Triage complete!")
    print("=" * 60)
    print(f"  Total tickets processed: {total}")
    print(f"  Replied:    {stats.get('replied', 0)}")
    print(f"  Escalated:  {stats.get('escalated', 0)}")
    print()
    print("  Request Type Breakdown:")
    for rtype, count in sorted(type_stats.items()):
        print(f"    {rtype:<20s}: {count}")
    print()
    print(f"  Output saved to: {OUTPUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
