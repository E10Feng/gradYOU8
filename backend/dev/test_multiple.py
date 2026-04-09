import urllib.request, json

questions = [
    "what are the math requirements for the computational biology major?",
    "what courses are required for the biology major?",
    "how many credits do i need to graduate?",
]

for q in questions:
    data = json.dumps({"question": q}).encode()
    req = urllib.request.Request("http://localhost:8000/chat", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            print(f"Q: {q}")
            print(f"A: {resp.get('answer', '')[:300]}")
            print()
    except Exception as e:
        print(f"Q: {q} -> Error: {e}")
        print()
