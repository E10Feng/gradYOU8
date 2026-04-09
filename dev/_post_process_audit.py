"""
WashU Navigator — Post-audit equivalency post-processor.
Run after audit() to apply course equivalencies to the raw result.
"""

import json, os

EQUIV_PATH = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\equivalencies.json"

def load_equiv():
    if not os.path.exists(EQUIV_PATH):
        return {}
    with open(EQUIV_PATH) as f:
        return json.load(f)

def build_reverse_map(equiv):
    """Build: official_code -> [(student_code, title, equiv_status)]"""
    rev = {}
    for dept, courses in equiv.items():
        if dept.startswith("_"):
            continue
        for student_code, info in courses.items():
            official = info.get("official")
            if official:
                rev.setdefault(official, []).append({
                    "code": student_code,
                    "title": info.get("title", ""),
                    "status": info.get("equiv_status", ""),
                    "note": info.get("note", "")
                })
    return rev

def apply_equivalencies(result, verbose=False):
    """Fix requirement.satisfied_by using the equivalency table."""
    equiv = load_equiv()
    rev = build_reverse_map(equiv)

    # Build forward map: student_code -> official
    fwd = {}
    for dept, courses in equiv.items():
        if dept.startswith("_"):
            continue
        for student_code, info in courses.items():
            official = info.get("official")
            if official and info.get("equiv_status") == "confirmed":
                fwd[student_code] = official

    audit = result.get("audit", {})
    for section_key in ["major", "minor"]:
        section = audit.get(section_key, {})
        for req in section.get("requirements", []):
            # Check satisfied_by / taken field
            taken = req.get("satisfied_by") or req.get("taken", "")
            if not taken or taken in (True, False):
                continue
            # If taken uses a non-official code, note the equivalence
            for student_code, official in fwd.items():
                if student_code in taken and student_code != official:
                    current_note = req.get("note", "")
                    req["note"] = (current_note + f" [OR EQUIVALENT: {student_code} = {official}]").strip()
                    if verbose:
                        print(f"  {section_key}: {taken} -> {official}")
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator")
    from run_llm_scored_rag import load_student_profile, audit
    profile = load_student_profile()
    result = audit(profile)
    result = apply_equivalencies(result, verbose=True)
    from run_llm_scored_rag import audit_to_text
    print(audit_to_text(result))
