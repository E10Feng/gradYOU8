import sys; sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
import os
os.chdir(r"C:\Users\ethan\.openclaw\workspace\vectorless_gemini")
os.environ["MINIMAX_API_KEY"] = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
os.environ["MINIMAX_MODEL"] = "MiniMax-M2.7"

import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(line_buffering=True)

import PyPDF2
from pageindex_agent.utils import ChatGPT_API, extract_json

pdf_path = r"C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin.pdf"
reader = PyPDF2.PdfReader(pdf_path)

# Test detect_page_index with actual TOC content from page 9
toc_content = reader.pages[9].extract_text()[:3000]  # First 3000 chars
print(f"TOC content length: {len(toc_content)}", flush=True)

prompt = f"""You will be given a table of contents.

Your job is to detect if there are page numbers/indices given within the table of contents.

Given text: {toc_content}

Reply format:
{{
    "thinking": <why do you think there are page numbers/indices given within the table of contents>
    "page_index_given_in_toc": "<yes or no>"
}}
Directly return the final JSON structure. Do not output anything else."""

print("Calling detect_page_index...", flush=True)
response = ChatGPT_API("MiniMax-M2.7", prompt)
print(f"Response ({len(response)} chars): {response[:300]}", flush=True)
parsed = extract_json(response)
print(f"Parsed: {parsed}", flush=True)
