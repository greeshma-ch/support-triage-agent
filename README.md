# Multi-Domain Support Triage Agent — Deployed Edition

A RAG-based support ticket triage agent (originally built for HackerRank
Orchestrate 2026, top 2% / 284 of 12,885) rebuilt as a deployed, multi-tenant
web app.

**Pipeline:** classifier (safety keywords + company inference) → retriever
(ChromaDB + sentence-transformers, with a confidence score) → agent (Gemini
2.5 Flash) → validation.

## What's new in this pass

- **FastAPI backend** (`backend/`) wrapping the original CLI pipeline as a
  REST API, deployable to Render.
- **Confidence scoring** — every retrieval returns a 0–1 "grounding signal"
  derived from ChromaDB's cosine distance. Tickets with weak retrieval
  matches (default threshold `0.35`) are auto-escalated even if the LLM
  wanted to answer, so the agent never confidently improvises without
  grounding. Tune `CONFIDENCE_ESCALATION_THRESHOLD` in
  `backend/app/pipeline.py`.
- **Generic multi-tenant corpus upload** — the old hardcoded
  hackerrank/claude/visa folders are gone. Any company/corpus can be
  uploaded at runtime via the API or the UI (`.md`/`.txt` files), and the
  classifier's company inference works against whatever is currently
  indexed instead of a fixed keyword list.
- **React console UI** (`frontend/`), deployable to Vercel: submit a ticket,
  see the status/confidence/response/retrieved sources, and manage corpora.

Still open from the original README's future-enhancements list (deliberately
out of scope for this pass): the feedback loop for continuous accuracy
improvement, and the analytics dashboard for ticket trends. The API is
structured so both can be added later without touching the core pipeline.

## Repo layout

```
backend/
  app/
    main.py         # FastAPI routes
    pipeline.py      # classifier -> retriever -> agent orchestration
    retriever.py     # ChromaDB + confidence scoring, generic corpus
    classifier.py    # escalation keywords, company inference, request typing
    agent.py         # Gemini call
    seed_data/       # the original hackerrank/claude/visa example corpora
  requirements.txt
  .env.example
frontend/
  src/               # React (Vite) console
  vercel.json
  .env.example
render.yaml           # Render deploy config for the backend
```

## Local development

**Backend**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # add your GEMINI_API_KEY
uvicorn app.main:app --reload
```
First boot seeds the bundled HackerRank/Claude/Visa example corpora into
ChromaDB automatically. API docs at `http://localhost:8000/docs`.

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm run dev
```

## Deploying

**Backend → Render**
1. Push this repo to GitHub.
2. In Render: New → Blueprint → point at the repo (it will read `render.yaml`).
3. Set the `GEMINI_API_KEY` secret in the Render dashboard.
4. Note: Render's free plan has an ephemeral filesystem, so uploaded corpora
   (and the ChromaDB index) reset on every restart/redeploy — the bundled
   example corpora will always re-seed, but anything uploaded at runtime
   won't persist. Add a paid persistent disk mounted at
   `backend/app/storage` if you need uploads to survive restarts.

**Frontend → Vercel**
1. In Vercel: New Project → import the repo → set root directory to `frontend`.
2. Add environment variable `VITE_API_URL` = your Render backend URL.
3. Deploy. Vercel auto-detects the Vite framework from `vercel.json`.
4. Back on Render, set `ALLOWED_ORIGINS` to your Vercel URL (instead of `*`)
   once you have it, so CORS is locked down.

## API reference

| Method | Path                      | Purpose                          |
|--------|---------------------------|-----------------------------------|
| GET    | `/api/health`              | liveness check                    |
| GET    | `/api/companies`           | list indexed corpora + chunk counts |
| POST   | `/api/companies/upload`    | multipart: `company` + `files[]` (.md/.txt) |
| DELETE | `/api/companies/{name}`    | remove a corpus                   |
| POST   | `/api/triage`               | `{issue, subject, company}` → full triage result |
| POST   | `/api/triage/batch`         | upload a tickets CSV, get results CSV back |
