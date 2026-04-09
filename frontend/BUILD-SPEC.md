# gradYOU8 Frontend — Build Specification

## Overview

**What it does:** A graduation tracking app for WashU undergrads — RAG chat for requirement questions, manual course entry for audit, course catalog browsing.

**Product name:** Path (stylized as "path")
**Slug:** `washu-navigator` / `gradYOU8`
**Frontend:** React 18 + Vite + TypeScript + Tailwind CSS (already scaffolded)

---

## Pages

### 1. Home (`/`) — Landing
- Hero: "Stop guessing. Know your requirements."
- 3 quick-action cards: "Ask a Question", "Browse Courses", "Run My Audit"
- Simple semester progress widget (if courses entered)
- Nav bar with links to all pages + "path" branding top-left

### 2. Chat (`/ask`) — RAG Question Answering
- Full-page chat interface
- 5 example question chips at top (already exists, refine)
- Message bubbles: user (right, indigo), assistant (left, slate)
- Assistant messages show: answer text + collapsible "Sources" section
  - Each source: document title, page range, excerpt text
- Input bar fixed to bottom with "Ask" button
- Loading state: "Thinking..." with pulse animation
- Streaming response if supported by backend

**API:** `POST /api/chat` → `{ question, chat_history }` → `{ answer, sources: [...] }`

### 3. Audit (`/audit`) — Graduation Audit
- Program selector: major + minor + school (dropdowns)
- Two-column layout: left = "Your Courses", right = "Requirements"
- Course entry: text input → "Add" button, list of added courses with ✕ remove
- "Run Audit" button → POST to backend → show results
- Results: green "Satisfied" list + amber "Missing" list
  - Each satisfied item: course code that satisfied it
  - Each missing item: requirement description + suggested courses to fill it

**API:** 
- `GET /api/requirements?program=biology-ba` → requirement groups
- `POST /api/audit` → `{ courses: [...], program }` → `{ satisfied: [...], missing: [...] }`

### 4. Courses (`/courses`) — Course Catalog
- Search bar (live filter by name/department)
- Grid of course cards: code, title, credits, department
- Click card → detail panel (description, what requirements it can satisfy)
- Filter chips: department, credits

**API:** `GET /api/courses?q=bio&dept=biology` → course list

### 5. Transcript Upload (`/transcript`) — MVP out of scope
- Placeholder page: "Coming soon — upload your transcript for automatic course parsing"
- Not in MVP scope — skip for now

---

## Design Language

**Color palette:**
- Background: `bg-slate-950` (deep navy)
- Surface: `bg-slate-900`
- Border: `border-slate-800`
- Primary: `indigo-600` (user bubbles, buttons, links)
- Text: white, `text-slate-400` for secondary
- Success: `emerald-600` (satisfied requirements)
- Warning: `amber-500` (missing requirements)

**Typography:**
- Font: system sans (no custom fonts needed)
- Headings: `text-3xl font-bold`
- Body: `text-sm`
- Mono: `font-mono` for course codes

**Spacing:** `max-w-5xl mx-auto px-6 py-8` page container

**No table support** — use bullet lists and cards instead.

---

## Components

### NavBar
- Logo left: "path" in bold + "gradYOU8" subtitle in slate
- Links: Ask, Audit, Courses
- Right side: build badge "vectorless RAG + MiniMax" (small, slate-600)

### CourseCard
- States: default, hover (border-slate-700), selected
- Shows: code (mono), title, credits badge, department tag

### RequirementGroup (Audit page)
- Satisfied: green left-border, checkmark icon, course that satisfied it
- Missing: amber left-border, ⚠ icon, description + suggested fill courses

### ChatBubble
- User: right-aligned, indigo background, no border
- Assistant: left-aligned, slate-800 background, rounded-xl
- Sources: collapsible section below assistant bubble

### SourceCard
- Title in bold, page range in mono, excerpt in italic
- Background: slate-800

---

## State Management

**No Redux needed** — React state + Context sufficient for MVP:
- `ChatContext`: messages, loading, streaming
- `AuditContext`: added courses, selected program, audit results
- `CoursesContext`: search query, filters, results

---

## Backend API (FastAPI)

### Endpoints

```
GET  /api/health
     → { "status": "ok", "indexed": bool }

GET  /api/tree
     → { "num_nodes": int, "roots": [...] }

POST /api/chat
     body: { "question": str, "chat_history": [] }
     → { "answer": str, "sources": [{ "title": str, "page_range": str, "text": str }] }

GET  /api/courses
     query: ?q=bio&dept=biology&limit=20
     → { "courses": [{ "id": str, "title": str, "credits": int, "department": str }] }

GET  /api/requirements?program=biology-ba
     → { "groups": [{ "group": str, "description": str, "courses": [...], "credits_required": int }] }

POST /api/audit
     body: { "courses": [str], "program": str }
     → { "satisfied": [{ "group": str, "courses": [str] }], "missing": [{ "group": str, "description": str, "suggested": [str] }] }

POST /api/courses (add course to tracker)
     body: { "course_id": str, "semester": str, "grade": str }
     → { "id": int }
```

---

## Tech Stack (confirmed)

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind (already scaffolded) |
| Backend | FastAPI + Python 3.11 |
| RAG | MiniMax M2.7 via OpenClaw agent |
| Database | SQLite (bulletin tree + course data + student courses) |
| PDF parsing | PyMuPDF (already in requirements.txt) |

**Backend runs on port 8000.** Frontend Vite proxies `/api` → `localhost:8000`.

---

## File Structure

```
washu-navigator/
├── frontend/                      (already exists)
│   ├── src/
│   │   ├── App.tsx                (update: add Courses page route)
│   │   ├── pages/
│   │   │   ├── Chat.tsx            (refine: streaming, better sources UI)
│   │   │   ├── Audit.tsx           (wire to backend)
│   │   │   └── Courses.tsx         (CREATE: catalog page)
│   │   ├── components/
│   │   │   ├── NavBar.tsx          (CREATE)
│   │   │   ├── CourseCard.tsx       (CREATE)
│   │   │   ├── SourceCard.tsx      (CREATE)
│   │   │   └── RequirementGroup.tsx (CREATE)
│   │   └── context/
│   │       ├── ChatContext.tsx     (CREATE)
│   │       └── AuditContext.tsx    (CREATE)
│   ├── index.html
│   ├── vite.config.ts             (add /api proxy)
│   └── package.json
│
├── backend/                       (CREATE)
│   ├── main.py                    (FastAPI app)
│   ├── routers/
│   │   ├── chat.py
│   │   ├── courses.py
│   │   └── audit.py
│   ├── services/
│   │   ├── rag_engine.py          (MiniMax M2.7 calls + PageIndex logic)
│   │   └── audit_engine.py
│   ├── db/
│   │   ├── models.py
│   │   └── schema.sql
│   └── requirements.txt
│
├── data/
│   ├── bulletin_full.json         (already exists — RAG source)
│   ├── equivalencies.json         (already exists)
│   └── pageindex_cache.json       (already exists)
│
├── scripts/
│   └── ingest_bulletin.py         (already exists — run_llm_scored_rag.py)
│
├── SPEC.md                        (already exists — this is the source of truth)
└── README.md
```

---

## MVP Scope (what to build)

**Phase 1 — Backend + Chat (highest value)**
1. FastAPI app with health + tree endpoints
2. `POST /api/chat` — wire to existing `run_llm_scored_rag.py` logic
3. `GET /api/courses` — return course list from SQLite
4. Frontend Chat page: wire to `/api/chat`, show sources nicely

**Phase 2 — Audit**
5. `GET /api/requirements` — load requirement groups from DB
6. `POST /api/audit` — run audit against entered courses + equivalency table
7. Frontend Audit page: wire to real endpoints

**Phase 3 — Courses catalog**
8. `GET /api/courses` with search + filter
9. Frontend Courses page with detail panel

**Out of scope:**
- Transcript upload (hard — OCR + PDF parsing variability)
- Multi-year planning
- Student auth / persistence

---

## Dependencies to Add (frontend)

```json
{
  "dependencies": {
    "react-router-dom": "^6.24.0",
    "lucide-react": "^0.400.0"
  }
}
```

`lucide-react` for icons (check, warning, search, graduation-cap, etc.)

---

## Testing Plan

### Frontend Tests (Vitest + React Testing Library)
1. `NavBar` renders all links
2. `Chat` — submitting a question adds user message + triggers API call
3. `Chat` — loading state shows "Thinking..."
4. `Audit` — adding a course appears in the list
5. `Audit` — run audit shows satisfied/missing results
6. `Courses` — searching filters the course list

### Integration Tests
7. Full flow: add courses → run audit → see correct satisfied/missing
8. Chat: question → answer → sources shown

---

## Acceptance Criteria

- [ ] Frontend builds with `npm run build` (zero TypeScript errors)
- [ ] Chat page: question → response in < 5s (backend on localhost)
- [ ] Sources section: shows document title + page range for each source
- [ ] Audit page: add course → run audit → green/amber results displayed
- [ ] Courses page: search returns results in < 1s
- [ ] All 3 pages accessible via nav bar
- [ ] No placeholder text like "TODO" or "coming soon" on core pages
- [ ] Mobile-friendly (single column on small screens)

---

*Spec version: 1.0 — created 2026-04-04 — frontend focus*