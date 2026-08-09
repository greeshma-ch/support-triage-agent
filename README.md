# Multi-Domain Support Triage Agent

An AI-powered support triage agent that automatically classifies and routes customer support tickets using RAG (Retrieval-Augmented Generation).

## Results
- 29 tickets processed in ~5 minutes
- 16 replied (grounded answers from documentation)
- 13 escalated (high-risk or unanswerable cases)
- 0 hallucinated policies
- Model: Gemini 2.5 Flash, temperature=0

## Architecture

```
classifier.py → retriever.py → agent.py → main.py
```

| Module | Purpose |
|---|---|
| classifier.py | Pre-LLM safety check: keyword escalation, company inference, request type classification |
| retriever.py | ChromaDB RAG: chunks docs, embeds with sentence-transformers, filters by domain |
| agent.py | Gemini 2.5 Flash call, JSON parsing, safe fallback on failure |
| main.py | Pipeline orchestrator, reads input, writes output CSV, crash-safe |

## Setup

1. Install dependencies:
   ```
   pip install -r code/requirements.txt
   ```

2. Add your Gemini API key to `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```

3. Place your support documentation in:
   ```
   data/<company_name>/ as .md files
   ```

4. Run:
   ```
   python code/main.py
   ```

5. Output:
   ```
   support_tickets/output.csv
   ```

## Output Format
Each ticket produces:
- **status**: "replied" or "escalated"
- **product_area**: support domain category
- **response**: user-facing answer grounded in documentation only
- **request_type**: "product_issue", "feature_request", "bug", or "invalid"
- **justification**: internal routing explanation

## Key Features
- Corpus-only grounding — never uses outside knowledge
- Two-layer escalation: keyword pre-filter + LLM safety check
- Deterministic: temperature=0 on all LLM calls
- Crash-safe: writes each result immediately after processing
- Company inference: detects domain when not specified

## Tech Stack
Python, ChromaDB, sentence-transformers, Google Gemini 2.5 Flash, pandas, tqdm, python-dotenv

## Future Enhancements
- FastAPI + React web interface for real-time triage
- Generic corpus support — upload any documentation
- Confidence scoring: auto-escalate on weak retrieval
- Feedback loop for continuous accuracy improvement
- Analytics dashboard for ticket trends and escalation rates