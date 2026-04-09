with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'def get_tree_path() -> Path:\n    return Path(os.getenv("TREE_INDEX_PATH", str(DATA_DIR / "bulletin.tree.json")))\n\ndef load_tree() -> dict:\n    path = get_tree_path()\n    if not path.exists():\n        raise HTTPException(404, f"Tree index not found at {path}. Run /ingest first.")\n    with open(path, "r", encoding="utf-8") as f:\n        return json.load(f)'

new = 'def get_tree_path() -> Path:\n    # Prefer the full merged tree (all schools), fall back to single-file index\n    full = DATA_DIR / "bulletin_full.tree.json"\n    if full.exists():\n        return full\n    return Path(os.getenv("TREE_INDEX_PATH", str(DATA_DIR / "bulletin.tree.json")))\n\ndef load_tree() -> dict:\n    path = get_tree_path()\n    if not path.exists():\n        raise HTTPException(404, f"Tree index not found at {path}. Run /ingest first.")\n    with open(path, "r", encoding="utf-8") as f:\n        tree = json.load(f)\n    # bulletin_full.tree.json is a list of school roots; wrap in dict format\n    if isinstance(tree, list):\n        return {"structure": tree, "doc_name": "WashU Bulletin (Full)"}\n    return tree'

if old in content:
    content = content.replace(old, new)
    print("Fixed load_tree")
else:
    print("WARNING: old block not found")

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)
print("Done")
