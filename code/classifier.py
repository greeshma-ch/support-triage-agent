"""
Safety & domain classifier for support ticket triage.

Runs BEFORE the LLM call to:
1. Detect high-risk tickets that need immediate escalation.
2. Infer the company if not provided.
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

# ─── Company Inference Keywords ──────────────────────────────────────────────
HACKERRANK_KEYWORDS = [
    "hackerrank", "hacker rank", "assessment", "test", "interview",
    "candidate", "coding challenge", "screen", "proctoring",
    "skillup", "library", "plagiarism", "recruiter", "hiring",
    "certificate", "mock interview", "resume builder",
]

CLAUDE_KEYWORDS = [
    "claude", "anthropic", "api", "conversation", "prompt",
    "bedrock", "sonnet", "haiku", "opus", "artifact",
    "workspace", "team plan", "pro plan", "max plan",
    "lti", "claude code", "claude desktop",
]

VISA_KEYWORDS = [
    "visa", "card", "transaction", "payment", "merchant",
    "credit card", "debit card", "charge", "atm",
    "chargeback", "travel", "traveller", "cheque",
    "cardholder", "mastercard",
]

# Valid request types
VALID_REQUEST_TYPES = {"product_issue", "feature_request", "bug", "invalid"}
VALID_STATUSES = {"replied", "escalated"}


def escalate_immediately(issue_text: str) -> bool:
    """
    Check if the ticket should be escalated immediately based on
    high-risk keyword matching.
    """
    text_lower = issue_text.lower()
    for keyword in ESCALATION_KEYWORDS:
        if keyword in text_lower:
            return True
    return False


def infer_company(issue_text: str, subject: str = "") -> str:
    """
    If company is 'None' or missing, infer the company from the issue text
    and subject using keyword matching.
    Returns: 'HackerRank', 'Claude', 'Visa', or 'unknown'
    """
    combined = (issue_text + " " + subject).lower()

    scores = {
        "HackerRank": 0,
        "Claude": 0,
        "Visa": 0,
    }

    for kw in HACKERRANK_KEYWORDS:
        if kw in combined:
            scores["HackerRank"] += 1

    for kw in CLAUDE_KEYWORDS:
        if kw in combined:
            scores["Claude"] += 1

    for kw in VISA_KEYWORDS:
        if kw in combined:
            scores["Visa"] += 1

    max_score = max(scores.values())
    if max_score == 0:
        return "unknown"

    # Return the company with the highest score
    return max(scores, key=scores.get)


def classify_request_type(issue_text: str, response_from_llm: str = "") -> str:
    """
    Classify the request type based on issue text and optionally
    the LLM response content.

    Returns one of: 'product_issue', 'feature_request', 'bug', 'invalid'
    """
    text_lower = issue_text.lower()
    response_lower = response_from_llm.lower() if response_from_llm else ""

    # ── Invalid detection ────────────────────────────────────────────────
    invalid_patterns = [
        r"iron man", r"what is the name of", r"who is the",
        r"delete all files", r"\bhack\b(?!errank)", r"\bcrack\b",
        r"out of scope", r"irrelevant",
    ]
    for pattern in invalid_patterns:
        if re.search(pattern, text_lower):
            return "invalid"

    # Check if LLM flagged it as invalid
    if "invalid" in response_lower and "request_type" in response_lower:
        return "invalid"

    # ── Feature request detection ────────────────────────────────────────
    feature_patterns = [
        r"feature request", r"would be nice", r"can you add",
        r"suggestion", r"i wish", r"it would be great",
        r"please add", r"i'd like to see", r"new feature",
        r"can we have", r"enhancement",
    ]
    for pattern in feature_patterns:
        if re.search(pattern, text_lower):
            return "feature_request"

    # ── Bug detection ────────────────────────────────────────────────────
    bug_patterns = [
        r"bug", r"broken", r"not working", r"doesn't work",
        r"doesn.t work", r"error", r"crash", r"down",
        r"failing", r"fail", r"can.?not", r"unable to",
        r"issue while", r"blocker", r"blocked",
        r"submissions.*(not|aren.t).*working",
    ]
    for pattern in bug_patterns:
        if re.search(pattern, text_lower):
            return "bug"

    # ── Default: product issue ───────────────────────────────────────────
    return "product_issue"


def validate_status(status: str) -> str:
    """Ensure status is one of the allowed values."""
    if status and status.lower().strip() in VALID_STATUSES:
        return status.lower().strip()
    return "escalated"  # safe default


def validate_request_type(request_type: str) -> str:
    """Ensure request_type is one of the allowed values."""
    if request_type and request_type.lower().strip() in VALID_REQUEST_TYPES:
        return request_type.lower().strip()
    return "product_issue"  # safe default


# ─── CLI Test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        ("My identity has been stolen, what should I do", "Identity Theft", "Visa"),
        ("site is down & none of the pages are accessible", "", "None"),
        ("What is the name of the actor in Iron Man?", "Urgent, please help", "None"),
        ("How do I add extra time for a candidate on HackerRank?", "Extra time", "None"),
        ("Claude has stopped working completely", "Claude not responding", "None"),
        ("I want Claude to stop crawling my website", "Website Data crawl", "Claude"),
        ("Give me the code to delete all files from the system", "Delete files", "None"),
    ]

    for issue, subject, company in test_cases:
        esc = escalate_immediately(issue)
        inferred = infer_company(issue, subject) if company == "None" else company
        req_type = classify_request_type(issue)
        print(f"Issue: {issue[:60]}...")
        print(f"  Escalate: {esc}  |  Company: {inferred}  |  Type: {req_type}")
        print()
