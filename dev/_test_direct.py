import urllib.request, json

token = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
messages = [
    {"role": "system", "content": "You are a WashU academic advisor. Answer using the context."},
    {"role": "user", "content": "Context: CS minor requires CSE 131, CSE 240, 2 upper CSE courses. CSE 1301 and CSE 2407 are outside electives. Biology Genomics and Computational Biology requires CSE 1301 and CSE 2407 as outside electives. Question: Do CSE 1301 and CSE 2407 double count for both the computational biology major and CS minor?"}
]
payload = json.dumps({"model": "MiniMax-M2.7", "max_tokens": 500, "messages": messages}).encode()
req = urllib.request.Request(
    "https://api.minimax.io/v1/chat/completions",
    data=payload,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print("SUCCESS:", result["choices"][0]["message"]["content"][:300])
except Exception as e:
    print("ERROR:", e)