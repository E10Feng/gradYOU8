"""Test direct Gemini API call without the google.genai SDK"""
import os, sys
sys.stdout.reconfigure(line_buffering=True)

API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit("Set GOOGLE_API_KEY for Gemini API calls")
import httpx
import json

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
payload = {
    "contents": [{"parts": [{"text": "Reply with just the word 'OK'"}]}],
    "generationConfig": {"temperature": 0}
}

print("Testing direct API...", flush=True)
try:
    resp = httpx.post(url, json=payload, timeout=30.0)
    print(f"Status: {resp.status_code}", flush=True)
    data = resp.json()
    if "error" in data:
        print(f"Error: {data['error']}", flush=True)
    else:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"Response: {text}", flush=True)
except Exception as e:
    print(f"Exception: {e}", flush=True)
