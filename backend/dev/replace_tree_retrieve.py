import subprocess, os

py = r"C:\Users\ethan\AppData\Local\Programs\Python\Python311\python.exe"
main_py = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main.py"
new_func_file = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\main_new.py"

with open(main_py, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

func_start = content.find("# ── Query (tree-based reasoning retrieval)")
func_end = content.find("\n# ── Routes ──")
if func_start < 0 or func_end < 0:
    print(f"ERROR: couldn't find function boundaries (start={func_start}, end={func_end})")
    exit(1)

print(f"Old function: {func_end - func_start} chars")

with open(new_func_file, "r", encoding="utf-8", errors="ignore") as f:
    new_func = f.read()

# Add import re at module level if not present
if "import re" not in content:
    content = content.replace("import os\n", "import os\nimport re\n", 1)
    print("Added 'import re'")

# Replace the function
content = content[:func_start] + new_func + content[func_end:]

with open(main_py, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)

print(f"New content: {len(content)} chars")

result = subprocess.run([py, "-m", "py_compile", main_py], capture_output=True, text=True)
if result.returncode == 0:
    print("OK - compiles cleanly")
else:
    print("COMPILE ERROR:")
    print(result.stderr.decode())
