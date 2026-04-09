# gradYOU8: Full Agentic Tree Traversal Loop

## Goal
Replace the current hybrid keyword+LLM approach with a full agentic loop matching PageIndex's recommended approach.

## Current State (hybrid keyword + single-shot LLM)
- `tree_retrieve` in `backend/main.py` uses keyword search first (deterministic)
- Falls back to single-shot LLM routing (inconsistent)
- Then reads pages and generates answer

## Desired State (full agentic loop)
The LLM calls tools iteratively:

**Step 1**: Call `get_document_structure()` → get the tree overview  
**Step 2**: LLM reasons: "I need to find Area B of the Biology Major. The Biology Major is on pages 338-340. Let me narrow to pages 338-340."  
**Step 3**: Call `get_page_content(pages="338-342")` → read those pages  
**Step 4**: Generate answer from page text

## Implementation Plan

### New function: `agentic_retrieve(query, tree, model)`
1. System prompt: "You are a WashU degree requirement assistant. You have access to two tools: `get_document_structure()` returns the table of contents with page ranges. `get_page_content(pages)` returns the text content of specified pages. Answer based ONLY on tool output."
2. First LLM call: instruct it to call `get_document_structure()` first to explore the tree
3. Parse the tool call from the response
4. Return the structure to the LLM in the next turn
5. Second LLM call: based on structure, call `get_page_content(pages)` with tight ranges
6. Parse the tool call, get page content
7. Third LLM call: generate answer from page content

### Tool definitions for MiniMax
The `ChatGPT_API` function needs to support a `tools` parameter. Check if MiniMax API supports function calling (it does via the OpenAI-compatible endpoint).

### Key files to modify
- `backend/main.py`: add `agentic_retrieve` function, update `/chat` route to use it
- The existing `tree_retrieve` can be kept as fallback

### MiniMax function calling
MiniMax supports function calling via the standard tools parameter in the OpenAI-compatible API. Pass tools as:
```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_document_structure",
            "description": "Returns the document's table of contents with page ranges and section titles.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "get_page_content",
            "description": "Returns the text content of specified PDF pages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pages": {"type": "string", "description": "Page range as 'start-end', e.g. '338-342'"}
                },
                "required": ["pages"]
            }
        }
    }
]
```

### Constraint
- The tool calling loop should max out at 3 LLM turns (structure → pages → answer)
- If tool calling isn't supported by MiniMax-M2.7, fall back to the current hybrid approach
- Don't add new dependencies

### Test queries
- "what are all the courses that satisfy the area B component of the biology major"
- "what are the math requirements for the computational biology major"
- "list the upper level bio electives for computational biology"
