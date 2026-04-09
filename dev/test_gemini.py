import os, sys
sys.stdout.reconfigure(line_buffering=True)
if not os.environ.get("GOOGLE_API_KEY"):
    raise SystemExit("Set GOOGLE_API_KEY for Gemini API calls")

import google.genai as genai
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# Try different models
models_to_test = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-1.5-flash",
    "gemini-1.5-flash-002",
    "gemini-1.5-pro",
]

for model in models_to_test:
    print(f"Testing {model}...", end=" ", flush=True)
    try:
        response = client.models.generate_content(
            model=model,
            contents="Reply with just the word 'OK'",
        )
        print(f"OK - {repr(response.text.strip())}", flush=True)
    except Exception as e:
        err = str(e)
        if "NOT_FOUND" in err or "unsupported" in err.lower():
            print(f"NOT FOUND", flush=True)
        else:
            print(f"ERROR: {err[:100]}", flush=True)
