"""
POST /api/upload-transcript — accept a PDF transcript, parse it, and store the student profile.
"""
import json
import subprocess
import uuid
import asyncio
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Request, BackgroundTasks
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["upload"])

# Path to the transcript_to_json.py script (relative to backend/main.py)
_BACKEND_ROOT = Path(__file__).parent.parent
# transcript_to_json.py lives at gradYOU8/, one level above backend/
TRANSCRIPT_SCRIPT = _BACKEND_ROOT.parent / "transcript_to_json.py"
DATA_DIR = _BACKEND_ROOT.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"


def _normalize_program_name(raw_name: str) -> tuple[str, str]:
    """
    Normalize noisy transcript program labels to bulletin-friendly names.
    Returns: (normalized_name, type)
    """
    name = (raw_name or "").strip()
    lower = name.lower()

    # Strong explicit minor detection first.
    if " minor" in lower:
        # Canonicalize common shorthand variants.
        if "computer science" in lower:
            return "Computer Science Minor", "minor"
        return name, "minor"

    # Transcript parser occasionally hallucinates this for CS minor.
    # If "second major in computer science + mathematics" appears,
    # normalize to the known minor unless transcript explicitly says major.
    if "second major" in lower and "computer science" in lower and "mathematics" in lower:
        return "Computer Science Minor", "minor"

    # Default: major.
    return name, "major"


def _run_parser(pdf_path: Path) -> dict:
    """Run transcript_to_json.py and return parsed JSON output."""
    result = subprocess.run(
        ["C:\\Users\\Ethan\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", str(TRANSCRIPT_SCRIPT), str(pdf_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Parser script failed: {result.stderr}")

    # The script saves JSON to data/student_profile.json — read it directly.
    profile_path = DATA_DIR / "student_profile.json"
    if not profile_path.exists():
        raise RuntimeError(f"Parser did not produce profile file: {profile_path}")
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/upload-transcript")
async def upload_transcript(file: UploadFile = File(...), request: Request = None):
    """
    Accept a PDF transcript, parse it, and store the result in app.state.current_profile.

    Returns:
        {
          "student": { name, id, ... },
          "courses": [...],   # flat list of all courses taken
          "gpa": float,
          "programs": [...]   # majors and minors
        }
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    # Save to temp location
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    tmp_path = UPLOADS_DIR / f"{file_id}.pdf"

    try:
        content = await file.read()
        tmp_path.write_bytes(content)

        # Parse the PDF
        profile = _run_parser(tmp_path)

        # Validate required fields
        if not profile.get("student"):
            raise ValueError("Parsed profile is missing 'student' field.")
        if not profile.get("semesters") and not profile.get("courses"):
            raise ValueError("Parsed profile has no course data.")

        # Flatten semesters into a courses list for convenience
        semesters = profile.get("semesters", [])
        courses = []
        for sem in semesters:
            for c in sem.get("courses", []):
                courses.append({
                    "id": c.get("code", c.get("id", "")),
                    "title": c.get("title", ""),
                    "credits": c.get("credits", 0),
                    "grade": c.get("grade", ""),
                    "semester": sem.get("term", ""),
                })

        gpa = profile.get("cumulative", {}).get("gpa") or profile.get("gpa") or 0.0
        raw_programs = profile.get("programs", [])
        # Normalize school/college field
        school_raw = (profile.get("student", {}).get("school") or "").lower()
        school_normalized = "arts-sciences"
        if "engineer" in school_raw:
            school_normalized = "engineering"
        elif "business" in school_raw:
            school_normalized = "business"
        elif "art" in school_raw and "sci" in school_raw:
            school_normalized = "arts-sciences"
        # Infer type from program name and attach normalized school
        programs = []
        for p in raw_programs:
            name, prog_type = _normalize_program_name(p.get("name", ""))
            if not name:
                continue
            programs.append({
                "name": name,
                "type": prog_type,
                "school": school_normalized,
            })

        # Store normalized profile in app state for downstream endpoints
        if request is not None:
            normalized_profile = dict(profile)
            normalized_profile["programs"] = programs
            normalized_profile["courses"] = courses
            normalized_profile["student"] = {
                **profile.get("student", {}),
                "school": school_normalized,
            }
            request.app.state.current_profile = normalized_profile

        # ── Pre-warm requirements cache (fire-and-forget, best-effort) ─────────────
        # Warm requirements for all the student's programs + college in the background.
        # This makes the first audit call near-instant since nothing needs to hit the LLM.
        prog_names = [p["name"] for p in programs if p.get("name")]
        school = school_normalized

        def _warm_cache():
            import sys
            sys.path.insert(0, str(_BACKEND_ROOT))
            try:
                from services.requirements_extractor import get_requirements, get_college_requirements
                for prog in prog_names:
                    try:
                        get_requirements(prog)
                        print(f"[cache warm] {prog}: OK")
                    except Exception as e:
                        print(f"[cache warm] {prog}: {e}")
                try:
                    get_college_requirements(school)
                    print(f"[cache warm] college ({school}): OK")
                except Exception as e:
                    print(f"[cache warm] college ({school}): {e}")
            except Exception as e:
                print(f"[cache warm] failed: {e}")

        t = threading.Thread(target=_warm_cache, daemon=True)
        t.start()

        # Normalize and return student data
        raw_student = profile["student"]
        student = {
            "name": raw_student.get("name", ""),
            "id": raw_student.get("id", ""),
            "school": school_normalized,
        }
        return JSONResponse({
            "student": student,
            "courses": courses,
            "gpa": gpa,
            "programs": programs,
        })

    except RuntimeError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Unexpected error: {e}")
    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()
