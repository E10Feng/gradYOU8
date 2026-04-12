import requests
import json

BASE = "http://localhost:8001"

# Load student profile
with open("../../data/student_profile.json") as f:
    profile = json.load(f)

courses = []
for sem in profile.get("semesters", []):
    for course in sem.get("courses", []):
        courses.append({
            "id": course.get("code", ""),
            "title": course.get("title", ""),
            "credits": course.get("credits", 0),
            "grade": course.get("grade", ""),
        })

print(f"Loaded {len(courses)} courses from student profile")

programs = [
    {"name": "GCB Major", "type": "major", "school": "arts-sciences"},
    {"name": "Computer Science Minor", "type": "minor", "school": "engineering"},
]

payload = {"programs": programs, "courses": courses, "debug": True}

print("\nCalling /api/audit-full for GCB only...")
resp = requests.post(f"{BASE}/api/audit-full", json=payload, timeout=180)
print(f"Status: {resp.status_code}")

data = resp.json()

for audit_data in data.get("audits", []):
    print(f"\n{'='*60}")
    print(f"Program: {audit_data.get('program')} ({audit_data.get('school')})")
    print(f"Mode: {audit_data.get('audit_mode')}")
    print(f"Overall: {audit_data.get('overall_percent')}%")
    for g in audit_data.get("groups", []):
        print(f"  [{g.get('status', '?')}] {g.get('name', '?')} ({g.get('percent', 0)}%)  {g.get('credit_progress', '')}")
        for s in g.get("satisfied", []):
            print(f"    ✓ {s}")
        for r in g.get("remaining", []):
            print(f"    ✗ {r}")
        details = g.get("satisfied_details", [])
        if details:
            print(f"    satisfied_details ({len(details)}):")
            for d in details:
                print(f"      {d}")

