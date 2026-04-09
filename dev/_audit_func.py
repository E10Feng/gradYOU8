# This is the replacement audit function and audit_to_text for run_llm_scored_rag.py
# Copy the AUDIT_SYSTEM constant and replace the audit/audit_to_text functions

AUDIT_SYSTEM = (
    "You are a WashU degree audit system. "
    "Return ONLY valid JSON. No explanation, no markdown, no thinking tags."
)

MINOR_AUDIT_USER = (
    "STUDENT PROFILE:\n{student_ctx}\n\n"
    "BULLETIN SECTIONS:\n{minor_ctx}\n\n"
    "TASK: Audit the Computer Science Minor (CSE, Engineering school).\n"
    "Course equivalencies: CSE-E81 131 = CSE 1301, CSE-E81 247 = CSE 2407, CSE-E81 132 = CSE 1302.\n"
    "For each required core course (CSE 1301, CSE 1302, CSE 2407, CSE 3302), "
    "state whether the student has taken it and with what grade.\n"
    "List elective options and which one (if any) the student has taken.\n"
    "Note any courses that double-count with the major.\n"
    "Return ONLY this JSON (no other text):\n"
    '{"minor": {"name": "Computer Science Minor (CSE)", '
    '"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", '
    '"requirements": [{"slot": "CSE 1301", "satisfied_by": "CSE-E81 131 (A)", "status": "SATISFIED"}], '
    '"missing": [], "double_counted": []}}'
)

MAJOR_AUDIT_USER = (
    "STUDENT PROFILE:\n{student_ctx}\n\n"
    "BULLETIN SECTIONS:\n{major_ctx}\n\n"
    "TASK: Audit the Biology Major with Genomics and Computational Biology specialization (Arts & Sciences).\n"
    "List each required course group (Biology core, Chemistry, Physics, Math, advanced biology, outside electives).\n"
    "For each group, state which courses the student has taken and with what grade.\n"
    "Outside electives CSE 1301 and CSE 2407 are required for this specialization.\n"
    "Note GPA requirement (C- or better in all major courses).\n"
    "Return ONLY this JSON (no other text):\n"
    '{"major": {"name": "Biology Major, Genomics and Computational Biology", '
    '"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", '
    '"requirements": [{"slot": "Biology core", "satisfied_by": "BIOL 2970 (A)", "status": "SATISFIED"}], '
    '"missing": [], "gpa_met": true}}'
)


def _audit(profile, category):
    import re
    student_ctx = build_profile_context(profile)

    def get_nodes(ids):
        nodes = [id_to_node[a] for a in ids if a in id_to_node]
        return build_context(nodes)

    if category == "minor":
        ctx = get_nodes(["0649", "0101"])
        user = MINOR_AUDIT_USER.format(student_ctx=student_ctx, minor_ctx=ctx)
        system = AUDIT_SYSTEM
    else:
        ctx = get_nodes(["0252", "0101", "0189"])
        user = MAJOR_AUDIT_USER.format(student_ctx=student_ctx, major_ctx=ctx)
        system = AUDIT_SYSTEM

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
    response = minimax(messages, max_tokens=3000)
    response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
    response = response.strip()
    start = response.find("{")
    end = response.rfind("}") + 1
    if start != -1 and end > start:
        response = response[start:end]
    try:
        return json.loads(response)
    except Exception:
        return {"error": response[:500]}


def audit(profile: dict) -> dict:
    """
    Run a full degree audit for both minor and major in parallel.
    Returns a dict with student info and per-category audit results.
    """
    import concurrent.futures

    def call_audit(category):
        return _audit(profile, category)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_minor = ex.submit(call_audit, "minor")
        f_major = ex.submit(call_audit, "major")
        minor_result = f_minor.result(timeout=90)
        major_result = f_major.result(timeout=90)

    return {
        "student": {
            "name": profile.get("student", {}).get("name", ""),
            "id": profile.get("student", {}).get("id", ""),
            "school": profile.get("student", {}).get("school", ""),
            "gpa": profile.get("cumulative", {}).get("gpa"),
        },
        "audit": {
            "major": major_result.get("major", major_result),
            "minor": minor_result.get("minor", minor_result),
        }
    }


def audit_to_text(audit_result: dict) -> str:
    """Format audit result as readable text."""
    if "error" in str(audit_result):
        return f"Audit error: {audit_result}"

    student = audit_result.get("student", {})
    audit = audit_result.get("audit", {})

    status_icon = {
        "COMPLETE": "COMPLETE",
        "IN_PROGRESS": "IN PROGRESS",
        "MISSING_REQUIREMENTS": "MISSING REQUIREMENTS",
        "SATISFIED": "DONE",
        "MISSING": "MISSING",
        "PARTIAL": "PARTIAL",
    }

    lines = []
    lines.append("=" * 50)
    lines.append("WASHU DEGREE AUDIT")
    lines.append(f"  {student.get('name', 'Student')} | GPA: {student.get('gpa', 'N/A')} | {student.get('school', '')}")
    lines.append("=" * 50)

    for section_key, label in [("major", "MAJOR"), ("minor", "MINOR")]:
        section = audit.get(section_key, {})
        if not section or "error" in section:
            lines.append(f"\n{label}: Could not retrieve requirements.")
            continue

        status = section.get("status", "")
        icon = status_icon.get(status, status)
        lines.append(f"\n[{icon}] {section.get('name', section_key.upper())}")
        lines.append("-" * 40)

        for req in section.get("requirements", []):
            slot = req.get("slot", "")
            satisfied = req.get("satisfied_by", "")
            req_status = req.get("status", "")
            icon2 = status_icon.get(req_status, req_status)
            if satisfied:
                lines.append(f"  {icon2} {slot}: {satisfied}")
            else:
                lines.append(f"  {icon2} {slot}")

        for m in section.get("missing", []):
            lines.append(f"  MISSING: {m}")

        if section.get("gpa_met") is not None:
            lines.append(f"  GPA req met: {section['gpa_met']}")

    dbl = audit.get("double_counted", [])
    if dbl:
        lines.append(f"\n  DOUBLE-COUNTED: {', '.join(dbl)}")

    warnings = audit.get("warnings", [])
    for w in warnings:
        lines.append(f"  WARNING: {w}")

    return "\n".join(lines)
