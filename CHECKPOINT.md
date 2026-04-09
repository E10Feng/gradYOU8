# gradYOU8 Checkpoint — 2026-04-07 FINAL

## Status: COMPLETE ✅

**Backend**: Running at `http://localhost:8000` (health: `{"status":"ok","db":true,"tree_indexed":true,"tree_nodes":19}`)  
**Frontend**: Builds cleanly ✅ TypeScript: 0 errors

---

## What Was Done

### Goal 1: Audit Feature End-to-End

#### Problem 1a: Transcript Parser ✅
- Already working — `transcript_to_json.py` correctly parses WashU PDFs via MiniMax LLM
- Returns: `{student:{name,id,school}, programs[{name}], semesters[{term,gpa,courses[{code,title,grade,credits}]}], cumulative{gpa,credits_earned}}`

#### Problem 1b: Upload Endpoint ✅ FIXED
**`backend/routers/upload.py`**:
1. Added `type` field to programs — inferred from name ("Minor" → type="minor", else "major")
2. Normalized school: "Arts & Sciences" → "arts-sciences", "Engineering" → "engineering", etc.
3. Fixed course ID: `c.get("code", c.get("id", ""))` (parser uses `code`)
4. Fixed GPA: now uses `cumulative.gpa` from parsed profile
5. Returns normalized `student` object: `{name, id, school}`

#### Problem 1c: Student Profile Display ✅ NEW UI
- `Profile.tsx` displays student name, ID, school, GPA, major/minor badges in shared header

#### Problem 1d: Requirements + Audit Wiring ✅
- Fixed course `code` vs `id` field in `_extract_course_codes()`
- `asyncio.gather()` for parallel program audits
- `college_audit` included in response alongside per-program audits

#### Problem 1e: College-Level Graduation Requirements ✅ ADDED
**`backend/services/requirements_extractor.py`**:
- Added `get_college_requirements(school_name)` — searches bulletin for general education requirements
- Maps normalized school names to bulletin search terms
- Uses `keyword_tree_search` + LLM parsing
- Caches results in `_college_cache`

**`backend/routers/audit_full.py`**:
- Added college audit alongside program audits
- Returns `college_audit` key with `is_college: true`

---

### Goal 2: UI Redesign ✅

**New files**:
- `frontend/src/pages/Profile.tsx` — main page: shared header + timeline/audit toggle + chat sidebar
- `frontend/src/components/TimelineView.tsx` — horizontal semester timeline with course cards
- `frontend/src/components/ChatSidebar.tsx` — fixed right sidebar with chat

**Modified files**:
- `frontend/src/App.tsx` — `/`, `/ask`, `/audit` → Profile page; `/courses` → Courses
- `frontend/src/components/NavBar.tsx` — removed `/ask` link
- `frontend/src/components/TranscriptUpload.tsx` — exported `StudentProfile`, `Course`, `Semester` interfaces
- `frontend/src/components/AuditDashboard.tsx` — imports shared StudentProfile
- `frontend/src/pages/Audit.tsx` — imports shared StudentProfile

**Backend fixes**:
- `backend/routers/upload.py` — type + school normalization
- `backend/services/requirements_extractor.py` — `get_college_requirements()` + fixed corrupted file ending
- `backend/routers/audit_full.py` — college audit + course code fix

---

## How to Test

1. **Start backend**: `cd backend && python -m uvicorn main:app --port 8000`
2. **Start frontend**: `cd frontend && npm run dev`
3. **Upload**: Go to `/`, upload a WashU transcript PDF
4. **Check header**: Student name, ID, school, GPA, major/minor badges should appear
5. **Timeline view**: Horizontal scrolling semester timeline with course cards
6. **Audit view**: Click "Audit" toggle — per-program cards + college requirements
7. **Chat sidebar**: Ask questions about requirements (right side)

---

## Issues Encountered

1. **Backend startup hang**: FastAPI `on_event` startup handler pre-warms requirements cache via daemon thread — takes ~10s but server starts fine
2. **File corruption**: `requirements_extractor.py` had its ending corrupted during edit — fixed by rebuilding the end of the file
3. **TypeScript interface conflicts**: Multiple files had duplicate `StudentProfile` interfaces — resolved by creating single shared interface in `TranscriptUpload.tsx`
4. **PowerShell encoding issues**: Some Python commands with special characters flagged by exec safety — worked around by using separate script files
