import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:8000/chat',
    data=json.dumps({'question': 'what are the upper level bio elective requirements for the computational biology major'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=60)
    resp = json.loads(r.read().decode())
    answer = resp.get('answer', '')
    print(f"Answer: {answer[:500]}")
    print(f"\nSources: {[s.get('title','') for s in resp.get('sources',[])]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
