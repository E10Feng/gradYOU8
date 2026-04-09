# gradYOU8 — Graduation Progress Navigator: Build Spec

## Overview

Build a full-stack web app where students upload their WashU transcript PDF and see their graduation requirement progress — which courses they've completed, what's remaining, and % done per requirement group. Uses the existing RAG system to dynamically fetch requirements for any program (no hardcoding).

**Stack:** React + Vite (frontend), FastAPI (backend), Minimax LLM, WashU Bulletin RAG

---

## Part 1: Backend — Upload & Profile

### `POST /api/upload-transcript`
- **Input:** `multipart/form-data` with field `file` (PDF transcript)
- **Process:** 
  1. Save PDF temporarily to `data/uploads/{uuid}.pdf`
  2. Run `transcript_to_json.py` as subprocess on the PDF
  3. Parse stdout JSON → student profile
  4. Delete temp PDF
- **Output:**
  ```json
  {
    "student": {
      "name": "Ethan Feng",
      "school": "arts-sciences",
      "graduation_year": 2026,
      "majors": ["Biology Major, Genomics and Computational Biology Specialization"],
      "minors": []
    },
    "courses": [
      {"code": "BIOL 296", "title": "Intro to Biology I", "credits": 3, "semester": "Fall 2023", "grade": "A"}
    ],
    "gpa": 3.78
  }
  ```
- **Errors:** 400 if not a PDF, 422 if transcript parsing fails

### `GET /api/profile`
- Returns the currently loaded student profile (from last upload)
- 404 if no profile loaded yet

---

## Part 2: Backend — RAG-Powered Requirements

### `POST /api/requirements`
- **Input:** `{ "program": "Biology Major, Genomics and Computational Biology Specialization" }`
- **Process:**
  1. `keyword_tree_search()` finds the matching tree node
  2. `get_text_of_pages()` extracts PDF pages for that program
  3. A secondary Minimax call parses the raw text into structured requirements
- **Output:**
  ```json
  {
    "program": "Biology Major, Genomics and Computational Biology Specialization",
    "school": "arts-sciences",
    "groups": [
      {
        "name": "Advanced Biology Coursework",
        "required_credits": 18,
        "required_courses": ["BIOL 3000+ (3000-level or above)"],
        "distribution": [
          {"area": "A: Cellular & Molecular", "courses": ["BIOL 3240", "BIOL 3340", ...]},
          {"area": "B: Organismal Biology", "courses": ["BIOL 3057", "BIOL 3151", ...]},
          {"area": "C: Evolution, Ecology & Population", "courses": ["BIOL 3220", "BIOL 3470", ...]}
        ],
        "specializations": ["BIOL 3240", "BIOL 4183", "BIOL 4344", "BIOL 5480", "BIOL 5488"],
        "lab_required": true,
        "lab_options": ["BIOL 3492", "BIOL 3493", "BIOL 4220", "BIOL 4342", "BIOL 4343", "BIOL 4346", "BIOL 4522", "BIOL 4525"]
      }
    ]
  }
  ```
- **Cache:** Requirements responses cached in memory by program name (keyed on normalized name)

### `POST /api/audit-full`
- **Input:** `{ "program": "...", "courses": [...] }`  
  OR uses the currently uploaded profile if `program` not specified
- **Process:**
  1. Fetch requirements via RAG (`/api/requirements`)
  2. Run audit logic against student's courses
  3. Return detailed progress report
- **Output:**
  ```json
  {
    "program": "Biology Major, GCB Specialization",
    "overall_percent": 67,
    "groups": [
      {
        "name": "Advanced Biology (18 units)",
        "status": "PARTIAL",
        "percent": 50,
        "satisfied": ["BIOL 3240 (3.0 cr)", "BIOL 4183 (3.0 cr)"],
        "remaining": ["Area A: 1 more course", "Area B: 1 more course", "Area C: 2 more courses"],
        "credit_progress": "6 / 18 credits"
      }
    ]
  }
  ```

---

## Part 3: Backend — Chat (Existing, Enhanced)

### `POST /api/chat`
- Already exists and works
- Enhance system prompt to include student profile context when loaded:
  ```
  Student: {name}, {school}
  Majors: {majors}
  Minors: {minors}
  Courses taken: {course_list}
  
  When answering requirements questions, reference the student's actual 
  completed courses when relevant.
  ```

---

## Part 4: Frontend — Audit Page

### Layout
```
┌─────────────────────────────────────────────────────────┐
│  [Upload PDF]  [student name]  [GPA: 3.78]  [School: A&S] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MAJORS                                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Biology Major, GCB Specialization                │   │
│  │ ████████████████████░░░░░░░░  67%               │   │
│  │                                                 │   │
│  │ Advanced Biology (18 credits)     ████████░░ 67%  │   │
│  │ Area A: Cellular & Molecular    ████████░░ 80%  │   │
│  │ Area B: Organismal Biology      ░░░░░░░░░  0%   │   │
│  │ Area C: Evolution & Ecology      ████░░░░░░ 40%  │   │
│  │ Specialization Elective         ████████░░ 67%  │   │
│  │ Lab Requirement                 ✓ Complete      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  MINORS  (none detected)                                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  CHAT — Ask about requirements                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [message history]                                │   │
│  │ [input field]                          [Send]   │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Components

**`TranscriptUpload.tsx`**
- Drag-and-drop or click-to-upload PDF
- Shows loading spinner while parsing
- On success: populates profile, triggers audit
- On error: shows error message

**`ProgressBar.tsx`**
- Props: `label`, `percent`, `color`
- Animated fill bar

**`RequirementGroup.tsx`**
- Props: `group` (name, status, satisfied, remaining, credit_progress)
- Shows progress bar + list of satisfied courses + remaining items

**`AuditDashboard.tsx`**
- Fetches audit results from `/api/audit-full`
- Renders major/minor cards with requirement groups

**`Chat.tsx`** (existing, modify)
- When student profile is loaded, inject profile context into system prompt
- Chat continues to work standalone (without profile)

### State Management
- `studentProfile` in `App.tsx` state
- On profile load: call `/api/audit-full` for each major/minor
- Store audit results alongside profile

---

## Implementation Order

1. Backend: `POST /api/upload-transcript` + `GET /api/profile`
2. Backend: `POST /api/requirements` (RAG → structured requirements)
3. Backend: `POST /api/audit-full` (requirements → audit)
4. Frontend: `TranscriptUpload` component
5. Frontend: `ProgressBar` + `RequirementGroup` components
6. Frontend: Audit dashboard (replace manual entry)
7. Frontend: Wire profile into chat system prompt
8. Frontend: Loading states + error handling

---

## File Map

### Backend (new files)
- `backend/routers/upload.py` — transcript upload endpoint
- `backend/routers/audit_full.py` — full RAG-powered audit
- `backend/services/requirements_extractor.py` — RAG → structured requirements

### Backend (modified)
- `backend/main.py` — add routers, add profile to app state, enhance chat prompt
- `backend/routers/chat.py` — inject student profile context

### Frontend (new files)
- `frontend/src/components/TranscriptUpload.tsx`
- `frontend/src/components/ProgressBar.tsx`
- `frontend/src/components/RequirementGroup.tsx`
- `frontend/src/components/AuditDashboard.tsx`

### Frontend (modified)
- `frontend/src/pages/Audit.tsx` — integrate upload + dashboard
- `frontend/src/pages/Chat.tsx` — inject profile context

---

## Notes

- All existing RAG infrastructure (bulletin PDF, tree index, `keyword_tree_search`, `get_text_of_pages`) is already in place
- `transcript_to_json.py` already parses transcripts correctly
- Minimax is used for: (a) RAG answer synthesis, (b) requirements text → structured data parsing
- Equivalency resolver (`equivalency_resolver.py`) already exists and is used in audit
- No database needed — profile stored in backend memory (acceptable for prototype)
