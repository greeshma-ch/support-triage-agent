"""
The triage pipeline: classifier -> retriever (with confidence) -> agent -> validation.
Shared by the FastAPI routes so there's a single source of truth for the logic.
"""

from . import retriever
from . import classifier
from . import agent

# Below this retrieval-confidence threshold we don't trust the grounding
# enough to let the LLM answer, even if it wanted to reply. Tune per corpus.
CONFIDENCE_ESCALATION_THRESHOLD = 0.35


def process_ticket(issue: str, subject: str = "", company: str = "") -> dict:
    """
    Run one ticket through the full pipeline.

    Returns a dict with: issue, subject, company, response, product_area,
    status, request_type, justification, confidence, escalation_reason,
    retrieved_sources.
    """
    issue = (issue or "").strip()
    subject = (subject or "").strip()
    company = (company or "").strip()

    known = [c["name"] for c in retriever.list_companies()]

    # ── Step 1: immediate keyword-based escalation ───────────────────────
    keyword_escalation = classifier.escalate_immediately(issue)

    if not company or company.lower() in ("none", "unknown", ""):
        company = classifier.infer_company(issue, subject, known)

    # ── Step 2: retrieve docs + confidence ────────────────────────────────
    retrieval = retriever.query_with_scores(issue, company)
    confidence = retrieval["confidence"]
    low_confidence = confidence < CONFIDENCE_ESCALATION_THRESHOLD

    # ── Step 3: LLM call (always run so we get product_area/justification,
    #     even if we're going to override with an escalation) ─────────────
    result = agent.process_ticket(issue, subject, company, retrieval["context"])

    status = classifier.validate_status(result.get("status", "escalated"))
    request_type = classifier.validate_request_type(result.get("request_type", "product_issue"))

    classifier_type = classifier.classify_request_type(issue, result.get("response", ""))
    if classifier_type in ("invalid", "bug") and request_type == "product_issue":
        request_type = classifier_type

    escalation_reason = None
    if keyword_escalation:
        status = "escalated"
        escalation_reason = "High-risk keyword detected (fraud, security, legal, etc.)"
    elif low_confidence:
        status = "escalated"
        escalation_reason = f"Low retrieval confidence ({confidence:.2f} < {CONFIDENCE_ESCALATION_THRESHOLD})"

    response_text = result.get("response", " Escalate to a human")
    if status == "escalated" and escalation_reason:
        response_text = " Escalate to a human"

    return {
        "issue": issue,
        "subject": subject,
        "company": company,
        "response": response_text,
        "product_area": result.get("product_area", "general_support"),
        "status": status,
        "request_type": request_type,
        "justification": result.get("justification", "Processed by automated triage."),
        "confidence": confidence,
        "escalation_reason": escalation_reason,
        "retrieved_sources": retrieval["matches"],
    }
