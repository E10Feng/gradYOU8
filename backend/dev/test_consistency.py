import urllib.request, json

question = "what are all the courses that satisfy the area B component of the biology major"
url = "http://localhost:8000/chat"

for i in range(3):
    data = json.dumps({"question": question}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
        sources = resp.get("sources", [])
        page_ranges = [s.get("page_range") for s in sources]
        answer_preview = resp.get("answer", "")[:100].replace("\n", " ")
        print(f"Run {i+1}: pages={page_ranges} | {answer_preview}")
