# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

gradYOU8 (WashU Navigator) helps WashU undergraduates track graduation requirements, audit degree progress, and ask questions about the WashU Bulletin — all powered by a vectorless RAG pipeline (PageIndex) and the MiniMax M2.7 LLM.

## Commands

### Backend
```bash
cd backend
pip install -r requirements.txt        # first-time setup
cp .env.example .env                   # then fill in MINIMAX_API_KEY + MINIMAX_GROUP_ID
python -m uvicorn main:app --port 8000 --reload

# Health check
curl http://localhost:8000/api/health
```

### Frontend
```bash
cd frontend
npm install                            # first-time setup
npm run dev                            # dev server at http://localhost:5173
npm run build                          # compile TS + bundle → frontend/dist/
```

The Vite dev server proxies `/api` and `/chat` to `http://localhost:8001` — change the port in `frontend/vite.config.ts` if your backend runs on 8000.

In production, `npm run build` populates `frontend/dist/` and the FastAPI server serves those static files directly.

### No formal test suite
The many `test_*.py` files throughout the repo are ad-hoc development scripts, not a pytest suite. Run them individually: `python backend/test_chat.py`.

## Architecture

### Stack
- **Backend:** Python 3.11, FastAPI, Uvicorn
- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS 4, React Router 6
- **RAG:** PageIndex (vectorless, tree-based) — `backend/libs/pageindex_agent/` (git submodule)
- **LLM:** MiniMax M2.7 via `ChatGPT_API` wrapper inside the submodule
- **Data:** JSON files in `data/` (no database for most features; SQLite available via aiosqlite)

### Backend Layout
```
backend/
  main.py                    # app factory, router registration, /chat + /chat/stream endpoints
  routers/
    requirements.py          # GET /api/requirements?program=<name>
    audit.py                 # POST /api/audit (simple, hardcoded programs)
    audit_full.py            # POST /api/audit-full (RAG-powered, any program)
    upload.py                # POST /api/upload-transcript
  services/
    agentic_retriever.py     # core RAG: route → identify nodes → fetch text → answer
    requirements_extractor.py # LLM-parses raw bulletin text → structured requirement groups
    audit_engine.py          # matches student courses against requirement groups
    equivalency_resolver.py  # maps legacy course codes (CSE-E81 131) → official (CSE 131)
    tree_navigator.py        # utilities for walking PageIndex tree nodes
    tree_router.py           # LLM selects which split tree(s) to search
    program_indexer.py       # fuzzy program name lookup + caching
```

### Split Tree Catalog
The WashU Bulletin PDF is pre-processed into multiple PageIndex trees stored in `data/`:
- `bulletin_arts_sciences.tree.json`
- `bulletin_engineering.tree.json`
- `bulletin_business.tree.json`
- `bulletin_art.tree.json`, `bulletin_architecture.tree.json`
- `bulletin_university.tree.json`, `bulletin_cross_school.tree.json`

At query time, `tree_router.py` uses MiniMax to select 1–4 relevant trees, then `agentic_retriever.py` searches those trees for matching nodes (no embeddings — purely LLM-driven node selection).

### Key Data Flows

**Transcript Upload → Profile:**
1. `POST /api/upload-transcript` saves the PDF, shells out to `transcript_to_json.py`
2. That script calls MiniMax to parse the PDF → writes `data/student_profile.json`
3. Backend normalizes the profile and stores it in `app.state.current_profile`
4. Background thread pre-warms requirements cache for the student's programs

**Audit (`POST /api/audit-full`):**
1. For each program, `requirements_extractor.get_requirements()` calls `agentic_retrieve()` to gather evidence, then MiniMax parses it into structured requirement groups (result is in-memory cached)
2. `audit_engine.audit_group()` matches each student course against requirements, resolving legacy codes via `equivalency_resolver`
3. Returns per-program + college-level results with SATISFIED / PARTIAL / MISSING status per group

**Chat (`POST /chat/stream`):**
1. `agentic_retrieve()`: LLM routes to relevant split trees → LLM identifies node IDs → text extracted (24 KB budget) → MiniMax generates answer
2. Server-Sent Events stream `status`, `answer_delta`, `sources`, `done` events to the frontend
3. Frontend (`ChatSidebar.tsx`, `Chat.tsx`) renders answer incrementally

### Frontend Layout
```
frontend/src/
  App.tsx                    # root router (Profile is the main page)
  pages/
    Profile.tsx              # student dashboard: header + timeline/audit toggle + chat sidebar
    Chat.tsx                 # standalone RAG Q&A page
    Courses.tsx              # course catalog with search/filter
  components/
    TranscriptUpload.tsx     # drag-and-drop PDF upload
    AuditDashboard.tsx       # per-program audit results with progress bars
    TimelineView.tsx         # horizontal scrolling semester timeline
    ChatSidebar.tsx          # resizable right-side chat with SSE streaming
    RequirementGroup.tsx     # single requirement group card (satisfied/missing lists)
    ProgressBar.tsx          # animated fill bar
    NavBar.tsx               # top nav
```

Student profile is persisted to `localStorage` under key `gradYOU8_profile`.

## Environment Variables

```bash
# Required for all LLM calls
MINIMAX_API_KEY=
MINIMAX_GROUP_ID=
MINIMAX_MODEL=MiniMax-M2.7      # default

# Paths (relative to backend/)
DATA_DIR=../data
BULLETIN_PDF=../data/bulletin_full.pdf
```

## Known Issues

- `backend/routers/upload.py` has a hard-coded absolute Windows Python path (`C:\Users\Ethan\...`). Should be `sys.executable` for portability.
- `audit_engine.py` has only two hardcoded programs (`biology-ba`, `cs-minor-engineering`). Full audit goes through `audit_full.py` which uses the RAG pipeline for any program.
- Requirements cache (`_cache` dict in `requirements_extractor.py`) is unbounded in-memory — fine for single-session use.
