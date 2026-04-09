"""
WashU Navigator — Transcript Parser
Reusable module: call parse_and_save(pdf_path) → saves to student_profile.json
Telegram/web-app handlers just call this function.
"""

import json, os, re
import fitz  # PyMuPDF

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "data", "student_profile.json")

# ── Public API ────────────────────────────────────────────────────────────────

def parse_and_save(pdf_path: str) -> dict:
    """
    Parse a Workday transcript PDF and save to student_profile.json.
    Returns the parsed profile dict.
    Raises on failure.
    """
    raw = extract_pdf_text(pdf_path)
    profile = parse_transcript(raw)
    save_profile(profile)
    return profile


def load_profile() -> dict | None:
    """Load existing student profile, or None if not yet uploaded."""
    if not os.path.exists(PROFILE_PATH):
        return None
    with open(PROFILE_PATH) as f:
        return json.load(f)


def build_taken_courses_context(profile: dict) -> str:
    """
    Build a compact string summarising all courses taken, suitable for
    injecting into the RAG advisor system prompt.
    """
    lines = []
    for sem in profile.get("semesters", []):
        term = sem.get("term", "Unknown Term")
        gpa = sem.get("gpa")
        codes = [c["code"] for c in sem.get("courses", [])]
        lines.append(f"{term} ({gpa}): {', '.join(codes)}")
    return "\n".join(lines)


# ── PDF Extraction ────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: str) -> str:
    """Extract full text from PDF using PyMuPDF, page by page."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pages.append(f"--- PAGE {i+1} ---\n{page.get_text()}")
    doc.close()
    return "\n".join(pages)


# ── LLM Parsing ───────────────────────────────────────────────────────────────

def get_token():
    auth_path = os.path.join(os.environ["APPDATA"], "npm", "node_modules",
                             "openclaw", "dist", "extensions", "acpx",
                             "agents", "main", "agent", "auth-profiles.json")
    if not os.path.exists(auth_path):
        # Fallback for local dev
        auth_path = r"C:\Users\ethan\.openclaw\agents\main\agent\auth-profiles.json"
    with open(auth_path) as f:
        profiles = json.load(f)
    for name, cfg in profiles.get("profiles", profiles).items():
        if "minimax" in name.lower():
            return cfg.get("access", "")
    return ""


def minimax(messages, max_tokens=8000):
    import urllib.request, urllib.error
    token = get_token()
    payload = {
        "model": "MiniMax-M2.7",
        "messages": messages,
        "max_tokens": max_tokens
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.minimax.io/v1/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


PARSE_PROMPT = """You are a WashU transcript parsing assistant. Extract all course enrollments from a raw Workday transcript.

RULES:
- Course code: first pattern like BIOL 3240, CSE-E81 132, CHINESE 227C, MATH 151, LING 3100, etc. (dept code + number)
- Title: everything after the course code until the next " - " that precedes the semester repetition
- Grade: first token that is A+, A, A-, B+, B, B-, C+, C, C-, D, F, CR, CR#, P, or similar
- Credit hours: the number token after the grade
- CR / CR# / P = Pass (no grade points), record grade_points as 0
- Skip: lines about totals, GPA summaries, standings, headers, footers
- Semester: extract from "Academic Period" lines, apply to all courses until the next Academic Period line
- Programs: extract from the student info block at the top of the transcript
- GPA: per-semester GPA is on "Academic Period Totals" lines (e.g. "Academic Period GPA 3.74")
- Cumulative: from the last "Cumulative Totals" block on the final page

OUTPUT — return ONLY valid JSON:
{
  "student": {
    "id": "508431",
    "name": "E10 Feng",
    "school": "Arts & Sciences"
  },
  "programs": [
    {"name": "Biology Major with Specialization in Genomics and Computational Biology, B.A."},
    {"name": "Computer Science Minor"}
  ],
  "semesters": [
    {
      "term": "Fall 2025",
      "gpa": 3.74,
      "courses": [
        {
          "code": "AMCS 3717",
          "title": "Topics in AMCS",
          "grade": "A",
          "grade_points": 4.0,
          "credits": 3
        }
      ]
    }
  ],
  "cumulative": {
    "gpa": 3.87,
    "credits_earned": 117,
    "gpa_credits": 104
  }
}

Return ONLY the JSON. No explanation, no markdown fences."""


def parse_transcript(raw_text: str) -> dict:
    """Use LLM to parse raw transcript text into structured JSON."""
    messages = [
        {"role": "system", "content": PARSE_PROMPT},
        {"role": "user", "content": f"Raw transcript text:\n\n{raw_text}"}
    ]
    response = minimax(messages, max_tokens=8000)
    # Strip thinking tags and markdown fences
    response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
    response = response.strip().strip("```json").strip("```").strip()
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse transcript: {e}\nResponse: {response[:500]}")


def save_profile(data: dict, path: str = PROFILE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python transcript_to_json.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"Parsing: {pdf_path}")
    profile = parse_and_save(pdf_path)

    s = profile.get("student", {})
    print(f"\nStudent : {s.get('name')} ({s.get('id')})")
    print(f"Programs : {[p['name'] for p in profile.get('programs', [])]}")
    print(f"Semesters: {len(profile.get('semesters', []))}")
    total = sum(len(s["courses"]) for s in profile["semesters"])
    creds  = sum(c["credits"] for s in profile["semesters"] for c in s["courses"])
    print(f"Courses  : {total} courses, {creds} credits")
    print(f"\nProfile saved to: {PROFILE_PATH}")
