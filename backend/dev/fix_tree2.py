with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "rb") as f:
    content = f.read()

# Fix get_tree_path to prefer bulletin_full.tree.json
old1 = (
    b"def get_tree_path() -> Path:\r\n"
    b"    return Path(os.getenv(\"TREE_INDEX_PATH\", str(DATA_DIR / \"bulletin.tree.json\")))\r\n"
)

new1 = (
    b"def get_tree_path() -> Path:\r\n"
    b"    # Prefer full merged tree (all schools) over single-school stub\r\n"
    b"    full = DATA_DIR / \"bulletin_full.tree.json\"\r\n"
    b"    if full.exists():\r\n"
    b"        return full\r\n"
    b"    return Path(os.getenv(\"TREE_INDEX_PATH\", str(DATA_DIR / \"bulletin.tree.json\")))\r\n"
)

if old1 in content:
    content = content.replace(old1, new1)
    print("1. get_tree_path fixed")
else:
    print("WARNING: get_tree_path pattern not found")

# Fix load_tree to handle list format
old2 = (
    b"def load_tree() -> dict:\r\n"
    b"    path = get_tree_path()\r\n"
    b"    if not path.exists():\r\n"
    b"        raise HTTPException(404, f\"Tree index not found at {path}. Run /ingest first.\")\r\n"
    b"    with open(path, \"r\", encoding=\"utf-8\") as f:\r\n"
    b"        return json.load(f)\r\n"
)

new2 = (
    b"def load_tree() -> dict:\r\n"
    b"    path = get_tree_path()\r\n"
    b"    if not path.exists():\r\n"
    b"        raise HTTPException(404, f\"Tree index not found at {path}. Run /ingest first.\")\r\n"
    b"    with open(path, \"r\", encoding=\"utf-8\") as f:\r\n"
    b"        tree = json.load(f)\r\n"
    b"    # bulletin_full.tree.json is a list of school roots; wrap in dict format\r\n"
    b"    if isinstance(tree, list):\r\n"
    b"        return {\"structure\": tree, \"doc_name\": \"WashU Bulletin (Full)\"}\r\n"
    b"    return tree\r\n"
)

if old2 in content:
    content = content.replace(old2, new2)
    print("2. load_tree fixed")
else:
    print("WARNING: load_tree pattern not found")

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py", "wb") as f:
    f.write(content)
print("Done")
