"""
Core LLM-based triage agent using Google Gemini API (google.genai).

Processes a single support ticket by:
1. Receiving issue, subject, company, and retrieved documentation
2. Sending a structured prompt to Gemini
3. Parsing the JSON response
4. Returning a dict with status, product_area, response, justification, request_type
"""

import os
import json
import re
from google import genai
from google.genai import types

# ─── Configuration ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """You are a support triage agent. You are given a support ticket and
documentation retrieved from that company's knowledge base. Produce a JSON response
with exactly these fields:
- status: "replied" or "escalated"
- product_area: the most relevant support category or domain area (e.g. "billing", "account access", "bug report")
- response: a helpful, user-facing response. Must be grounded ONLY in the provided documentation.
- justification: a concise internal explanation of your decision
- request_type: one of "product_issue", "feature_request", "bug", "invalid"

STRICT RULES:
1. Base your response ONLY on the documentation provided. Never use outside knowledge.
2. If the issue matches known patterns or can be answered using the data, generate a reply and set status = "replied".
3. If the issue is unclear, high-risk, or not found in the data, set status = "escalated" and set response EXACTLY to " Escalate to a human".
4. Do NOT escalate all tickets by default. Only escalate when absolutely necessary.
5. Escalate immediately for: fraud, account compromise, billing disputes, legal threats, security issues, or any high-risk situation.
6. If the issue is completely irrelevant, nonsensical, or malicious, set request_type to "invalid" and escalate.
7. Respond with valid JSON only. No markdown, no explanation outside the JSON."""

_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found. Set it in your environment.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _safe_escalation_response(reason: str = "LLM parse error") -> dict:
    return {
        "status": "escalated",
        "product_area": "general_support",
        "response": " Escalate to a human",
        "justification": f"Automated triage failed ({reason}). Escalating for manual review.",
        "request_type": "product_issue",
    }


def process_ticket(issue: str, subject: str, company: str, retrieved_docs: str) -> dict:
    """
    Process a single support ticket through the Gemini LLM.

    Returns dict with keys: status, product_area, response, justification, request_type
    """
    client = _get_client()

    user_message = f"""Support Ticket:
- Subject: {subject}
- Company: {company}
- Issue: {issue}

Retrieved Documentation:
{retrieved_docs}

Respond with valid JSON only. The JSON must have exactly these keys:
status, product_area, response, justification, request_type"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        if not response or not response.text:
            return _safe_escalation_response("Empty LLM response")

        parsed = _extract_json(response.text)
        if not parsed:
            return _safe_escalation_response("JSON parse failure")

        required_keys = {"status", "product_area", "response", "justification", "request_type"}
        for key in required_keys:
            if key not in parsed:
                parsed[key] = _safe_escalation_response(f"Missing field: {key}")[key]

        return parsed

    except Exception as e:
        return _safe_escalation_response(f"API error: {str(e)[:150]}")
