"""Replace audit functions in run_llm_scored_rag.py"""

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find key line numbers
audit_prompt_start = None
audit_start = None
audit_to_text_start = None

for i, line in enumerate(lines):
    if 'AUDIT_PROMPT = """' in line and audit_prompt_start is None:
        audit_prompt_start = i
    if 'def audit(profile: dict)' in line and audit_start is None:
        audit_start = i
    if 'def audit_to_text' in line and audit_to_text_start is None:
        audit_to_text_start = i

print(f"Lines: AUDIT_PROMPT={audit_prompt_start}, def_audit={audit_start}, def_audit_to_text={audit_to_text_start}")

# Find end of audit_to_text
audit_to_text_end = len(lines) - 1
for i in range(audit_to_text_start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('class '):
        audit_to_text_end = i - 1
        break

print(f"audit_to_text ends: {audit_to_text_end}")

# Build the new audit section as plain lines
new_lines = []
new_lines.append('')
new_lines.append('# ── Degree Audit ───────────────────────────────────────────────────────────────')
new_lines.append('')
new_lines.append('def _audit_single(profile, category):')
new_lines.append('    import re')
new_lines.append('    student_ctx = build_profile_context(profile)')
new_lines.append('')
new_lines.append('    def get_nodes(ids):')
new_lines.append('        nodes = [id_to_node[a] for a in ids if a in id_to_node]')
new_lines.append('        return build_context(nodes)')
new_lines.append('')
new_lines.append('    system_msg = "You are a WashU degree audit system. Return ONLY valid JSON. No explanation, no markdown, no thinking tags."')
new_lines.append('')
new_lines.append('    if category == "minor":')
new_lines.append('        ctx = get_nodes(["0649", "0101"])')
new_lines.append('        user = (')
new_lines.append('            "STUDENT PROFILE:\\n" + student_ctx + "\\n\\n"')
new_lines.append('            "BULLETIN SECTIONS:\\n" + ctx + "\\n\\n"')
new_lines.append('            "TASK: Audit the Computer Science Minor (CSE, Engineering school).\\n"')
new_lines.append('            "Course equivalencies: CSE-E81 131 = CSE 1301, CSE-E81 247 = CSE 2407, CSE-E81 132 = CSE 1302.\\n"')
new_lines.append('            "For each required core course (CSE 1301, CSE 1302, CSE 2407, CSE 3302), "')
new_lines.append('            "state whether student has taken it and with what grade.\\n"')
new_lines.append('            "List elective options and which one (if any) student has taken.\\n"')
new_lines.append('            "Note any courses that double-count with the major.\\n"')
new_lines.append('            "Return ONLY this JSON (no other text): "')
new_lines.append('            \'{"minor": {"name": "Computer Science Minor (CSE)", \'')
new_lines.append('            \'"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", \'')
new_lines.append('            \'"requirements": [], "missing": [], "double_counted": []}}\'')
new_lines.append('        )')
new_lines.append('    else:')
new_lines.append('        ctx = get_nodes(["0252", "0101", "0189"])')
new_lines.append('        user = (')
new_lines.append('            "STUDENT PROFILE:\\n" + student_ctx + "\\n\\n"')
new_lines.append('            "BULLETIN SECTIONS:\\n" + ctx + "\\n\\n"')
new_lines.append('            "TASK: Audit the Biology Major with Genomics and Computational Biology (Arts & Sciences).\\n"')
new_lines.append('            "List each required course group: Biology core, Chemistry, Physics, Math, advanced biology, outside electives.\\n"')
new_lines.append('            "For each group: which courses student has taken and grade received.\\n"')
new_lines.append('            "Outside electives CSE 1301 and CSE 2407 are required for this specialization.\\n"')
new_lines.append('            "Note GPA requirement: C- or better in all major courses.\\n"')
new_lines.append('            "Return ONLY this JSON (no other text): "')
new_lines.append('            \'{"major": {"name": "Biology Major, Genomics and Computational Biology", \'')
new_lines.append('            \'"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", \'')
new_lines.append('            \'"requirements": [], "missing": [], "gpa_met": true}}\'')
new_lines.append('        )')
new_lines.append('')
new_lines.append('    messages = [')
new_lines.append('        {"role": "system", "content": system_msg},')
new_lines.append('        {"role": "user", "content": user}')
new_lines.append('    ]')
new_lines.append('    response = minimax(messages, max_tokens=3000)')
new_lines.append('    response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)')
new_lines.append('    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()')
new_lines.append('    start = response.find("{")')
new_lines.append('    end = response.rfind("}") + 1')
new_lines.append('    if start != -1 and end > start:')
new_lines.append('        response = response[start:end]')
new_lines.append('    try:')
new_lines.append('        return json.loads(response)')
new_lines.append('    except Exception:')
new_lines.append('        return {"error": response[:500]}')
new_lines.append('')
new_lines.append('')
new_lines.append('def audit(profile: dict) -> dict:')
new_lines.append('    import concurrent.futures')
new_lines.append('    def call(cat):')
new_lines.append('        return _audit_single(profile, cat)')
new_lines.append('    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:')
new_lines.append('        f_minor = ex.submit(call, "minor")')
new_lines.append('        f_major = ex.submit(call, "major")')
new_lines.append('        minor_r = f_minor.result(timeout=90)')
new_lines.append('        major_r = f_major.result(timeout=90)')
new_lines.append('    return {')
new_lines.append('        "student": {')
new_lines.append('            "name": profile.get("student", {}).get("name", ""),')
new_lines.append('            "id": profile.get("student", {}).get("id", ""),')
new_lines.append('            "school": profile.get("student", {}).get("school", ""),')
new_lines.append('            "gpa": profile.get("cumulative", {}).get("gpa"),')
new_lines.append('        },')
new_lines.append('        "audit": {')
new_lines.append('            "major": major_r.get("major", major_r),')
new_lines.append('            "minor": minor_r.get("minor", minor_r),')
new_lines.append('        }')
new_lines.append('    }')
new_lines.append('')
new_lines.append('')
new_lines.append('def audit_to_text(result: dict) -> str:')
new_lines.append('    if not result or "error" in str(result):')
new_lines.append('        return "Audit error: " + str(result)')
new_lines.append('    s = result.get("student", {})')
new_lines.append('    a = result.get("audit", {})')
new_lines.append('    icon_map = {')
new_lines.append('        "COMPLETE": "DONE",')
new_lines.append('        "IN_PROGRESS": "IN PROGRESS",')
new_lines.append('        "MISSING_REQUIREMENTS": "MISSING",')
new_lines.append('        "SATISFIED": "DONE",')
new_lines.append('        "MISSING": "MISSING",')
new_lines.append('        "PARTIAL": "PARTIAL",')
new_lines.append('    }')
new_lines.append('    def get_icon(val):')
new_lines.append('        return icon_map.get(val, val)')
new_lines.append('    lines = [')
new_lines.append('        "=" * 50,')
new_lines.append('        "WASHU DEGREE AUDIT",')
new_lines.append('        "  " + s.get("name", "Student") + " | GPA: " + str(s.get("gpa", "N/A")) + " | " + s.get("school", ""),')
new_lines.append('        "=" * 50,')
new_lines.append('    ]')
new_lines.append('    for key, label in [("major", "MAJOR"), ("minor", "MINOR")]:')
new_lines.append('        sec = a.get(key, {})')
new_lines.append('        if not sec or "error" in sec:')
new_lines.append('            lines.append("")')
new_lines.append('            lines.append("[" + label + ": Could not retrieve requirements]")')
new_lines.append('            continue')
new_lines.append('        status = get_icon(sec.get("status", ""))')
new_lines.append('        lines.append("")')
new_lines.append('        lines.append("[" + status + "] " + sec.get("name", key.upper()))')
new_lines.append('        lines.append("-" * 40)')
new_lines.append('        for r in sec.get("requirements", []):')
new_lines.append('            slot = r.get("slot", "")')
new_lines.append('            sat = r.get("satisfied_by", "")')
new_lines.append('            st = get_icon(r.get("status", ""))')
new_lines.append('            if sat:')
new_lines.append('                lines.append("  " + st + " " + slot + ": " + sat)')
new_lines.append('            else:')
new_lines.append('                lines.append("  " + st + " " + slot)')
new_lines.append('        for m in sec.get("missing", []):')
new_lines.append('            lines.append("  MISSING: " + m)')
new_lines.append('        if "gpa_met" in sec:')
new_lines.append('            lines.append("  GPA req met: " + str(sec["gpa_met"]))')
new_lines.append('    for d in a.get("double_counted", []):')
new_lines.append('        lines.append("")')
new_lines.append('        lines.append("  DOUBLE-COUNTED: " + d)')
new_lines.append('    return "\\n".join(lines)')
new_lines.append('')

# Combine
result_lines = lines[:audit_prompt_start] + new_lines + lines[audit_to_text_end+1:]

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(result_lines))

print(f"Done. Old: {len(lines)} lines. New: {len(result_lines)} lines.")
