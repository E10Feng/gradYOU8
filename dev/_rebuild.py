"""Rebuild run_llm_scored_rag.py from clean components."""
import os

# ── Section 1: imports and globals
S1 = '''\
import json, os, re, urllib.request, urllib.error
import concurrent.futures

TREE_PATH    = r"C:\\Users\\ethan\\.openclaw\\workspace\\builds\\washu-navigator\\data\\bulletin_full.json"
OUT_PATH     = r"C:\\Users\\ethan\\.openclaw\\workspace\\builds\\washu-navigator\\data\\rag_answer.json"
PROFILE_PATH = r"C:\\Users\\ethan\\.openclaw\\workspace\\builds\\washu-navigator\\data\\student_profile.json"
MAX_ITERS = 3

with open(TREE_PATH, encoding="utf-8") as f:
    _tree = json.load(f)

flat = []
def _flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get("nodes"):
            _flatten(n["nodes"])
_flatten(_tree)

id_to_node = {n["node_id"]: n for n in flat}
all_nodes = flat
print(f"Loaded {len(all_nodes)} nodes")

def get_token():
    auth_path = r"C:\\Users\\ethan\\.openclaw\\agents\\main\\agent\\auth-profiles.json"
    with open(auth_path) as f:
        profiles = json.load(f)
    for name, cfg in profiles.get("profiles", profiles).items():
        if "minimax" in name.lower():
            return cfg.get("access", "")
    return ""

def minimax(messages, max_tokens=8000):
    token = get_token()
    payload = json.dumps({
        "model": "MiniMax-M2.7",
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": messages
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.minimax.io/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]

'''

# ── Section 2: anchor nodes
S2 = '''\
ANCHOR_NODES = {
    "cs_minor":     ["0649", "0657"],
    "cs_major":     ["0648", "0643", "0644", "0645"],
    "bioinformatics": ["0257"],
    "overlap_rules": ["0189", "0101"],
}

SPECIALIZATION_ANCHORS = {
    "computational biology":              "0252",
    "genomics and computational":        "0252",
    "ecology and evolution":            "0251",
    "microbiology":                      "0253",
    "molecular biology and biochemistry":"0254",
    "neuroscience":                     "0255",
    "environmental biology":             "0256",
    "general biology":                  "0250",
}

def get_anchor_ids(question):
    q = question.lower()
    anchors = []
    def add(ids):
        for aid in ids:
            if aid not in anchors:
                anchors.append(aid)
    for kw, nid in SPECIALIZATION_ANCHORS.items():
        if kw in q:
            add([nid])
            break
    if "minor" in q and any(w in q for w in ["cs ", "cse ", "computer science", "csminor"]):
        add(ANCHOR_NODES["cs_minor"])
    if "minor" in q:
        add(ANCHOR_NODES["cs_minor"])
        add(ANCHOR_NODES["bioinformatics"])
    if any(w in q for w in ["computer science", "cse ", "cs major", "cs/minor"]):
        add(ANCHOR_NODES["cs_major"])
    if any(w in q for w in ["double", "overlap", "count"]):
        add(ANCHOR_NODES["overlap_rules"])
    return anchors

'''

# ── Section 3: node_summary
S3 = '''\
def node_summary(n, max_chars=None):
    title = n.get("title", "")
    summary = n.get("summary", "")
    text = n.get("text", "")
    nid = n.get("node_id", "")
    if nid in ("0252", "0649", "0257") and text:
        content = text
    elif summary:
        content = summary
    elif text:
        content = text[:max_chars] if max_chars else text
    else:
        content = ""
    return f"[{nid}] {title}\\n{content}"

def build_context(nodes):
    return "\\n\\n".join(node_summary(n) for n in nodes)

'''

# ── Section 4: student profile
S4 = '''\
def load_student_profile():
    if not os.path.exists(PROFILE_PATH):
        return None
    with open(PROFILE_PATH) as f:
        return json.load(f)

def build_profile_context(profile):
    lines = []
    for sem in profile.get("semesters", []):
        term = sem.get("term", "")
        gpa = sem.get("gpa")
        codes = [f"{c[\'code\']} ({c[\'grade\']})" for c in sem.get("courses", [])]
        lines.append(f"  {term} [{gpa}]: " + ", ".join(codes))
    cum = profile.get("cumulative", {})
    ctx = (
        f"STUDENT: {profile.get(\'student\', {}).get(\'name\', \'Unknown\')} - "
        f"{profile.get(\'student\', {}).get(\'school\', '')}\\n"
        f"Programs: " + ", ".join(p[\'name\'] for p in profile.get("programs", [])) + "\\n"
        f"Cumulative GPA: {cum.get(\'gpa\', \'N/A\')} | "
        f"Credits earned: {cum.get(\'credits_earned\', \'N/A\')}\\n"
        + "\\nCourses taken:\\n" + "\\n".join(lines)
    )
    return ctx

'''

# ── Section 5: system prompt
S5 = '''\
SYSTEM_PROMPT_BASE = (
    "You are a WashU academic advisor. Answer questions using ONLY the bulletin context provided.\\n"
    "CRITICAL - before answering, explicitly identify:\\n"
    "  1. The specific MAJOR and SPECIALIZATION (if any) - and which SCHOOL it belongs to (e.g., Arts & Sciences, Engineering).\\n"
    "  2. The specific MINOR (if any) - and which SCHOOL it belongs to.\\n"
    "  3. Whether the question involves a COMBINATION across schools (e.g., Biology major in Arts & Sciences + Computer Science minor in the Engineering school - this is allowed and common at WashU).\\n"
    "HOW TO ANSWER:\\n"
    "  1. Use ONLY the sections provided that are directly relevant.\\n"
    "  2. If a course or requirement is mentioned in one section but not described in another, state only what the context shows.\\n"
    "  3. If the sections do NOT contain enough to fully answer, say exactly: NEED_MORE_INFO: <specific missing topic>\\n"
    "Do NOT make up information not in the provided context."
)

def get_system_prompt(profile=None):
    prompt = SYSTEM_PROMPT_BASE
    if profile:
        prompt += "\\n\\n" + build_profile_context(profile)
    return prompt

'''

# ── Section 6: selector
S6 = '''\
SELECTOR_PROMPT = (
    "Select the {k} most relevant bulletin sections for answering this question: {question}\\n"
    "Return ONLY a JSON array of node IDs, e.g. [\\\"0252\\\", \\\"0649\\\"]\\n"
    "Node list:\\n{node_list}"
)

def node_key(n):
    return f'[{n.get("node_id","?")}] {n.get("title","")} | {n.get("summary","") or n.get("text","")[:200]}'

def build_node_list(nodes):
    return "\\n".join(node_key(n) for n in nodes)

def select_nodes(question, k=8):
    anchors = get_anchor_ids(question)
    anchor_nodes = [id_to_node[aid] for aid in anchors if aid in id_to_node]
    remaining = max(0, k - len(anchor_nodes))
    if remaining == 0:
        return anchor_nodes[:k]
    non_anchor_ids = set(id_to_node.keys()) - set(anchors)
    non_anchor_deduped = []
    seen = set()
    for nid in non_anchor_ids:
        n = id_to_node[nid]
        if nid not in seen:
            seen.add(nid)
            non_anchor_deduped.append(n)
    node_list = build_node_list(non_anchor_deduped)
    anchor_list = ", ".join(f\'"{aid}"\' for aid in anchors if aid in id_to_node)
    selector_sys = (
        f"You are a helpful assistant that selects relevant bulletin sections.\\n"
        f"ALREADY SELECTED (will be included automatically): [{anchor_list}]\\n"
        f"Select {remaining} ADDITIONAL sections most relevant to the question below."
    )
    prompt = SELECTOR_PROMPT.format(k=remaining, question=question, node_list=node_list)
    messages = [
        {"role": "system", "content": selector_sys},
        {"role": "user", "content": prompt}
    ]
    response = minimax(messages, max_tokens=600)
    try:
        start = response.find("[")
        end = response.rfind("]") + 1
        if start != -1 and end > start:
            ids = json.loads(response[start:end])
            selected = [id_to_node.get(uid) for uid in ids if uid in id_to_node]
            combined = anchor_nodes + [n for n in selected if n]
            return combined[:k]
    except:
        pass
    return anchor_nodes[:k]

'''

# ── Section 7: run_query and run_agentic
S7 = '''\
def run_query(question, profile=None):
    selected = select_nodes(question, k=8)
    if not selected:
        return None, "No relevant sections found.", []
    ctx = build_context(selected)
    print(f"\\n--- {len(selected)} nodes selected: ---")
    for n in selected:
        print(f"  [{n.get(\'node_id\',\'?\')}] {n.get(\'title\',\'\')[:65]}")
    messages = [
        {"role": "system", "content": get_system_prompt(profile)},
        {"role": "user", "content": f"Bulletin sections:\\n{ctx}\\n\\nQuestion: {question}"}
    ]
    answer = minimax(messages, max_tokens=4000)
    print(f"\\n--- Answer ---\\n{answer[:300]}")
    need_more = None
    if "NEED_MORE_INFO:" in answer:
        need_more = answer.split("NEED_MORE_INFO:")[1].split("\\n")[0].strip()
        print(f"\\n--- Need more: {need_more} ---")
    return answer, need_more, selected

def run_agentic(question, profile=None, save=True):
    print(f"\\n{\'=\'*60}\\nLLM-SCORED RAG - {question}\\n{\'=\'*60}")
    answer, need_more, _ = run_query(question, profile)
    if not answer:
        return answer
    iteration = 2
    while need_more and iteration <= MAX_ITERS:
        more = select_nodes(need_more, k=6)
        if not more:
            print(f"\\n--- Could not find: {need_more} ---")
            break
        print(f"\\n--- Pass {iteration}: {len(more)} nodes for \'{need_more}\' ---")
        for n in more:
            print(f"  [{n.get(\'node_id\',\'?\')}] {n.get(\'title\',\'\')[:65]}")
        ctx = build_context(more)
        messages = [
            {"role": "system", "content": get_system_prompt(profile)},
            {"role": "user", "content": f"Bulletin sections:\\n{ctx}\\n\\nQuestion: {question}"}
        ]
        answer = minimax(messages, max_tokens=4000)
        print(f"\\n--- Answer ---\\n{answer[:300]}")
        if "NEED_MORE_INFO:" in answer:
            need_more = answer.split("NEED_MORE_INFO:")[1].split("\\n")[0].strip()
        else:
            need_more = None
        iteration += 1
    try:
        print(f"\\n{\'=\'*60}\\nFINAL:\\n{answer}")
    except UnicodeEncodeError:
        print(f"\\n{\'=\'*60}\\nFINAL:\\n[Unicode - see rag_answer.json]")
    if save:
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump({"query": question, "answer": answer}, f, indent=2, ensure_ascii=False)
    return answer

'''

# ── Section 8: audit
S8 = '''\
def _audit_single(profile, category):
    student_ctx = build_profile_context(profile)

    def get_nodes(ids):
        nodes = [id_to_node[a] for a in ids if a in id_to_node]
        return build_context(nodes)

    system_msg = "You are a WashU degree audit system. Return ONLY valid JSON. No explanation, no markdown, no thinking tags."

    if category == "minor":
        ctx = get_nodes(["0649", "0101"])
        user = (
            "STUDENT PROFILE:\\n" + student_ctx + "\\n\\n"
            "BULLETIN SECTIONS:\\n" + ctx + "\\n\\n"
            "TASK: Audit the Computer Science Minor (CSE, Engineering school).\\n"
            "Course equivalencies: CSE-E81 131 = CSE 1301, CSE-E81 247 = CSE 2407, CSE-E81 132 = CSE 1302.\\n"
            "For each required core course (CSE 1301, CSE 1302, CSE 2407, CSE 3302), "
            "state whether student has taken it and with what grade.\\n"
            "List elective options and which one (if any) student has taken.\\n"
            "Note any courses that double-count with the major.\\n"
            \'Return ONLY this JSON:\\n\'
            \'{"minor": {"name": "Computer Science Minor (CSE)", \'
            \'"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", \'
            \'"requirements": [{"course": "CSE 1301", "taken": true, "grade": "A"}], \'
            \'"missing": [], "double_counted": []}}\'
        )
    else:
        ctx = get_nodes(["0252", "0101", "0189"])
        user = (
            "STUDENT PROFILE:\\n" + student_ctx + "\\n\\n"
            "BULLETIN SECTIONS:\\n" + ctx + "\\n\\n"
            "TASK: Audit the Biology Major with Genomics and Computational Biology (Arts & Sciences).\\n"
            "List each required course group: Biology core, Chemistry, Physics, Math, advanced biology, outside electives.\\n"
            "For each group: which courses student has taken and grade received.\\n"
            "Outside electives CSE 1301 and CSE 2407 are required for this specialization.\\n"
            "Note GPA requirement: C- or better in all major courses.\\n"
            \'Return ONLY this JSON:\\n\'
            \'{"major": {"name": "Biology Major, Genomics and Computational Biology", \'
            \'"status": "COMPLETE|IN_PROGRESS|MISSING_REQUIREMENTS", \'
            \'"requirements": [], "missing": [], "gpa_met": true}}\'
        )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user}
    ]
    response = minimax(messages, max_tokens=8000)
    response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
    start = response.find("{")
    end = response.rfind("}") + 1
    if start != -1 and end > start:
        response = response[start:end]
    try:
        return json.loads(response)
    except Exception:
        return {"error": response[:500]}


def audit(profile):
    minor_r = _audit_single(profile, "minor")
    major_r = _audit_single(profile, "major")
    return {
        "student": {
            "name": profile.get("student", {}).get("name", ""),
            "id": profile.get("student", {}).get("id", ""),
            "school": profile.get("student", {}).get("school", ""),
            "gpa": profile.get("cumulative", {}).get("gpa"),
        },
        "audit": {
            "major": major_r.get("major", major_r),
            "minor": minor_r.get("minor", minor_r),
        }
    }


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
        True: "DONE",
        False: "NOT DONE",
    }

    def get_icon(val):
        return icon_map.get(val, str(val))

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
            # Handle multiple schemas: {course, taken, grade} or {slot, satisfied_by, status}
            course = r.get("course") or r.get("slot", "")
            taken = r.get("taken")
            grade = r.get("grade", "")
            status_val = r.get("status")
            equiv = r.get("equivalent", "")
            note = r.get("note", "")

            if taken is True:
                extra = " (" + grade + ")" if grade else ""
                if equiv:
                    extra += " = " + equiv
                if note:
                    extra += " | " + note
                lines.append("    DONE  " + course + extra)
            elif taken is False:
                lines.append("    NOT TAKEN: " + course)
            else:
                st = get_icon(status_val) if status_val else ""
                lines.append("    " + st + " " + course)

        for m in sec.get("missing", []):
            lines.append("    MISSING: " + str(m))

        if "gpa_met" in sec:
            lines.append("    GPA req met: " + str(sec["gpa_met"]))

    dbl = a.get("double_counted", [])
    if dbl:
        lines.append("")
        lines.append("  DOUBLE-COUNTED:")
        for d in dbl:
            lines.append("    " + str(d))

    return "\\n".join(lines)

'''

# ── Section 9: handlers and main
S9 = '''\
def answer_with_profile(question):
    profile = load_student_profile()
    return run_agentic(question, profile)


def handle_transcript_upload(pdf_path):
    from transcript_to_json import parse_and_save
    profile = parse_and_save(pdf_path)
    sem_count = len(profile.get("semesters", []))
    total_courses = sum(len(s["courses"]) for s in profile["semesters"])
    total_creds = sum(c["credits"] for s in profile["semesters"] for c in s["courses"])
    cum = profile.get("cumulative", {})
    programs = "; ".join(p["name"] for p in profile.get("programs", []))
    return (
        f"Transcript parsed successfully!\\n\\n"
        f"Student: {profile[\'student\'][\'name\']} ({profile[\'student\'][\'id\']})\\n"
        f"School: {profile[\'student\'][\'school\']}\\n"
        f"Programs: {programs}\\n"
        f"Semesters: {sem_count} | Courses: {total_courses} | Credits: {total_creds}\\n"
        f"Cumulative GPA: {cum.get(\'gpa\', \'N/A\')}\\n\\n"
        f"You can now ask me things like:\\n"
        f"- Which courses do I still need for the CS minor?\\n"
        f"- Am I missing any requirements for the comp bio specialization?\\n"
        f"- /audit to see your full degree audit"
    )


if __name__ == "__main__":
    import sys
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What are the requirements for the Biology major?"
    print(f"Total nodes: {len(all_nodes)}")
    profile = load_student_profile()
    if profile:
        print(f"Profile loaded: {profile.get(\'student\',{}).get(\'name\',\'\')} ({len(profile.get(\'semesters\',[]))} semesters)")
    else:
        print("No student profile found.")
    result = run_agentic(question, profile, save=True)
    print(f"\\nSaved to {OUT_PATH}")
'''

# ── Write the combined file
output = S1 + S2 + S3 + S4 + S5 + S6 + S7 + S8 + S9
output = output.replace("\\\\", "\\")  # fix double backslashes

with open(r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\run_llm_scored_rag.py", "w", encoding="utf-8") as f:
    f.write(output)

print(f"Written {len(output)} chars, {len(output.splitlines())} lines")
