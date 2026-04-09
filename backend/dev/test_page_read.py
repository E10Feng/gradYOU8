import urllib.request, json

questions = [
    "what are the course requirements for upper level bio classes for the computational biology major?",
    "what are the math requirements for the computational biology major?",
    "how many credits of upper level biology are required for the biology major?",
]

for q in questions:
    data = json.dumps({"question": q}).encode()
    req = urllib.request.Request("http://localhost:8000/chat", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
            print(f"Q: {q}")
            print(f"A: {resp.get('answer', '')[:400]}")
            print(f"Sources: {[s.get('page_range') for s in resp.get('sources', [])]}")
            print()
    except Exception as e:
        print(f"Q: {q} -> Error: {e}")
        print()
