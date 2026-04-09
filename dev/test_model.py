import sys; sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
import os
os.environ["MINIMAX_API_KEY"] = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
os.environ["MINIMAX_MODEL"] = "MiniMax-M2.7"

import httpx
import json
import re

API_KEY = os.environ["MINIMAX_API_KEY"]
MODEL = os.environ["MINIMAX_MODEL"]
BASE_URL = "https://api.minimax.io/v1"

def extract_json_from_response(content: str):
    """Extract JSON from MiniMax response — handles thinking tags and post-thinking JSON."""
    # First, strip thinking tags
    stripped = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    stripped = stripped.strip()
    
    # If stripped content starts with JSON, parse it
    if stripped.startswith("["):
        try:
            return json.loads(stripped)
        except:
            pass
    
    # Otherwise look for JSON array anywhere in the original content (after last </think>)
    last_thinking_end = content.rfind("</think>")
    if last_thinking_end != -1:
        after_thinking = content[last_thinking_end + len("</think>"):].strip()
        if after_thinking.startswith("["):
            try:
                return json.loads(after_thinking)
            except:
                pass
    
    # Fallback: find first complete JSON array
    json_arrays = re.findall(r'\[[\s\S]*?\]', content)
    for arr in json_arrays:
        try:
            parsed = json.loads(arr)
            if isinstance(parsed, list):
                return parsed
        except:
            continue
    
    return None

# Test with the actual long prompt (simulate generate_toc_init)
prompt_base = """You are an expert in extracting hierarchical tree structure, your task is to generate the tree structure of the document.

The structure variable is the numeric system which represents the index of the hierarchy section in the table of contents. For example, the first section has structure index 1, the first subsection has structure index 1.1, the second subsection has structure index 1.2, etc.

For the title, you need to extract the original title from the text, only fix the space inconsistency.

The provided text contains tags like <physical_index_X> and <physical_index_X> to indicate the start and end of page X. 

For the physical_index, you need to extract the physical index of the start of the section from the text. Keep the <physical_index_X> format.

The response should be in the following format. 
    [
        {{
            "structure": <structure index, "x.x.x"> (string),
            "title": <title of the section, keep the original title>,
            "physical_index": "<physical_index_X> (keep the format)"
        }},
    ],

Directly return the final JSON structure. Do not output anything else."""

test_text = """Biology (page 315)
Biochemistry (page 320)
Chemistry (page 330)
Physics (page 340)
Mathematics (page 350)"""

full_prompt = prompt_base + "\nGiven text\n:" + test_text
print(f"Prompt length: {len(full_prompt)}", flush=True)

text_parts = []
with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=60.0) as client:
    with client.stream("POST", "/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": full_prompt}], "stream": True, "max_tokens": 3000}) as resp:
        for line in resp.iter_lines():
            if line.strip().startswith("data: ") and line[6:].strip() != "[DONE]":
                try:
                    data = json.loads(line[6:])
                    delta = data["choices"][0].get("delta", {})
                    if delta.get("content"):
                        text_parts.append(delta["content"])
                except:
                    pass

streamed = "".join(text_parts)
print(f"Streamed: {len(streamed)} chars", flush=True)
print(f"Last 300: {repr(streamed[-300:])}", flush=True)

parsed = extract_json_from_response(streamed)
print(f"\nExtracted: {'OK' if parsed else 'FAIL'}", flush=True)
if parsed:
    print(f"Items: {len(parsed)}", flush=True)
    for item in parsed[:3]:
        print(f"  {item}", flush=True)
