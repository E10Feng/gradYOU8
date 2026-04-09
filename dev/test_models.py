import os
os.environ["MINIMAX_API_KEY"] = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"

import httpx
import json

API_KEY = os.environ["MINIMAX_API_KEY"]
BASE_URL = "https://api.minimax.io/v1"

prompt = "Return JSON: {\"test\": \"hello\"}. Output only JSON."

# Test models that are non-reasoning / fast
models = [
    "abab6.5s",
    "abab6.5",
    "abab5.5s",
    "abab5.5",
    "abab5s",
    "abab5",
    "minimax-i2",
    "minimax-i1",
]

for model in models:
    try:
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15.0) as client:
            resp = client.post("/chat/completions", json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 200
            })
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                thinking = content.startswith("<think>")
                print(f"{model}: OK, thinking={thinking}, len={len(content)}, content={repr(content[:80])}", flush=True)
            else:
                print(f"{model}: HTTP {resp.status_code} - {resp.text[:100]}", flush=True)
    except Exception as e:
        print(f"{model}: ERROR - {e}", flush=True)
