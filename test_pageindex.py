"""
test_pageindex.py — Test PageIndex against the WashU Biology Bulletin PDF
Run: python test_pageindex.py
"""
import sys
import json
import asyncio
import concurrent.futures
from pathlib import Path

# ── CONFIG ───────────────────────────────────────────────────────────────────
PDF_PATH = Path(__file__).parent / "test_biology_bulletin.pdf"
WORKSPACE = Path(__file__).parent / "workspace"
OPENAI_API_KEY = None  # Set your key here, or set OPENAI_API_KEY env var

# ── TEST QUERIES ─────────────────────────────────────────────────────────────
TEST_QUERIES = [
    "What are the required courses for the Biology major?",
    "What gateway courses do I need for the Biology major?",
    "Can BIOL 296 count toward the natural science distribution requirement?",
    "What are the different Biology major specializations?",
    "What is the grade requirement for Biology major courses?",
    "How many units do I need total for the Biology major?",
    "What courses satisfy the upper-level requirements for the Biology major?",
]

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """You are PageIndex, a document QA assistant for the WashU Undergraduate Bulletin.
TOOL USE:
- Call get_document() first to confirm status and page/line count.
- Call get_document_structure() to identify relevant page ranges for the question.
- Call get_page_content(pages="X-Y") with tight ranges; never fetch the whole document.
- Before each tool call, output one short sentence explaining the reason.
Answer based only on tool output. Be concise. If the answer is in a table, summarize the table rows clearly."""


def main():
    from pageindex import PageIndexClient
    import pageindex.utils as utils
    from openai import OpenAI

    # ── Setup ────────────────────────────────────────────────────────────────
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        print("Download the bulletin PDF and save it as test_biology_bulletin.pdf")
        sys.exit(1)

    if OPENAI_API_KEY:
        client = PageIndexClient(workspace=WORKSPACE, openai_api_key=OPENAI_API_KEY)
    else:
        client = PageIndexClient(workspace=WORKSPACE)

    # ── Index ───────────────────────────────────────────────────────────────
    print(f"\nIndexing: {PDF_PATH.name}")
    doc_id = None
    for did, doc in client.documents.items():
        if doc.get("doc_name") == PDF_PATH.name:
            doc_id = did
            break

    if doc_id:
        print(f"Using cached doc_id: {doc_id}")
    else:
        doc_id = client.index(PDF_PATH)
        print(f"Indexed. doc_id: {doc_id}")

    # ── Show structure ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("TREE STRUCTURE (top-level sections)")
    print("=" * 70)
    structure = json.loads(client.get_document_structure(doc_id))
    utils.print_tree(structure)

    # ── Show metadata ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("DOCUMENT METADATA")
    print("=" * 70)
    print(client.get_document(doc_id))

    # ── Run queries ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RAG QUERY RESULTS")
    print("=" * 70)

    for i, question in enumerate(TEST_QUERIES, 1):
        print(f"\n{'─' * 70}")
        print(f"QUERY {i}: {question}")
        print(f"{'─' * 70}")
        result = query_agent(client, doc_id, question, verbose=True)
        print(f"\nANSWER: {result}")


def query_agent(client, doc_id: str, prompt: str, verbose: bool = True) -> str:
    """Run a document QA agent. Streams text and returns full answer."""
    import requests



    # ── Define agent tools ──────────────────────────────────────────────────
    def get_document() -> str:
        """Get document metadata: status, page count, name, and description."""
        return client.get_document(doc_id)

    def get_document_structure() -> str:
        """Get the document's full tree structure (without text) to find relevant sections."""
        return client.get_document_structure(doc_id)

    def get_page_content(pages: str) -> str:
        """
        Get the text content of specific pages or line numbers.
        Use tight ranges: e.g. '5-7' for pages 5 to 7, '3,8' for pages 3 and 8, '12' for page 12.
        """
        return client.get_page_content(doc_id, pages)

    tools = [
        get_document,
        get_document_structure,
        get_page_content,
    ]
    tool_map = {t.__name__: t for t in tools}

    # ── Simple tool-calling loop ────────────────────────────────────────────
    # PageIndex doesn't require OpenAI Agents SDK — use the client directly
    # with a simple ReAct-style loop
    api_key = None
    try:
        api_key = __import__("os").environ.get("OPENAI_API_KEY")
    except Exception:
        pass

    if not api_key:
        # Try to load from environment
        import os
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("WARNING: OPENAI_API_KEY not set. Set it as environment variable.")
        print("  Windows (PowerShell): $env:OPENAI_API_KEY='sk-...'\n")
        return "[SKIPPED — no OpenAI API key]"

    from openai import OpenAI
    openai = OpenAI(api_key=api_key)

    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    max_turns = 10
    for turn in range(max_turns):
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_document",
                        "description": "Get document metadata: status, page count, name, and description.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_document_structure",
                        "description": "Get the document's full tree structure (without text) to find relevant sections.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_page_content",
                        "description": "Get the text content of specific pages or line numbers. Use tight ranges.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "pages": {
                                    "type": "string",
                                    "description": "Page range, e.g. '5-7' or '3,8' or '12'",
                                }
                            },
                            "required": ["pages"],
                        },
                    },
                },
            ],
            tool_choice="auto",
            temperature=0,
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            # Final answer
            return msg.content or ""

        # Execute tool calls
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            args = json.loads(tc.function.arguments)
            if fn_name in tool_map:
                result = tool_map[fn_name](**args)
                if verbose:
                    print(f"\n[tool: {fn_name}] pages={args.get('pages', 'N/A')} → {result[:300]}...")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            else:
                print(f"\nUnknown tool: {fn_name}")

    return "[Max turns exceeded]"


if __name__ == "__main__":
    main()
