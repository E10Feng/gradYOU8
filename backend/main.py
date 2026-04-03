"""
WashU Navigator — FastAPI Backend
RAG-powered degree requirement explorer for WashU undergrads.
Uses E10's vectorless_gemini PageIndex fork for tree-based document retrieval.
"""
import os
import json
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Load env ─────────────────────────────────────────────────────────────────
load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "../data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="WashU Navigator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Import vectorless RAG lib ────────────────────────────────────────────────
import sys
AGENT_PATH = Path(__file__).parent / "libs" / "pageindex_agent"
sys.path.insert(0, str(AGENT_PATH))

from pageindex_agent.page_index import page_index_main
from pageindex_agent.pageindex_config import pageindex_config
from pageindex_agent.utils import ConfigLoader

# ── Models ────────────────────────────────────────────────────────────────────
class IngestRequest(BaseModel):
    pdf_path: Optional[str] = None  # relative to DATA_DIR, or absolute
    force: bool = False

class IngestResponse(BaseModel):
    status: str
    tree_path: str
    num_nodes: int
    elapsed_seconds: float

class QueryRequest(BaseModel):
    question: str
    chat_history: Optional[list[dict]] = None

class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]  # [{page_range: "10-15", title: "...", text: "..."}]
    doc_name: str

class CourseAddRequest(BaseModel):
    course_id: str
    title: str
    credits: int
    semester: str
    grade: Optional[str] = None

class CourseListResponse(BaseModel):
    courses: list[dict]
    requirements: list[dict]
    satisfied: list[str]
    missing: list[dict]

# ── Helpers ─────────────────────────────────────────────────────────────────
def get_tree_path() -> Path:
    return Path(os.getenv("TREE_INDEX_PATH", str(DATA_DIR / "bulletin.tree.json")))

def get_bulletin_pdf() -> Path:
    default = DATA_DIR / "bulletin.pdf"
    return Path(os.getenv("BULLETIN_PDF", str(default)))

def load_tree() -> dict:
    path = get_tree_path()
    if not path.exists():
        raise HTTPException(404, f"Tree index not found at {path}. Run /ingest first.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ── Ingestion ────────────────────────────────────────────────────────────────
def run_ingestion(pdf_path: Path, force: bool) -> dict:
    """Run PageIndex tree generation in a thread pool (blocks I/O, not event loop)."""
    tree_out = get_tree_path()
    if tree_out.exists() and not force:
        with open(tree_out, "r", encoding="utf-8") as f:
            result = json.load(f)
        return {"status": "already_indexed", "tree_path": str(tree_out), "num_nodes": len(result.get("structure", [])), "elapsed_seconds": 0}

    import time
    t0 = time.time()

    config_loader = ConfigLoader()
    opt = config_loader.load({
        "model": getattr(pageindex_config, "PAGEINDEX_MODEL", "gemini-3-flash-preview"),
        "if_add_node_id": "yes",
        "if_add_node_summary": "yes",
        "if_add_doc_description": "yes",
        "if_add_node_text": "yes",
    })

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(page_index_main, str(pdf_path), opt)
        result = future.result(timeout=3600)  # 60 min max

    elapsed = time.time() - t0

    # Save tree
    tree_out.parent.mkdir(parents=True, exist_ok=True)
    with open(tree_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    num_nodes = len(result.get("structure", []))
    return {"status": "indexed", "tree_path": str(tree_out), "num_nodes": num_nodes, "elapsed_seconds": round(elapsed, 1)}

# ── Query (tree-based reasoning retrieval) ───────────────────────────────────
def tree_retrieve(query: str, tree: dict, model: str = "gemini-2.5-flash") -> tuple[str, list[dict]]:
    """
    Given a question and a loaded tree index, use Gemini to reason over
    the tree structure and retrieve the most relevant page ranges.
    Returns (answer, sources).
    """
    from pageindex_agent.utils import ChatGPT_API, extract_json

    # Build a concise tree overview for the LLM to reason over
    def summarize_tree(nodes, depth=0):
        lines = []
        for node in nodes:
            indent = "  " * depth
            title = node.get("title", "")
            start = node.get("start_index", "?")
            end = node.get("end_index", "?")
            summary = node.get("summary", "")[:100]
            lines.append(f"{indent}- [{start}-{end}] {title} {'| ' + summary if summary else ''}")
            if node.get("nodes"):
                lines.extend(summarize_tree(node["nodes"], depth + 1))
        return lines

    tree_overview = "\n".join(summarize_tree(tree.get("structure", [])))
    doc_name = tree.get("doc_name", "WashU Bulletin")

    # Prompt the LLM to pick the right pages
    prompt = f"""You are a WashU degree requirement assistant.
A student asks: "{query}"

Here is the document's table of contents with page ranges and summaries:

{tree_overview}

Your task:
1. Identify which section(s) of the table of contents are most relevant to answering this question.
2. Return the page ranges (start_index and end_index) for those sections as JSON.
3. Also return a brief answer to the question based on what you know about the document structure.

Return JSON in this format:
{{
  "relevant_sections": [
    {{"title": "...", "start_index": N, "end_index": M, "reasoning": "..."}},
    ...
  ],
  "answer": "Your brief answer to the question"
}}

Return ONLY JSON, no extra text."""

    response = ChatGPT_API(model=model, prompt=prompt)
    parsed = extract_json(response)

    sections = parsed.get("relevant_sections", [])
    answer = parsed.get("answer", "I couldn't find a confident answer in the document.")

    # Retrieve the actual page text for sources
    sources = []
    if sections:
        pdf_path = get_bulletin_pdf()
        if pdf_path.exists():
            try:
                from pageindex_agent.utils import get_text_of_pages
                for sec in sections[:3]:  # top 3 only
                    start = sec.get("start_index", 0)
                    end = sec.get("end_index", start + 1)
                    text = get_text_of_pages(str(pdf_path), start, end, tag=False)
                    sources.append({
                        "title": sec.get("title", ""),
                        "page_range": f"{start}-{end}",
                        "text": text[:500] + "..." if len(text) > 500 else text,
                    })
            except Exception:
                pass

    return answer, sources

# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"app": "WashU Navigator", "version": "0.1.0", "status": "running"}

@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """Ingest (or re-ingest) the WashU bulletin PDF and build the tree index."""
    pdf_path = get_bulletin_pdf()
    if req.pdf_path:
        candidate = DATA_DIR / req.pdf_path
        if candidate.exists():
            pdf_path = candidate

    if not pdf_path.exists():
        raise HTTPException(404, f"PDF not found at {pdf_path}. Upload it to {DATA_DIR} first.")

    # Run blocking ingestion in thread to avoid blocking event loop
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, run_ingestion, pdf_path, req.force)
    except concurrent.futures.TimeoutError:
        raise HTTPException(408, "Ingestion timed out after 60 minutes.")
    except Exception as e:
        raise HTTPException(500, str(e))

    return IngestResponse(**result)

@app.get("/tree")
async def get_tree():
    """Return the raw tree structure (for debugging / frontend nav)."""
    tree = load_tree()
    return {"doc_name": tree.get("doc_name", ""), "doc_description": tree.get("doc_description", ""), "num_nodes": len(tree.get("structure", []))}

@app.post("/chat", response_model=QueryResponse)
async def chat(req: QueryRequest):
    """RAG query against the bulletin using tree-based retrieval."""
    try:
        tree = load_tree()
    except HTTPException:
        raise HTTPException(503, "Document not indexed yet. POST /ingest first.")

    loop = asyncio.get_event_loop()
    answer, sources = await loop.run_in_executor(
        None, tree_retrieve, req.question, tree
    )

    return QueryResponse(
        answer=answer,
        sources=sources,
        doc_name=tree.get("doc_name", "WashU Bulletin"),
    )

# ── Static file serving (for built frontend) ─────────────────────────────────
STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
