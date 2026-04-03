"""
Minimix-compatible utility module for WashU Navigator (gradYOU8).

Replaces the original google.genai-based LLM calls with direct httpx calls
to the Minimix OpenAI-compatible API (https://api.minimax.chat/v1).

Environment variables required:
    MINIMAX_API_KEY   — your Minimimax API key
    MINIMAX_GROUP_ID   — your Minimax group ID
    MINIMAX_MODEL      — model name (default: MiniMax-M2.7)

All LLM call signatures (ChatGPT_API, ChatGPT_API_async,
ChatGPT_API_with_finish_reason) are preserved so PageIndex call sites
work without modification.
"""

from __future__ import annotations

import logging
import os
import re
import json
import copy
import asyncio
import concurrent.futures
import queue as queue_module
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import httpx

logger = logging.getLogger(__name__)

# ── Minimix API config ────────────────────────────────────────────────────────

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"

# ── HTTP client ───────────────────────────────────────────────────────────────

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=MINIMAX_BASE_URL,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=30.0),
        )
    return _client


def _reset_client() -> None:
    global _client
    if _client:
        _client.close()
    _client = None


# ── Token counting ───────────────────────────────────────────────────────────

def count_tokens(text: str, model: str | None = None) -> int:
    """Character-based approximation: ~4 chars per token."""
    if not text:
        return 0
    return len(text) // 4


# ── LLM wrappers ─────────────────────────────────────────────────────────────

_CALL_TIMEOUT = 300


def _call_with_timeout(fn, *args, **kwargs):
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(fn, *args, **kwargs)
    try:
        return fut.result(timeout=_CALL_TIMEOUT)
    except concurrent.futures.TimeoutError:
        _reset_client()
        ex.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError(f"LLM call timed out after {_CALL_TIMEOUT}s")
    except Exception:
        ex.shutdown(wait=False)
        raise
    finally:
        ex.shutdown(wait=False)


def _minimax_build_messages(prompt: str, chat_history: list | None = None) -> list[dict]:
    messages = []
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": prompt})
    return messages


def _parse_sse_stream(response: httpx.Response) -> tuple[str, str | None]:
    """Parse SSE stream from Minimix. OpenAI-compatible format."""
    text_parts = []
    finish_reason = None
    for line in response.iter_lines():
        if not line.strip() or not line.startswith("data: "):
            continue
        data_str = line[len("data: "):]
        if data_str.strip() == "[DONE]":
            break
        try:
            data = json.loads(data_str)
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                if delta.get("content"):
                    text_parts.append(delta["content"])
                finish = choices[0].get("finish_reason")
                if finish:
                    finish_reason = finish
        except json.JSONDecodeError:
            continue
    return "".join(text_parts), finish_reason


def _call_minimax_stream(
    model: str,
    prompt: str,
    chat_history: list | None = None,
    temperature: float = 0.0,
    max_retries: int = 10,
) -> tuple[str, str]:
    messages = _minimax_build_messages(prompt, chat_history)
    for attempt in range(max_retries):
        try:
            client = _get_client()
            with client.stream(
                "POST", "/chat/completions",
                json={
                    "model": model or MINIMAX_MODEL,
                    "messages": messages,
                    "stream": True,
                    "temperature": temperature,
                },
            ) as response:
                response.raise_for_status()
                return _parse_sse_stream(response)
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.error("Retry %d/%d — connection error: %s", attempt + 1, max_retries, e)
            _reset_client()
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return "Error", "error"
        except Exception as e:
            logger.error("Retry %d/%d — error: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return "Error", "error"
    return "Error", "error"


async def _call_minimax_async(
    model: str,
    prompt: str,
    temperature: float = 0.0,
    max_retries: int = 10,
) -> str:
    messages = _minimax_build_messages(prompt, None)
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(
                base_url=MINIMAX_BASE_URL,
                headers={"Authorization": f"Bearer {MINIMAX_API_KEY}", "Content-Type": "application/json"},
                timeout=httpx.Timeout(60.0, connect=30.0),
            ) as client:
                response = await asyncio.wait_for(
                    client.post("/chat/completions", json={
                        "model": model or MINIMAX_MODEL,
                        "messages": messages,
                        "stream": False,
                        "temperature": temperature,
                    }),
                    timeout=_CALL_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
        except (asyncio.TimeoutError, httpx.TimeoutException, httpx.ConnectError) as e:
            logger.error("Retry %d/%d — connection error: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return "Error"
        except Exception as e:
            logger.error("Retry %d/%d — error: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return "Error"
    return "Error"


# ── Public API ────────────────────────────────────────────────────────────────

def ChatGPT_API_with_finish_reason(model, prompt, api_key=None, chat_history=None):
    text, reason = _call_minimax_stream(model, prompt, chat_history, temperature=0.0)
    return text, reason


def ChatGPT_API(model, prompt, api_key=None, chat_history=None):
    text, _ = _call_minimax_stream(model, prompt, chat_history, temperature=0.0)
    return text


async def ChatGPT_API_async(model, prompt, api_key=None):
    return await _call_minimax_async(model, prompt, temperature=0.0)


# ── JSON helpers ─────────────────────────────────────────────────────────────

def get_json_content(response: str) -> str:
    start_idx = response.find("```json")
    if start_idx != -1:
        start_idx += 7
        response = response[start_idx:]
    end_idx = response.rfind("```")
    if end_idx != -1:
        response = response[:end_idx]
    return response.strip()


def extract_json(content: str) -> dict | list:
    try:
        start_idx = content.find("```json")
        if start_idx != -1:
            start_idx += 7
            end_idx = content.rfind("```")
            json_content = content[start_idx:end_idx].strip()
        else:
            json_content = content.strip()
        json_content = json_content.replace("None", "null").replace("\n", " ").replace("\r", " ")
        json_content = " ".join(json_content.split())
        return json.loads(json_content)
    except json.JSONDecodeError:
        try:
            return json.loads(json_content.replace(",]", "]").replace(",}", "}"))
        except Exception:
            logger.error("Failed to parse JSON")
            return {}
    except Exception as e:
        logger.error("Unexpected error extracting JSON: %s", e)
        return {}


# ── Tree helpers ─────────────────────────────────────────────────────────────

def write_node_id(data, node_id=0):
    if isinstance(data, dict):
        data["node_id"] = str(node_id).zfill(4)
        node_id += 1
        for key in list(data.keys()):
            if "nodes" in key:
                node_id = write_node_id(data[key], node_id)
    elif isinstance(data, list):
        for index in range(len(data)):
            node_id = write_node_id(data[index], node_id)
    return node_id


def get_nodes(structure):
    if isinstance(structure, dict):
        sn = copy.deepcopy(structure)
        sn.pop("nodes", None)
        nodes = [sn]
        for key in list(structure.keys()):
            if "nodes" in key:
                nodes.extend(get_nodes(structure[key]))
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nodes.extend(get_nodes(item))
        return nodes


def structure_to_list(structure):
    if isinstance(structure, dict):
        nodes = [structure]
        if "nodes" in structure:
            nodes.extend(structure_to_list(structure["nodes"]))
        return nodes
    elif isinstance(structure, list):
        nodes = []
        for item in structure:
            nodes.extend(structure_to_list(item))
        return nodes


def get_leaf_nodes(structure):
    if isinstance(structure, dict):
        if not structure.get("nodes"):
            sn = copy.deepcopy(structure)
            sn.pop("nodes", None)
            return [sn]
        leaf_nodes = []
        for key in list(structure.keys()):
            if "nodes" in key:
                leaf_nodes.extend(get_leaf_nodes(structure[key]))
        return leaf_nodes
    elif isinstance(structure, list):
        leaf_nodes = []
        for item in structure:
            leaf_nodes.extend(get_leaf_nodes(item))
        return leaf_nodes


def is_leaf_node(data, node_id):
    def find_node(data, node_id):
        if isinstance(data, dict):
            if data.get("node_id") == node_id:
                return data
            for key in data.keys():
                if "nodes" in key:
                    result = find_node(data[key], node_id)
                    if result:
                        return result
        elif isinstance(data, list):
            for item in data:
                result = find_node(item, node_id)
                if result:
                    return result
        return None
    node = find_node(data, node_id)
    return bool(node and not node.get("nodes"))


def get_last_node(structure):
    return structure[-1]


# ── PDF helpers ──────────────────────────────────────────────────────────────

import PyPDF2
import pymupdf


def extract_text_from_pdf(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    return "".join(page.extract_text() for page in pdf_reader.pages)


def get_pdf_title(pdf_path):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    meta = pdf_reader.metadata
    return (meta.title if meta and meta.title else "Untitled") if meta else "Untitled"


def get_text_of_pages(pdf_path, start_page, end_page, tag=True):
    pdf_reader = PyPDF2.PdfReader(pdf_path)
    text = ""
    for page_num in range(start_page - 1, end_page):
        page_text = pdf_reader.pages[page_num].extract_text()
        if tag:
            text += f"<start_index_{page_num+1}>\n{page_text}\n<end_index_{page_num+1}>\n"
        else:
            text += page_text
    return text


def get_first_start_page_from_text(text):
    m = re.search(r"<start_index_(\d+)>", text)
    return int(m.group(1)) if m else -1


def get_last_start_page_from_text(text):
    matches = list(re.finditer(r"<start_index_(\d+)>", text))
    return int(matches[-1].group(1)) if matches else -1


def sanitize_filename(filename, replacement="-"):
    return filename.replace("/", replacement)


def get_pdf_name(pdf_path):
    if isinstance(pdf_path, str):
        return sanitize_filename(os.path.basename(pdf_path))
    elif isinstance(pdf_path, BytesIO):
        pdf_reader = PyPDF2.PdfReader(pdf_path)
        meta = pdf_reader.metadata
        return sanitize_filename(meta.title if meta and meta.title else "Untitled")
    return "Untitled"


class JsonLogger:
    def __init__(self, file_path):
        self.filename = f"{get_pdf_name(file_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("./logs", exist_ok=True)
        self.log_data = []

    def log(self, level, message, **kwargs):
        pylog = logging.getLogger("pageindex_agent")
        if isinstance(message, dict):
            pylog.info(f"[{self.filename}] {level}: {json.dumps(message, default=str)}")
        else:
            pylog.info(f"[{self.filename}] {level}: {message}")
        self.log_data.append(message if isinstance(message, dict) else {"message": message})
        with open(self._filepath(), "w") as f:
            json.dump(self.log_data, f, indent=2)

    def info(self, message, **kwargs):
        self.log("INFO", message)
    def error(self, message, **kwargs):
        self.log("ERROR", message)
    def debug(self, message, **kwargs):
        self.log("DEBUG", message)
    def exception(self, message, **kwargs):
        self.log("ERROR", message)
    def _filepath(self):
        return os.path.join("logs", self.filename)


# ── Tree conversion ───────────────────────────────────────────────────────────

def list_to_tree(data):
    def get_parent(structure):
        if not structure:
            return None
        parts = str(structure).split(".")
        return ".".join(parts[:-1]) if len(parts) > 1 else None

    nodes = {}
    root_nodes = []

    for item in data:
        structure = item.get("structure")
        node = {"title": item.get("title"), "start_index": item.get("start_index"),
                "end_index": item.get("end_index"), "nodes": []}
        nodes[structure] = node
        parent = get_parent(structure)
        if parent and parent in nodes:
            nodes[parent]["nodes"].append(node)
        elif parent:
            root_nodes.append(node)
        else:
            root_nodes.append(node)

    def clean(node):
        if not node["nodes"]:
            del node["nodes"]
        else:
            for child in node["nodes"]:
                clean(child)
        return node

    return [clean(n) for n in root_nodes]


def add_preface_if_needed(data):
    if not isinstance(data, list) or not data:
        return data
    if data[0].get("physical_index", 0) and data[0]["physical_index"] > 1:
        data.insert(0, {"structure": "0", "title": "Preface", "physical_index": 1})
    return data


def get_page_tokens(pdf_path, model=None, pdf_parser="PyMuPDF"):
    if pdf_parser == "PyPDF2":
        pdf_reader = PyPDF2.PdfReader(pdf_path)
        return [(p.extract_text(), count_tokens(p.extract_text(), model)) for p in pdf_reader.pages]
    elif pdf_parser == "PyMuPDF":
        doc = pymupdf.open(pdf_path) if isinstance(pdf_path, str) else pymupdf.open(stream=pdf_path, filetype="pdf")
        return [(p.get_text(), count_tokens(p.get_text(), model)) for p in doc]
    raise ValueError(f"Unsupported parser: {pdf_parser}")


def get_text_of_pdf_pages(pdf_pages, start_page, end_page):
    return "".join(pdf_pages[i][0] for i in range(start_page - 1, end_page))


def get_text_of_pdf_pages_with_labels(pdf_pages, start_page, end_page):
    text = ""
    for i in range(start_page - 1, end_page):
        text += f"<physical_index_{i+1}>\n{pdf_pages[i][0]}\n<physical_index_{i+1}>\n"
    return text


def get_number_of_pages(pdf_path):
    return len(PyPDF2.PdfReader(pdf_path).pages)


# ── Post-processing helpers ──────────────────────────────────────────────────

def post_processing(structure, end_physical_index):
    for i, item in enumerate(structure):
        item["start_index"] = item.get("physical_index")
        if i < len(structure) - 1:
            item["end_index"] = (structure[i + 1]["physical_index"] - 1
                                 if structure[i + 1].get("appear_start") == "yes"
                                 else structure[i + 1]["physical_index"])
        else:
            item["end_index"] = end_physical_index
    tree = list_to_tree(structure)
    if len(tree) != 0:
        return tree
    for node in structure:
        node.pop("appear_start", None)
        node.pop("physical_index", None)
    return structure


def clean_structure_post(data):
    if isinstance(data, dict):
        for k in ["page_number", "start_index", "end_index"]:
            data.pop(k, None)
        if "nodes" in data:
            clean_structure_post(data["nodes"])
    elif isinstance(data, list):
        for section in data:
            clean_structure_post(section)
    return data


def remove_fields(data, fields=None):
    if fields is None:
        fields = ["text"]
    if isinstance(data, dict):
        return {k: remove_fields(v, fields) for k, v in data.items() if k not in fields}
    elif isinstance(data, list):
        return [remove_fields(item, fields) for item in data]
    return data


def print_toc(tree, indent=0):
    for node in tree:
        print("  " * indent + node["title"])
        if node.get("nodes"):
            print_toc(node["nodes"], indent + 1)


def print_json(data, max_len=40, indent=2):
    def simp(obj):
        if isinstance(obj, dict):
            return {k: simp(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [simp(i) for i in obj]
        elif isinstance(obj, str) and len(obj) > max_len:
            return obj[:max_len] + "..."
        return obj
    print(json.dumps(simp(data), indent=indent, ensure_ascii=False))


def remove_structure_text(data):
    if isinstance(data, dict):
        data.pop("text", None)
        if "nodes" in data:
            remove_structure_text(data["nodes"])
    elif isinstance(data, list):
        for item in data:
            remove_structure_text(item)
    return data


def check_token_limit(structure, limit=110000):
    for node in structure_to_list(structure):
        n = count_tokens(node["text"])
        if n > limit:
            print(f"Node {node.get('node_id')} has {n} tokens (limit {limit})")


def convert_physical_index_to_int(data):
    if isinstance(data, list):
        for i in range(len(data)):
            val = data[i].get("physical_index") if isinstance(data[i], dict) else None
            if isinstance(val, str):
                for marker in ("<physical_index_", "physical_index_"):
                    if marker in val:
                        start = val.find(marker) + len(marker)
                        end = val.rfind(">") if ">" in val else len(val)
                        try:
                            data[i]["physical_index"] = int(val[start:end].strip())
                        except ValueError:
                            pass
    return data


def convert_page_to_int(data):
    for item in data:
        if isinstance(item.get("page"), str):
            try:
                item["page"] = int(item["page"])
            except ValueError:
                pass
    return data


def add_node_text(node, pdf_pages):
    if isinstance(node, dict):
        node["text"] = get_text_of_pdf_pages(pdf_pages, node.get("start_index", 1), node.get("end_index", 1))
        if "nodes" in node:
            add_node_text(node["nodes"], pdf_pages)
    elif isinstance(node, list):
        for item in node:
            add_node_text(item, pdf_pages)


def add_node_text_with_labels(node, pdf_pages):
    if isinstance(node, dict):
        node["text"] = get_text_of_pdf_pages_with_labels(pdf_pages, node.get("start_index", 1), node.get("end_index", 1))
        if "nodes" in node:
            add_node_text_with_labels(node["nodes"], pdf_pages)
    elif isinstance(node, list):
        for item in node:
            add_node_text_with_labels(item, pdf_pages)


async def generate_node_summary(node, model=None):
    prompt = (
        "You are given a part of a document. Generate a brief 1-2 sentence description "
        "of the main topics covered.\n\nPartial Document Text: " + node["text"] + "\n\nDescription:"
    )
    return await ChatGPT_API_async(model, prompt)


async def generate_summaries_for_structure(structure, model=None):
    _log = logging.getLogger("pageindex_agent")
    nodes = structure_to_list(structure)
    _log.info(f"Generating summaries for {len(nodes)} nodes...")
    sem = asyncio.Semaphore(5)
    async def bounded(n):
        async with sem:
            return await generate_node_summary(n, model=model)
    summaries = await asyncio.gather(*[bounded(n) for n in nodes])
    for node, summary in zip(nodes, summaries):
        node["summary"] = summary
    _log.info(f"All {len(nodes)} summaries generated.")
    return structure


def create_clean_structure_for_description(structure):
    if isinstance(structure, dict):
        cn = {k: structure[k] for k in ["title", "node_id", "summary", "prefix_summary"] if k in structure}
        if structure.get("nodes"):
            cn["nodes"] = create_clean_structure_for_description(structure["nodes"])
        return cn
    elif isinstance(structure, list):
        return [create_clean_structure_for_description(s) for s in structure]
    return structure


def generate_doc_description(structure, model=None):
    prompt = (
        "Generate a one-sentence description of a document that helps distinguish it "
        "from other documents.\n\nDocument Structure: " + str(structure) + "\n\nDescription:"
    )
    return ChatGPT_API(model, prompt)


def reorder_dict(data, key_order):
    return {key: data[key] for key in key_order if key in data}


def format_structure(structure, order=None):
    if not order:
        return structure
    if isinstance(structure, dict):
        if "nodes" in structure:
            structure["nodes"] = format_structure(structure["nodes"], order)
            if not structure["nodes"]:
                structure.pop("nodes", None)
        structure = reorder_dict(structure, order)
    elif isinstance(structure, list):
        structure = [format_structure(s, order) for s in structure]
    return structure


# ── Config loader ─────────────────────────────────────────────────────────────

import yaml


class ConfigLoader:
    def __init__(self, default_path: str | None = None):
        if default_path is None:
            default_path = Path(__file__).parent / "config.yaml"
        self._default_dict = self._load_yaml(default_path)

    @staticmethod
    def _load_yaml(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _validate_keys(self, user_dict):
        unknown = set(user_dict) - set(self._default_dict)
        if unknown:
            raise ValueError(f"Unknown config keys: {unknown}")

    def load(self, user_opt=None):
        from types import SimpleNamespace
        if user_opt is None:
            user_dict = {}
        elif hasattr(user_opt, "__dict__"):
            user_dict = vars(user_opt)
        elif isinstance(user_opt, dict):
            user_dict = user_opt
        else:
            raise TypeError("user_opt must be dict, config, or None")
        self._validate_keys(user_dict)
        return SimpleNamespace(**{**self._default_dict, **user_dict})
