"""
WashU Navigator â€” FastAPI Backend
RAG-powered degree requirement explorer for WashU undergrads.
Uses E10's vectorless_gemini PageIndex fork for tree-based document retrieval.
"""
import os
import re
import json
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Optional, Any

import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# â”€â”€ Load env â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
load_dotenv()

# â”€â”€ Routers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from .routers.requirements import router as requirements_router
from .routers.audit import router as audit_router
from .routers.upload import router as upload_router
from .routers.audit_full import router as audit_full_router
from .routers.feedback import router as feedback_router

DATA_DIR = Path(os.getenv("DATA_DIR", "../data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# â”€â”€ App setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="WashU Navigator API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# â”€â”€ Startup: pre-warm requirements cache â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.on_event("startup")
async def warm_requirements_cache():
    """Startup hook — warm-up disabled for now (single-shot search is fast enough)."""
    pass

# Register routers
app.include_router(requirements_router)
app.include_router(audit_router)
app.include_router(upload_router)
app.include_router(audit_full_router)
app.include_router(feedback_router)

# Student profile state (set by /api/upload-transcript)
app.state.current_profile = None

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Password auth middleware ───────────────────────────────────────────────────
_APP_PASSWORD = os.getenv("APP_PASSWORD", "")

@app.middleware("http")
async def require_password(request: Request, call_next):
    # Always allow health check and OPTIONS (CORS preflight)
    if request.url.path in ("/api/ping", "/api/info") or request.method == "OPTIONS":
        return await call_next(request)
    # Skip auth if no password is configured (dev mode)
    if not _APP_PASSWORD:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {_APP_PASSWORD}":
        return await call_next(request)
    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})




# â”€â”€ Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    profile: Optional[dict] = None  # student profile from upload-transcript

class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]  # [{page_range: "10-15", title: "...", text: "..."}]
    doc_name: str


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _run_chat_query_sync(req: QueryRequest) -> tuple[str, list[dict]]:
    question = req.question
    from .services.agentic_retriever import agentic_retrieve
    result = agentic_retrieve(question, req.profile)
    answer = re.sub(r"<thinking[\s\S]*?</thinking>", "", result.answer, flags=re.IGNORECASE).strip()
    return answer, result.sources

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

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_tree_path() -> Path:
    explicit = os.getenv("TREE_INDEX_PATH")
    if explicit:
        return Path(explicit)
    return DATA_DIR / "bulletin.tree.json"


SPLIT_TREE_FILES: dict[str, dict[str, str]] = {
    "architecture": {"file": "bulletin_architecture.tree.json", "label": "Architecture"},
    "arts_sciences": {"file": "bulletin_arts_sciences.tree.json", "label": "Arts & Sciences"},
    "engineering": {"file": "bulletin_engineering.tree.json", "label": "Engineering"},
    "art": {"file": "bulletin_art.tree.json", "label": "Art"},
    "university": {"file": "bulletin_university.tree.json", "label": "University"},
    "cross_school": {"file": "bulletin_cross_school.tree.json", "label": "Cross School"},
    "business": {"file": "bulletin_business.tree.json", "label": "Business"},
}


def _load_tree_file(path: Path) -> tuple[list[dict], str]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw, ""
    if isinstance(raw, dict):
        return raw.get("structure", []), (raw.get("doc_description", "") or "")
    return [], ""


def _tree_summary(structure: list[dict], doc_description: str = "") -> str:
    titles = []
    snippets = []
    for node in structure[:6]:
        t = (node.get("title") or "").strip()
        s = (node.get("summary") or "").strip().replace("\n", " ")
        if t:
            titles.append(t)
        if s:
            snippets.append(s[:140])
    title_part = "; ".join(titles[:6])
    summary_part = " ".join(snippets[:3])
    base = (doc_description or "").strip().replace("\n", " ")
    return f"{base} Top sections: {title_part}. {summary_part}".strip()


def load_split_tree_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for tree_id, meta in SPLIT_TREE_FILES.items():
        p = DATA_DIR / meta["file"]
        if not p.exists():
            continue
        structure, doc_description = _load_tree_file(p)
        catalog[tree_id] = {
            "tree_id": tree_id,
            "path": p,
            "doc_name": f"WashU Bulletin ({meta['label']})",
            "label": meta["label"],
            "summary": _tree_summary(structure, doc_description),
            "structure": structure,
        }
    return catalog


def build_router_context(catalog: dict[str, dict[str, Any]]) -> str:
    lines = []
    for tree_id, entry in catalog.items():
        lines.append(f"- {tree_id}: {entry.get('summary', '')}")
    return "\n".join(lines)


def _split_tree_paths() -> list[Path]:
    names = [
        "bulletin_architecture.tree.json",
        "bulletin_arts_sciences.tree.json",
        "bulletin_engineering.tree.json",
        "bulletin_art.tree.json",
        "bulletin_university.tree.json",
        "bulletin_cross_school.tree.json",
        "bulletin_business.tree.json",
    ]
    return [DATA_DIR / n for n in names if (DATA_DIR / n).exists()]

def get_bulletin_pdf() -> Path:
    default = DATA_DIR / "bulletin_full.pdf"
    return Path(os.getenv("BULLETIN_PDF", str(default)))

def load_tree() -> dict:
    catalog = load_split_tree_catalog()
    if catalog:
        merged_structure: list[dict] = []
        for entry in catalog.values():
            merged_structure.extend(entry.get("structure", []))
        return {
            "structure": merged_structure,
            "doc_name": "WashU Bulletin (Split Trees)",
        }

    full = DATA_DIR / "bulletin_full.tree.json"
    if full.exists():
        with open(full, "r", encoding="utf-8") as f:
            tree = json.load(f)
        if isinstance(tree, list):
            return {"structure": tree, "doc_name": "WashU Bulletin (Full)"}
        return tree

    path = get_tree_path()
    if not path.exists():
        raise HTTPException(404, f"Tree index not found at {path}. Run /ingest first.")
    with open(path, "r", encoding="utf-8") as f:
        tree = json.load(f)
    return tree if isinstance(tree, dict) else {"structure": tree, "doc_name": "WashU Bulletin"}

# â”€â”€ Ingestion â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_ingestion(pdf_path: Path, force: bool) -> dict:
    """Run PageIndex tree generation in a thread pool (blocks I/O, not event loop)."""
    tree_out = get_tree_path()
    if tree_out.exists() and not force:
        with open(tree_out, "r", encoding="utf-8") as f:
            result = json.load(f)
        return {"status": "already_indexed", "tree_path": str(tree_out), "num_nodes": len(result.get("structure", [])), "elapsed_seconds": 0}

    import time
    _agent_lib = Path(__file__).parent / "libs" / "pageindex_agent"
    _agent_pkg = _agent_lib / "pageindex_agent"
    sys.path.insert(0, str(_agent_lib))
    sys.path.insert(0, str(_agent_pkg))
    from page_index import page_index_main
    from pageindex_config import pageindex_config
    from utils import ConfigLoader

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

# Legacy retrieval functions removed.
# All retrieval now goes through services.agentic_retriever
# (PageIndex-style single-shot tree search).

# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/info")
async def root():
    return {"app": "WashU Navigator", "version": "0.1.0", "status": "running"}



@app.get("/api/ping")
async def ping():
    """Public liveness probe (no auth required)."""
    return {"ok": True}


@app.get("/api/health")
async def health():
    """Health check â€” verifies tree index exists and reports node count."""
    indexed = False
    num_nodes = 0
    try:
        num_nodes = len(load_tree().get("structure", []))
        indexed = num_nodes > 0
    except Exception:
        indexed = False
    return {
        "status": "ok",
        "db": True,  # no real DB yet
        "tree_indexed": indexed,
        "tree_nodes": num_nodes,
    }

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
@limiter.limit("10/minute")
async def chat(req: QueryRequest, request: Request):
    """RAG query against the bulletin using tree-based retrieval."""
    try:
        tree = load_tree()
    except HTTPException:
        raise HTTPException(503, "Document not indexed yet. POST /ingest first.")

    try:
        loop = asyncio.get_event_loop()
        answer, sources = await loop.run_in_executor(None, lambda: _run_chat_query_sync(req))
    except Exception as e:
        import traceback
        traceback.print_exc()
        answer = (
            "I had trouble finding that information. "
            "Please try rephrasing your question or try again shortly."
        )
        sources = []
        print(f"[chat] retrieval_error type={type(e).__name__} error={e}")

    return QueryResponse(
        answer=answer,
        sources=sources,
        doc_name=tree.get("doc_name", "WashU Bulletin"),
    )


@app.post("/chat/stream")
@limiter.limit("10/minute")
async def chat_stream(req: QueryRequest, request: Request):
    """SSE stream for chat progress + incremental answer text."""
    try:
        tree = load_tree()
    except HTTPException:
        raise HTTPException(503, "Document not indexed yet. POST /ingest first.")

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, lambda: _run_chat_query_sync(req))

    async def event_stream():
        status_plan = [
            (0.0, "Identifying the program from your question..."),
            (1.5, "Searching the bulletin for relevant sections..."),
            (5.0, "Generating your personalized answer..."),
        ]
        emitted = 0
        t0 = asyncio.get_event_loop().time()

        while not future.done():
            elapsed = asyncio.get_event_loop().time() - t0
            while emitted < len(status_plan) and elapsed >= status_plan[emitted][0]:
                yield _sse("status", {"message": status_plan[emitted][1]})
                emitted += 1
            await asyncio.sleep(0.2)

        try:
            answer, sources = future.result()
        except Exception as e:
            yield _sse("error", {"message": f"Chat failed: {type(e).__name__}"})
            yield _sse("done", {"ok": False})
            return

        yield _sse("sources", {"sources": sources, "doc_name": tree.get("doc_name", "WashU Bulletin")})
        chunk_size = 48
        for i in range(0, len(answer), chunk_size):
            yield _sse("answer_delta", {"text": answer[i:i + chunk_size]})
            await asyncio.sleep(0.012)

        yield _sse("done", {"ok": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# â”€â”€ Static file serving (for built frontend) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file_path = (STATIC_DIR / path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
