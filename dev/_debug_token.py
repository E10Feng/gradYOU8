import json, os

auth_path = r"C:\Users\ethan\.openclaw\agents\main\agent\auth-profiles.json"
with open(auth_path) as f:
    profiles = json.load(f)

for name, cfg in profiles.items():
    if "minimax" in name.lower():
        token = cfg.get("access", "")
        print(f"Profile: {name}")
        print(f"Token prefix: {token[:25]}...")
        print(f"Token length: {len(token)}")
        break

# Write to temp file so we can see the exact token
with open(r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\_debug_token.txt", "w") as f:
    f.write(token)