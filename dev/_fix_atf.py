"""Replace audit_to_text function in run_llm_scored_rag.py"""

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# def audit_to_text starts at line 469 (1-indexed) = index 468 (0-indexed)
start_idx = 468

new_audit_to_text = """
def audit_to_text(result: dict) -> str:
    if not result or "error" in str(result):
        return "Audit error: " + str(result)

    s = result.get("student", {})
    a = result.get("audit", {})

    icon_map = {
        "COMPLETE": "DONE",
        "IN_PROGRESS": "IN PROGRESS",
        "MISSING_REQUIREMENTS": "MISSING",
        "SATISFIED": "DONE",
        "NOT_TAKEN": "NOT TAKEN",
        "NOT_EQUIVALENT": "NOT EQUIV",
        "MISSING": "MISSING",
        "PARTIAL": "PARTIAL",
    }

    def get_icon(val):
        return icon_map.get(val, val)

    lines = []
    lines.append("=" * 50)
    lines.append("WASHU DEGREE AUDIT")
    lines.append("  " + s.get("name", "Student") + " | GPA: " + str(s.get("gpa", "N/A")) + " | " + s.get("school", ""))
    lines.append("=" * 50)

    for key, label in [("major", "MAJOR"), ("minor", "MINOR")]:
        sec = a.get(key, {})
        if not sec or "error" in sec:
            lines.append("")
            lines.append("  [" + label + ": Could not retrieve requirements]")
            continue
        status = get_icon(sec.get("status", ""))
        lines.append("")
        lines.append("  [" + status + "] " + sec.get("name", key.upper()))
        lines.append("  " + "-" * 40)
        for r in sec.get("requirements", []):
            req_name = r.get("requirement") or r.get("group") or r.get("slot", "")
            taken = r.get("taken") or r.get("satisfied_by", "")
            grade = r.get("grade", "")
            st = get_icon(r.get("status", ""))
            if taken and taken not in ("true", "false", ""):
                extra = (" (" + grade + ")") if grade else ""
                lines.append("    " + st + " " + req_name + extra)
            elif req_name:
                lines.append("    " + st + " " + req_name)
        for m in sec.get("missing", []):
            lines.append("    MISSING: " + str(m))
        if sec.get("gpa_met") is not None:
            lines.append("    GPA req met: " + str(sec["gpa_met"]))

    dbl = a.get("double_counted", [])
    if dbl:
        lines.append("")
        lines.append("  DOUBLE-COUNTED: " + ", ".join(str(d) for d in dbl))

    return "\\n".join(lines)
"""

# Combine: lines[:468] + new_audit_to_text
new_content = "\n".join(lines[:start_idx]) + new_audit_to_text

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done")
