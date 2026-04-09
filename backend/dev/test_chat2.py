import urllib.request, json

data = json.dumps({"question": "what are the math requirements for the computational biology major?"}).encode()
req = urllib.request.Request("http://localhost:8000/chat", data=data, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
        print("=== ANSWER ===")
        print(resp.get("answer", ""))
        print("=== SOURCES ===")
        print(json.dumps(resp.get("sources", []), indent=2)[:800])
except Exception as e:
    print("Error:", e)
