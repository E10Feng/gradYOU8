# BUILD-SPEC: LLM-Driven Hierarchical Tree Navigator v2

## Changes from v1

- Reasoning is **internal only** — never shown to the user
- LLM can **explore multiple branches in parallel** at each level
- Navigator **remembers all explored paths** so it can report what was checked before falling back
- Explorer frontier replaces single current-level state

---

## Core Concept

The navigator maintains a **frontier** of nodes to explore. At each step, the LLM decides which nodes in the frontier to expand. It can explore multiple branches simultaneously. Navigation stops when enough pages have been gathered or the frontier is exhausted.

---

## Data Structures

```python
@dataclass
class NodeRef:
    title: str
    summary: str
    start_index: int
    end_index: int
    children_count: int
    depth: int
    path: list[str]          # breadcrumb e.g. ["Arts & Sciences", "Mathematics", "Mathematics Major"]
    text_preview: str = ""   # first 200 chars if already fetched

@dataclass
class ExploreDecision:
    to_fetch: list[int]      # indices into frontier to fetch pages from
    to_expand: list[int]    # indices into frontier to get children of
    reasoning: str           # INTERNAL ONLY

@dataclass
class NavigationResult:
    nodes_to_fetch: list[NodeRef]  # nodes whose pages should be fetched
    explored_paths: list[NodeRef]   # all nodes that were examined
    did_find: bool                   # whether relevant content was found
```

---

## Tree Navigator

### `navigate_tree(query, tree, model, max_steps=5, max_parallel=3) -> NavigationResult`

```
FRONTIER = [NodeRef(title="Root", summary="WashU Bulletin", children=root_nodes, depth=0, path=[])]
EXPLORED = []
NODES_TO_FETCH = []

for step in range(max_steps):
    # Ask LLM to decide what to do with current frontier
    decision = LLM.decide(query, FRONTIER)

    if decision.to_fetch:
        # Mark these nodes for page fetching
        for idx in decision.to_fetch:
            NODES_TO_FETCH.append(FRONTIER[idx])
            EXPLORED.append(FRONTIER[idx])

    if decision.to_expand:
        NEW_FRONTIER = []
        for idx in decision.to_expand:
            node = FRONTIER[idx]
            if node.children_count > 0:
                # Fetch children of this node (but don't recurse into LLM again this step)
                for child in get_children(node):
                    child.path = node.path + [node.title]
                    NEW_FRONTIER.append(child)
                    EXPLORED.append(child)
            elif node.children_count == 0:
                # Leaf — fetch its pages directly
                NODES_TO_FETCH.append(node)
        FRONTIER = NEW_FRONTIER
    else:
        # Nothing left to explore
        break

return NavigationResult(nodes_to_fetch=NODES_TO_FETCH, explored_paths=EXPLORED, did_find=bool(NODES_TO_FETCH))
```

### LLM Decision Prompt (per step)

```
You are navigating the WashU Undergraduate Bulletin to answer a student question.

Student question: "{query}"

You have a frontier of document sections. For each, you see:
- its title, summary, page range, and number of child sections
- the path in the tree you've already traversed to reach it

Your task: decide which sections to FETCH (get their PDF pages) and which to EXPAND (look at their children).

Rules:
- If a section's summary directly answers the question → FETCH it
- If a section seems related but might not fully answer → EXPAND it (look at children)
- If a section is clearly irrelevant → skip it
- You may FETCH and EXPAND multiple sections in one step
- Be concise — prefer sections with higher information density

Return JSON:
{{
  "to_fetch": [index, ...],     # indices of sections to fetch (their pages will be retrieved)
  "to_expand": [index, ...],    # indices of sections to expand (their children become new frontier)
  "reasoning": "..."            # internal note — never shown to user
}}
"""

### Sections Block Format (per frontier item, with index)

```
Frontier item 0:
  Title: [65-68] Majors (all schools)
  Summary: Alphabetical listing of all undergraduate majors across schools.
  Children: 0
  Path: Root

Frontier item 1:
  Title: [170-180] Department of Mathematics
  Summary: Mathematics department programs, faculty, course listings, and contact info.
  Children: 4
  Path: Root → Arts & Sciences

Frontier item 2:
  Title: [181-195] Department of Economics
  Summary: Economics department programs, major and minor requirements, faculty.
  Children: 5
  Path: Root → Arts & Sciences
```

### Answer Generation

After navigation, pages are fetched for all `nodes_to_fetch`. All fetched text is fed to the answer LLM:

```
You are a WashU degree requirement assistant.
Answer based ONLY on the provided bulletin content.
Be specific with course numbers and unit counts.

Student question: "{query}"

Content:
{fetched_pages_text}

Answer:"""

---

## Integration with Program Indexer

```
Query
  │
  ├─ program_indexer finds canonical name
  │    └─ direct tree lookup → fetch pages [SKIP NAVIGATOR — fast path]
  │
  └─ no canonical match
       └─ navigate_tree() [slow path — for policy queries, ambiguous cases]
```

### Integration in `tree_retrieve()`

```python
def tree_retrieve(query, tree, model="MiniMax-M2.7"):
    # Step 0: Try program indexer first (instant, no LLM)
    canonical = extract_programs_from_query(query)
    if canonical:
        node = get_program_section(canonical[0], tree)
        if node:
            pages_text = fetch_pages(node)
            return generate_answer(query, pages_text), [node]

    # Step 1: Navigate the tree (LLM-guided)
    result = navigate_tree(query, tree, model)

    if not result.nodes_to_fetch:
        # Navigator found nothing — fall back to keyword search
        sections = keyword_tree_search(query, tree)
        if sections:
            pages_text = fetch_pages_from_sections(sections[:3])
            return generate_answer(query, pages_text), sections
        return "I couldn't find information about that in the WashU Bulletin.", []

    # Step 2: Fetch pages and generate answer
    pages_text = fetch_pages(result.nodes_to_fetch)
    return generate_answer(query, pages_text), result.nodes_to_fetch
```

---

## Quality & Safety

1. **max_steps = 5**: Prevents runaway exploration
2. **max_parallel = 3**: LLM can explore up to 3 branches per step, keeps context manageable
3. **Explored paths always returned**: Even if navigation fails, the user sees which sections were checked (for transparency)
4. **Fallback chain**: navigator fails → keyword search → direct LLM (no retrieval)
5. **Stop on sufficient coverage**: If 3+ pages have been gathered and they're likely to answer the question, stop early

---

## Files

```
backend/services/tree_navigator.py   # NEW — TreeNavigator, navigate_tree(), _build_node_ref()
```

---

## Testing Plan

### Fast-path queries (program indexer, skip navigation):
- "math major requirements" → Mathematics Major [712-714]
- "biology major with genomics specialization" → correct specialization node
- "computer science minor" → Computer Science Minor

### Navigator-only queries (no canonical program):
- "can I double-count courses between major and minor?"
- "what is the pass/fail policy?"
- "how many credits to graduate?"
- "double major in math and economics"

### Parallel exploration test:
- "what courses are required for the computer science major?" — should explore CS node and fetch relevant pages
- "tell me about research opportunities in biology" — should expand multiple biology specialization nodes

### Fallback test:
- "asldkfjalsdkfj" (gibberish) → navigator returns nothing → keyword fallback → keyword returns nothing → "I couldn't find..."
