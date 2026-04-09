"""Replace audit functions in run_llm_scored_rag.py"""
import re

# Read the file
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

print(f"AUDIT_PROMPT starts: {audit_prompt_start}")
print(f"def audit starts: {audit_start}")
print(f"def audit_to_text starts: {audit_to_text_start}")

# Find end of audit_to_text (last non-empty line before EOF or next top-level def)
audit_to_text_end = len(lines) - 1
for i in range(audit_to_text_start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('class '):
        audit_to_text_end = i - 1
        break

print(f"audit_to_text ends: {audit_to_text_end}")

# Build replacement content - must be at top level (no indentation)
new_lines = [
    '',
    '# ── Degree Audit ───────────────────────────────────────────────────────────────',
    '',
    'AUDIT_SYSTEM = (',
    '    "You are a WashU degree audit system. "',
    '    "Return ONLY valid JSON. No explanation, no markdown, no thinking tags."',
    ')',
    '',
    'MINOR_AUDIT_USER = (',
    '    "STUDENT PROFILE:\\n{student_ctx}\\n\\n"',
    '    "BULLETIN SECTIONS:\\n{minor_ctx}\\n\\n"',
    '    "TASK: Audit the Computer Science Minor (CSE, Engineering school).\\n"',
    '    "Course equivalencies: CSE-E81 131 = CSE 1301, CSE-E81 247 = CSE 2407, CSE-E81 132 = CSE 1302.\\n"',
    '    "For each required core course (CSE 1301, CSE 1302, CSE 2407, CSE 3302), "',
    '    "state whether student has taken it and with what grade.\\n"',
    '    "List elective options and which one (if any) student has taken.\\n"',
    '    "Note any courses that double-count with the major.\\n"',
    '    \'Return ONLY this JSON: \'',
    '    \'{"minor": {"name": "Computer Science Minor (CSE)", \'',
    '    \'"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", \'',
    '    \'"requirements": [{"slot": "CSE 1301", "satisfied_by": "CSE-E81 131 (A)", "status": "SATISFIED"}], \'',
    '    \'"missing": [], "double_counted": []}}\'',
    ')',
    '',
    'MAJOR_AUDIT_USER = (',
    '    "STUDENT PROFILE:\\n{student_ctx}\\n\\n"',
    '    "BULLETIN SECTIONS:\\n{major_ctx}\\n\\n"',
    '    "TASK: Audit the Biology Major with Genomics and Computational Biology (Arts & Sciences).\\n"',
    '    "List each required course group: Biology core, Chemistry, Physics, Math, advanced biology, outside electives.\\n"',
    '    "For each group: which courses student has taken and grade received.\\n"',
    '    "Outside electives CSE 1301 and CSE 2407 are required for this specialization.\\n"',
    '    "Note GPA requirement: C- or better in all major courses.\\n"',
    '    \'Return ONLY this JSON: \'',
    '    \'{"major": {"name": "Biology Major, Genomics and Computational Biology", \'',
    '    \'"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", \'',
    '    \'"requirements": [{"slot": "Biology core", "satisfied_by": "BIOL 2970 (A)", "status": "SATISFIED"}], \'',
    '    \'"missing": [], "gpa_met": true}}\'',
    ')',
    '',
    '',
    'def _audit_single(profile, category):',
    '    import re',
    '    student_ctx = build_profile_context(profile)',
    '',
    '    def get_nodes(ids):',
    '        nodes = [id_to_node[a] for a in ids if a in id_to_node]',
    '        return build_context(nodes)',
    '',
    '    if category == "minor":',
    '        ctx = get_nodes(["0649", "0101"])',
    '        user = MINOR_AUDIT_USER.format(student_ctx=student_ctx, minor_ctx=ctx)',
    '    else:',
    '        ctx = get_nodes(["0252", "0101", "0189"])',
    '        user = MAJOR_AUDIT_USER.format(student_ctx=student_ctx, major_ctx=ctx)',
    '',
    '    messages = [',
    '        {"role": "system", "content": AUDIT_SYSTEM},',
    '        {"role": "user", "content": user}',
    '    ]',
    '    response = minimax(messages, max_tokens=3000)',
    '    response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)',
    '    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()',
    '    start = response.find("{")',
    '    end = response.rfind("}") + 1',
    '    if start != -1 and end > start:',
    '        response = response[start:end]',
    '    try:',
    '        return json.loads(response)',
    '    except Exception:',
    '        return {"error": response[:500]}',
    '',
    '',
    'def audit(profile: dict) -> dict:',
    '    import concurrent.futures',
    '',
    '    def call(cat):',
    '        return _audit_single(profile, cat)',
    '',
    '    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:',
    '        f_minor = ex.submit(call, "minor")',
    '        f_major = ex.submit(call, "major")',
    '        minor_r = f_minor.result(timeout=90)',
    '        major_r = f_major.result(timeout=90)',
    '',
    '    return {',
    '        "student": {',
    '            "name": profile.get("student", {}).get("name", ""),',
    '            "id": profile.get("student", {}).get("id", ""),',
    '            "school": profile.get("student", {}).get("school", ""),',
    '            "gpa": profile.get("cumulative", {}).get("gpa"),',
    '        },',
    '        "audit": {',
    '            "major": major_r.get("major", major_r),',
    '            "minor": minor_r.get("minor", minor_r),',
    '        }',
    '    }',
    '',
    '',
    'def audit_to_text(result: dict) -> str:',
    '    if not result or "error" in str(result):',
    '        return "Audit error: " + str(result)',
    '',
    '    s = result.get("student", {})',
    '    a = result.get("audit", {})',
    '    icon_map = {',
    '        "COMPLETE": "DONE",',
    '        "IN_PROGRESS": "IN PROGRESS",',
    '        "MISSING_REQUIREMENTS": "MISSING",',
    '        "SATISFIED": "DONE",',
    '        "MISSING": "MISSING",',
    '        "PARTIAL": "PARTIAL",',
    '    }',
    '',
    '    def get_icon(val):',
    '        return icon_map.get(val, val)',
    '',
    '    lines = [',
    '        "=" * 50,',
    '        "WASHU DEGREE AUDIT",',
    '        "  " + s.get("name", "Student") + " | GPA: " + str(s.get("gpa", "N/A")) + " | " + s.get("school", ""),',
    '        "=" * 50,',
    '    ]',
    '',
    '    for key, label in [("major", "MAJOR"), ("minor", "MINOR")]:',
    '        sec = a.get(key, {})',
    '        if not sec or "error" in sec:',
    '            lines.append("")',
    '            lines.append("[" + label + ": Could not retrieve requirements]")',
    '            continue',
    '        status = get_icon(sec.get("status", ""))',
    '        lines.append("")',
    '        lines.append("[" + status + "] " + sec.get("name", key.upper()))',
    '        lines.append("-" * 40)',
    '        for r in sec.get("requirements", []):',
    '            slot = r.get("slot", "")',
    '            sat = r.get("satisfied_by", "")',
    '            st = get_icon(r.get("status", ""))',
    '            if sat:',
    '                lines.append("  " + st + " " + slot + ": " + sat)',
    '            else:',
    '                lines.append("  " + st + " " + slot)',
    '        for m in sec.get("missing", []):',
    '            lines.append("  MISSING: " + m)',
    '        if "gpa_met" in sec:',
    '            lines.append("  GPA req met: " + str(sec["gpa_met"]))',
    '',
    '    for d in a.get("double_counted", []):',
    '        lines.append("")',
    '        lines.append("  DOUBLE-COUNTED: " + d)',
    '',
    '    return "\\n".join(lines)',
    '',
]

# Combine: lines before audit_prompt_start + new_lines + lines after audit_to_text_end
result_lines = lines[:audit_prompt_start] + new_lines + lines[audit_to_text_end+1:]

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(result_lines))

print(f"Done. Old file: {len(lines)} lines. New file: {len(result_lines)} lines.")
