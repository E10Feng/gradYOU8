import sys
import os
import urllib.request
import json

backend = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend"
sys.path.insert(0, backend)
os.chdir(backend)

from dotenv import load_dotenv
load_dotenv()

from services.tree_router import _get_api_key
token = _get_api_key()

candidate_titles = [
    "Biology Major",
    "Biology Minor",
    "Chemistry Major",
    "Advanced Topics in Anthropology",
    "Biology Course Offerings",
]

title_block = "\n".join("- " + t for t in candidate_titles)
query = "what are the core classes for the bio major?"
select_prompt = (
    "A student asks: " + query + "\n\n"
    "Here are section titles from the WashU bulletin:\n\n"
    + title_block + "\n\n"
    "Which titles are most relevant? Return ONLY valid JSON with key 'titles': [title1, ...]. "
    'Return at most 3. If none match, return {"titles": []}.'
)

payload = json.dumps({
    "model": "MiniMax-M2.7",
    "messages": [{"role": "user", "content": select_prompt}],
    "max_tokens": 8000,
}).encode()

req = urllib.request.Request(
    "https://api.minimax.io/v1/chat/completions",
    data=payload,
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=60) as r:
    result = json.loads(r.read())
    raw = result["choices"][0]["message"]["content"]

stripped = raw.replace("<think>", "").replace("</think>", "").strip()

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\full_llm_response.txt", "w", encoding="utf-8") as f:
    f.write("Length: " + str(len(raw)) + "\n")
    f.write("Stripped starts with '{': " + str(stripped.startswith("{")) + "\n")
    f.write("Contains 'trees': " + str('"trees"' in stripped) + "\n")
    f.write("\n--- RAW ---\n")
    f.write(raw)
    f.write("\n\n--- STRIPPED ---\n")
    f.write(stripped)
    f.write("\n")

print("Written. Length:", len(raw))
