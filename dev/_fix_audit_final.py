def audit_to_text(result):
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
    student_name = s.get("name", "Student")
    student_gpa = str(s.get("gpa", "N/A"))
    student_school = s.get("school", "")
    lines.append("  " + student_name + " | GPA: " + student_gpa + " | " + student_school)
    lines.append("=" * 50)

    for key, label in [("major", "MAJOR"), ("minor", "MINOR")]:
        sec = a.get(key, {})
        if not sec or "error" in sec:
            lines.append("")
            lines.append("  [" + label + ": Could not retrieve requirements]")
            continue
        status = get_icon(sec.get("status", ""))
        sec_name = sec.get("name", key.upper())
        lines.append("")
        lines.append("  [" + status + "] " + sec_name)
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
        dbl_str = ", ".join(str(d) for d in dbl)
        lines.append("  DOUBLE-COUNTED: " + dbl_str)

    return "\n".join(lines)
