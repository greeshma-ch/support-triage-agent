"""
Safety & domain classifier for support ticket triage.

Runs BEFORE the LLM call to:
1. Detect high-risk tickets that need immediate escalation.
2. Infer the company from the currently indexed corpora if not provided.
3. Classify the request type from issue text + LLM response.
"""

import re

# ─── Escalation Keywords ─────────────────────────────────────────────────────
ESCALATION_KEYWORDS = [
    "fraud", "unauthorized", "chargeback", "dispute", "hacked", "stolen",
    "legal", "lawsuit", "police", "threat", "minor", "death", "suicide",
    "account compromised", "identity theft", "refund not received",
    "security vulnerability", "vulnerability",
]

# Valid request types
VALID_REQUEST_TYPES = {"product_issue", "feature_request", "bug", "invalid"}
VALID_STATUSES = {"replied", "escalated"}


def escalate_immediately(issue_text: str) -> bool:
    """Check if the ticket should be escalated immediately (high-risk keywords)."""
    text_lower = issue_text.lower()
    return any(keyword in text_lower for keyword in ESCALATION_KEYWORDS)


def infer_company(issue_text: str, subject: str = "", known_companies: list[str] | None = None) -> str:
    """
    Infer which indexed corpus a ticket belongs to.

    known_companies: display names (or slugs) of companies currently indexed
    in the corpus. We do a simple substring match against the ticket text.
    Falls back to "unknown" if nothing matches (the retriever will then
    search across every corpus).
    """
    combined = (issue_text + " " + subject).lower()

    if known_companies:
        for name in known_companies:
            # Company names are stored as slugs (e.g. "acme-corp"), but the
            # ticket text will usually say "Acme Corp" or "acme corp" -- so
            # match against both the raw slug and its de-hyphenated form.
            candidates = {name.lower(), name.lower().replace("-", " ")}
            if any(c in combined for c in candidates):
                return name

    return "unknown"


def classify_request_type(issue_text: str, response_from_llm: str = "") -> str:
    """
    Classify the request type based on issue text and optionally
    the LLM response content.

    Returns one of: 'product_issue', 'feature_request', 'bug', 'invalid'
    """
    text_lower = issue_text.lower()
    response_lower = response_from_llm.lower() if response_from_llm else ""

    invalid_patterns = [
        r"iron man", r"what is the name of", r"who is the",
        r"delete all files", r"\bhack\b(?!errank)", r"\bcrack\b",
        r"out of scope", r"irrelevant",
    ]
    for pattern in invalid_patterns:
        if re.search(pattern, text_lower):
            return "invalid"

    if "invalid" in response_lower and "request_type" in response_lower:
        return "invalid"

    feature_patterns = [
        r"feature request", r"would be nice", r"can you add",
        r"suggestion", r"i wish", r"it would be great",
        r"please add", r"i'd like to see", r"new feature",
        r"can we have", r"enhancement",
    ]
    for pattern in feature_patterns:
        if re.search(pattern, text_lower):
            return "feature_request"

    bug_patterns = [
        r"bug", r"broken", r"not working", r"doesn't work",
        r"doesn.t work", r"error", r"crash", r"down",
        r"failing", r"fail", r"can.?not", r"unable to",
        r"issue while", r"blocker", r"blocked",
    ]
    for pattern in bug_patterns:
        if re.search(pattern, text_lower):
            return "bug"

    return "product_issue"


def validate_status(status: str) -> str:
    """Ensure status is one of the allowed values."""
    if status and status.lower().strip() in VALID_STATUSES:
        return status.lower().strip()
    return "escalated"


def validate_request_type(request_type: str) -> str:
    """Ensure request_type is one of the allowed values."""
    if request_type and request_type.lower().strip() in VALID_REQUEST_TYPES:
        return request_type.lower().strip()
    return "product_issue"
