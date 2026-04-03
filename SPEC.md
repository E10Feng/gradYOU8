# WashU Course Navigator — Spec Draft

## Working Title
**Path** — _"find your way through WashU's requirements maze"_

## What It Does
Helps WashU undergrads understand what they need to graduate, track what they've taken, and get accurate answers about requirements without scheduling an advisor appointment.

---

## Problem

- WebSTAC → Workday transition is a mess; Workday's UI for requirements is opaque
- Advisors routinely give incorrect information about major/grad requirements
- Students manually track requirements in spreadsheets or just guess
- No centralized, searchable knowledge base of "can I count this class toward that requirement?"

## Solution

A knowledge assistant + graduation tracker that:
1. Students ask questions in natural language → RAG-powered answers from official sources
2. Students enter classes they've taken → visual map of what's satisfied and remaining
3. (Stretch) Students upload transcripts → automatic class parsing via OCR

---

## Core Features

### MVP

1. **RAG Chat** — students ask "do I need to take organic chem for the bio major?", "can BIOL 296 count as a natural science elective?", "what are the gateway courses for the CS major?"
2. **Class Tracker** — student enters their completed courses; system shows requirements status
3. **Requirement Visualizer** — grid/list showing: requirement group → satisfied / missing / planned
4. **Course Catalog Search** — browse all WashU courses with descriptions

### v2 Stretch
5. **Transcript Upload + OCR** — parse PDF/photo of transcript, auto-extract courses
6. **Multi-year Planning** — suggest which semesters to take remaining courses
7. **What-If Mode** — "what if I switch to the CS major, how far along am I?"

---

## Data Sources

| Source | Format | Scope |
|---|---|---|
| WashU Course Catalog | HTML (web scrape) | All courses, descriptions, credits |
| Program Handbooks | PDF (downloadable) | Major requirements, concentrations |
| Degree Requirements (Arts & Sciences, Engineering, etc.) | HTML (web scrape) | Graduation requirements |
| WashU API (if exists) | JSON | Course schedule, sections |

**Scraping strategy:** Start with Arts & Sciences (largest), then Engineering, then others.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS |
| Backend | FastAPI + Python 3.11 |
| RAG | **PageIndex** (self-hosted) + **Minimix** — vectorless, reasoning-based |
| Reasoning Model | Minimix API (`MiniMax-M2.7`) |
| PDF Parsing | PyMuPDF (fitz) + pdfplumber (for tables) |
| Database | SQLite (tree index + course data) |
| Transcript OCR | pytesseract or hosted OCR API (v2) |
| Scraper | httpx + BeautifulSoup for supplemental pages |
| Deployment | Vercel (frontend) + Railway (backend) |
| Domain | `path.wtf` or `washupath.com` |

---

## RAG Architecture — PageIndex (Vectorless)

**Why PageIndex over vector RAG:**
- Degree requirements are in tables and structured lists — semantic similarity is unreliable for structured domain-specific content
- A 1200-page bulletin is a single document — PageIndex handles long documents natively
- Better explainability: answers cite exact page numbers, not opaque chunk IDs

**How it works:**
1. **Index** — PDF → PageIndex builds a hierarchical tree structure index (natural document sections, not arbitrary chunks)
2. **Query** — LLM agent receives the tree structure, reasons over it to find relevant sections, retrieves specific page ranges, synthesizes answer
3. **No vectors, no chunking, no vector DB**

**Indexing pipeline:**
```
Bulletin PDF (1200pp) 
  → PyMuPDF text extraction
  → PageIndex index() → tree structure index (JSON)
  → Cache tree index locally
```

**Query pipeline:**
```
Student question
  → LLM agent reasons over tree structure
  → get_page_content(pages="50-53") for relevant sections
  → Synthesize answer with page citations
```

**Tables in PDF:**
- Use `pdfplumber` alongside PyMuPDF for table extraction
- Format tables as Markdown before indexing — preserves row/column structure
- If a table is too complex, treat it as a page-level chunk with metadata noting its position

---

## Data Model

```
courses
  course_id (washu code, e.g. "BIOL 296")
  title
  description
  credits
  department
  tags []

requirements
  program (e.g. "biology-ba")
  group (e.g. "core", "electives", "gateway")
  description
  course_codes [] (allowed courses)
  credits_required

student_courses
  course_id (FK)
  semester (e.g. "Fall 2024")
  grade (optional)

pageindex_cache
  doc_id
  tree_index (JSON — serialized PageIndex tree)
  pdf_path (local file path)
  indexed_at (timestamp)
```

---

## API Endpoints

```
GET  /courses?q=...           Search course catalog
GET  /courses/{id}            Course details
GET  /requirements?program=   Get requirements for a program
POST /chat                   RAG question answering
GET  /me/courses             Student's entered courses
POST /me/courses             Add a course to tracker
DELETE /me/courses/{id}      Remove a course
GET  /me/audit?program=      Graduation audit: satisfied vs. remaining
POST /transcript/upload      Upload transcript (stretch)
```

---

## Frontend Pages

### `/` — Home
- Hero: "Stop guessing. Know your requirements."
- Quick links: Browse Courses, Start Audit, Ask a Question
- Semester-at-a-glance if courses entered

### `/courses` — Course Catalog
- Searchable, filterable list of all WashU courses
- Filter by department, credits, tags
- Click course → detail view with description and what requirements it satisfies

### `/audit` — Requirement Audit
- Select program(s) (major + minor + general education)
- Grid showing each requirement group and status:
  - ✅ Satisfied (with course that satisfied it)
  - 🔲 Missing (with suggested courses)
  - 📋 Planned (from student's planned courses)

### `/ask` — Chat
- RAG-powered chat interface
- Sources cited in answer (clickable links to original docs)
- "Did this answer your question?" feedback

### `/transcript` — Upload (stretch)
- Drag-and-drop transcript PDF or photo
- Preview parsed courses before confirming

---

## Unknowns to Resolve

1. **Scraping feasibility** — are there `robots.txt` restrictions? Is there a S3/CDN-hosted version of handbooks?
2. **Course catalog structure** — is it static HTML or dynamically loaded (JS)? Affects scraper choice.
3. **Student identity** — anonymous for now, but if we add transcript upload, we need to think about data privacy.
4. **Credential requirements** — does WashU's data require login? Are there public APIs?
5. **GPT-4o vs local embeddings** — budget for OpenAI API vs. local embedding model (sentence-transformers)?

---

## MVP Scope (what we ship first)

1. ✅ RAG chat over Arts & Sciences + Engineering requirements (scraped from HTML)
2. ✅ Manual course entry + requirement audit
3. ✅ Course catalog search
4. ❌ No transcript upload (harder — OCR, grade parsing, PDF variability)
5. ❌ No multi-year planning

---

## Why Students Would Use It

- It's faster than reading the 80-page handbook
- It's more accurate than asking advisors (who get it wrong)
- It works on mobile
- It's free
