import json

d = json.load(open(r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini\workspace\bulletin.tree.json", encoding="utf-8"))

print("=== TREE VALIDATION ===")
print("Top-level sections:", len(d["structure"]))
print()

for i, s in enumerate(d["structure"]):
    title = s.get("title", "MISSING")
    node_id = s.get("node_id", "MISSING")
    start = s.get("start_index", "MISSING")
    end = s.get("end_index", "MISSING")
    text_len = len(s.get("text", ""))
    summary_len = len(s.get("summary", ""))
    num_children = len(s.get("nodes", []))
    
    print(f"[{i}] title: {title}")
    print(f"    node_id: {node_id}, start: {start}, end: {end}")
    print(f"    text length: {text_len}, summary length: {summary_len}")
    print(f"    children: {num_children}")
    
    missing = [k for k in ("title", "node_id", "start_index", "end_index") if k not in s]
    if missing:
        print(f"    *** MISSING FIELDS: {missing}")
    print()
    
    # Validate children
    for j, child in enumerate(s.get("nodes", [])):
        c_title = child.get("title", "MISSING")
        c_start = child.get("start_index", "MISSING")
        c_end = child.get("end_index", "MISSING")
        c_id = child.get("node_id", "MISSING")
        print(f"    [{j}] {c_title} | id={c_id} | pages {c_start}-{c_end}")
        c_missing = [k for k in ("title", "node_id", "start_index", "end_index") if k not in child]
        if c_missing:
            print(f"        *** MISSING: {c_missing}")

print("\n=== VALIDATION COMPLETE ===")
