# gradYOU8 — Backend Build Specification

## What Already Exists

```
backend/
├── main.py           # FastAPI — /ingest, /tree, /chat (PageIndex-based)
├── libs/             # pageindex_agent (vectorless RAG fork)
├── .env.example
└── test_pageindex.py
```

**Confirmed working:**
- `POST /ingest` — ingests bulletin PDF → tree index via PageIndex
- `GET /tree` — returns num_nodes, doc_name, doc_description
- `POST /chat` — RAG query via tree reasoning + page extraction; returns answer + sources

**DB:** none yet — all data is in-memory or on disk as JSON

---

## What's Missing (MVP)

### 1. SQLite Database
**File:** `backend/db/schema.sql` + `backend/db/init_db.py`

Tables:
```sql
-- Courses from the WashU bulletin
courses (
  id TEXT PRIMARY KEY,        -- "BIOL 296", "CSE 1301"
  title TEXT,
  credits INTEGER,
  department TEXT,
  description TEXT,
  tags TEXT                  -- JSON array: ["biology", "natural-science", "gateway"]
)

-- Requirement groups per program
requirements (
  id INTEGER PRIMARY KEY,
  program TEXT,               -- "biology-ba", "cs-minor-engineering"
  school TEXT,               -- "arts-sciences", "engineering"
  "group" TEXT,              -- "core", "electives", "gateway", "distributions"
  description TEXT,
  credits_required INTEGER,
  allowed_courses TEXT,      -- JSON array of course codes that can satisfy this
  FOREIGN KEY(program) REFERENCES programs(code)
)

-- Programs (major/minor)
programs (
  code TEXT PRIMARY KEY,     -- "biology-ba"
  name TEXT,                 -- "Biology, B.A."
  school TEXT,
  degree TEXT,               -- "BA", "BS", "BSC"
  type TEXT                  -- "major", "minor"
)

-- Student entered courses (client-side for MVP, server-side for persistence)
student_courses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id TEXT,             -- FK to courses.id
  semester TEXT,             -- "Fall 2024"
  grade TEXT                 -- "A", "B+", null
)

-- Equivalencies (course code → official code mapping)
equivalencies (
  old_code TEXT PRIMARY KEY, -- "CSE-E81 131"
  official_code TEXT,        -- "CSE 131"
  equivalent BOOLEAN,         -- 1 or 0
  note TEXT
)
```

**Seed data needed:**
- Programs: biology-ba (A&S), cs-minor-engineering (Engineering), etc.
- Requirements: loaded from `data/equivalencies.json` + hardcoded WashU req structures
- Equivalencies: loaded from `data/equivalencies.json`
- Courses: seeded from bulletin data (can be minimal for MVP — just the key courses)

### 2. Course Catalog API

**`GET /api/courses`** — Search/browse courses
```
Query params:
  q           — search query (matches title, id, department)
  dept        — filter by department
  limit       — max results (default 20, max 100)

Response: { "courses": [{ "id", "title", "credits", "department", "description" }] }
```

**`GET /api/courses/{id}`** — Course detail
```
Response: { "id", "title", "credits", "department", "description", "tags", "satisfies": ["req_group_1", ...] }
```

**Implementation:** Query SQLite `courses` table. No LLM needed — plain SQL LIKE search + index.

### 3. Requirements API

**`GET /api/requirements`** — Get all requirement groups for a program
```
Query params:
  program   — program code (e.g., "biology-ba", "cs-minor-engineering")

Response: {
  "program": { "code": "biology-ba", "name": "Biology, B.A.", "school": "arts-sciences" },
  "groups": [
    {
      "group": "gateway",
      "description": "Gateway courses",
      "credits_required": 12,
      "courses": ["BIOL 296", "BIOL 297", "CHEM 111", "CHEM 112"]
    },
    ...
  ]
}
```

**Source of truth:** Hardcode WashU requirement structures for MVP. Data lives in `requirements` table seeded from a `seed_data.json`.

### 4. Audit Engine — Core Feature

**`POST /api/audit`** — Run graduation audit
```
Body: {
  "courses": ["CSE-E81 131", "CSE-E81 247", "BIOL 296", "CHEM 111A"],
  "program": "biology-ba",
  "minor": "cs-minor-engineering"
}

Response: {
  "student": { "name": "", "school": "arts-sciences" },
  "audit": {
    "major": {
      "code": "biology-ba",
      "name": "Biology, B.A.",
      "status": "IN_PROGRESS",   -- COMPLETE | IN_PROGRESS | MISSING_REQUIREMENTS
      "groups": [
        {
          "group": "gateway",
          "status": "SATISFIED",
          "satisfied_by": ["BIOL 296", "CHEM 111"],
          "remaining": []
        },
        {
          "group": "electives",
          "status": "IN_PROGRESS",
          "satisfied_by": ["CSE-E81 131"],   -- counts as outside elective
          "remaining": ["3 more 3000+ courses"]
        }
      ]
    },
    "minor": {
      "code": "cs-minor-engineering",
      "name": "Computer Science Minor (CSE)",
      "status": "IN_PROGRESS",
      "groups": [
        {
          "group": "core",
          "status": "PARTIAL",
          "satisfied_by": ["CSE 131", "CSE 2407"],   -- equivalencies resolved
          "missing": ["CSE 1302"]                     -- CSE-E81 132 NOT equivalent
        }
      ]
    }
  }
}
```

**Audit algorithm:**
```
For each program (major + minor):
  For each requirement group:
    Check each of student's courses against allowed_courses
    Resolve equivalencies (CSE-E81 131 → CSE 131)
    Mark group: COMPLETE if all required courses present, PARTIAL if some, MISSING if none
    Track which specific courses satisfied which groups
    Handle double-counting: courses that are in both major and minor allowed lists
```

**Equivalency handling:**
- Load `data/equivalencies.json` at startup
- When checking if a course satisfies a requirement:
  1. Check if course code is directly in allowed_courses
  2. If not, look up equivalencies table: does `student_course_code` map to an allowed code?
  3. Check `equivalent` flag — if false, course does NOT count

### 5. Student Course Tracker

**`GET /api/me/courses`** — Get all tracked courses
```
Response: { "courses": [{ "id", "course_id": "BIOL 296", "title", "semester", "grade" }] }
```

**`POST /api/me/courses`** — Add a course to tracker
```
Body: { "course_id": "BIOL 296", "semester": "Fall 2024", "grade": "A" }
Response: { "id": 1, "course_id": "BIOL 296" }
```

**`DELETE /api/me/courses/{id}`** — Remove a tracked course

### 6. Health Check

**`GET /api/health`** — Confirm services are up
```
Response: { "status": "ok", "db": true, "tree_indexed": bool, "courses_count": int }
```

---

## File Structure (Backend Additions)

```
backend/
├── main.py                    (exists)
├── libs/                      (exists)
├── db/
│   ├── schema.sql             (CREATE)
│   ├── init_db.py             (CREATE: create tables + seed data)
│   ├── models.py              (CREATE: Pydantic models for DB rows)
│   └── seed_data.json         (CREATE: WashU requirements seed data)
├── routers/
│   ├── courses.py             (CREATE: GET /api/courses, GET /api/courses/{id})
│   ├── requirements.py        (CREATE: GET /api/requirements)
│   ├── audit.py               (CREATE: POST /api/audit)
│   └── tracker.py             (CREATE: GET/POST/DELETE /api/me/courses)
├── services/
│   ├── audit_engine.py        (CREATE: audit logic — match courses to requirements)
│   ├── equivalency_resolver.py (CREATE: resolve student course → official code)
│   └── course_search.py       (CREATE: search logic)
└── requirements.txt           (UPDATE: add pydantic, aiosqlite if async)
```

---

## Dependencies to Add

```
fastapi>=0.110
uvicorn>=0.27
aiosqlite>=0.20   # async SQLite
pydantic>=2.6
python-dotenv>=1.0
```

---

## Key Design Decisions

### Equivalency Resolution (Critical)
The equivalency table (`data/equivalencies.json`) is the bridge between student entered courses and official requirement codes. The audit engine MUST use it to:
1. Map student codes → official codes (CSE-E81 131 → CSE 131)
2. Reject non-equivalent courses (CSE-E81 132 is NOT equivalent to CSE 1302)

**Algorithm in `audit_engine.py`:**
```python
def resolve_course(student_code: str) -> str | None:
    """Return official code if equivalent, None if not equivalent."""
    if student_code in equivalencies:
        return equivalencies[student_code]['official_code'] if equivalencies[student_code]['equivalent']
    return student_code  # assume direct match if no equiv entry

def course_satisfies_requirement(student_code: str, allowed_codes: list[str]) -> bool:
    official = resolve_course(student_code)
    if not official:
        return False
    return official in allowed_codes or student_code in allowed_codes
```

### Audit Status Logic
```
group_status:
  SATISFIED   — all required courses present (by code or equivalency)
  PARTIAL    — some required courses present
  MISSING    — no required courses present

program_status:
  COMPLETE              — all groups SATISFIED
  IN_PROGRESS           — some groups PARTIAL or SATISFIED
  MISSING_REQUIREMENTS  — one or more groups MISSING
```

### Double-Counting
A course can satisfy requirements in BOTH major and minor if it appears in both programs' allowed lists. The audit engine should NOT double-count against the student's total credits — just track it per-program.

### No Auth for MVP
Student course tracker uses a single shared store (no user isolation). Auth is out of scope for MVP.

---

## API Summary

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/courses` | Search course catalog |
| GET | `/api/courses/{id}` | Course detail |
| GET | `/api/requirements?program=` | Get requirement groups |
| POST | `/api/audit` | Run graduation audit |
| GET | `/api/me/courses` | List tracked courses |
| POST | `/api/me/courses` | Add tracked course |
| DELETE | `/api/me/courses/{id}` | Remove tracked course |
| GET | `/api/tree` | Get bulletin tree index info |
| POST | `/api/chat` | RAG query (existing) |
| POST | `/api/ingest` | Ingest bulletin PDF (existing) |

---

## Test Cases

1. `test_audit_biology_major` — student has BIOL 296, CHEM 111A, CSE-E81 131 → biology-ba partially satisfied, gateway satisfied
2. `test_audit_cs_minor` — student has CSE-E81 131, CSE-E81 247 → core partially satisfied, CSE 1302 still missing
3. `test_audit_double_count` — CSE 1301 in both biology (outside elective) and cs-minor (core) → shows in both
4. `test_equivalency_not_equivalent` — CSE-E81 132 does NOT satisfy CSE 1302 requirement
5. `test_course_search` — search "bio" returns biology courses
6. `test_course_detail` — GET /api/courses/BIOL-296 returns description + satisfies list

---

## Out of Scope

- Student authentication / multi-user
- Transcript PDF upload + OCR
- Real-time course schedule from WashU API
- Grade-aware GPA calculations
- Persistent user sessions (cookies/tokens)

---

*Spec version: 1.0 — created 2026-04-04 — backend additions*