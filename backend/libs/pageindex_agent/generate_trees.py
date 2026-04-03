"""
Batch tree generation script for all state guideline PDFs.

Walks workers_comp_state_specific_guidelines/ (14 states, 138 PDFs),
generates a hierarchical tree index for each using PageIndex + Gemini 2.5 Flash,
and saves the results as JSON files under output_pageindex/{state}/{pdf_name}.tree.json.

Usage:
    # Process all PDFs
    python -m pageindex_agent.generate_trees

    # Process a single state
    python -m pageindex_agent.generate_trees --state Colorado

    # Process a single PDF
    python -m pageindex_agent.generate_trees --pdf "workers_comp_state_specific_guidelines/Colorado/Rule_16.pdf"

    # Dry run (list files without processing)
    python -m pageindex_agent.generate_trees --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

from pageindex_agent.pageindex_config import pageindex_config
from pageindex_agent.page_index import page_index_main
from pageindex_agent.utils import ConfigLoader

LOG_FILE = Path("logs/generate_trees.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")

# File handler — writes directly to disk, never blocks on a pipe.
_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setFormatter(_fmt)

_handlers: list[logging.Handler] = [_fh]

# Only add a console handler when running in an interactive terminal.
# In detached/background mode the console pipe buffer fills and deadlocks Python.
if sys.stderr.isatty():
    _ch = logging.StreamHandler(sys.stderr)
    _ch.setFormatter(_fmt)
    _handlers.append(_ch)

logging.basicConfig(level=logging.INFO, handlers=_handlers)
logger = logging.getLogger(__name__)


def discover_pdfs(
    pdf_dir: str,
    state_filter: str | None = None,
) -> list[tuple[str, str]]:
    """Return list of (state, pdf_path) tuples for all PDFs in the directory."""
    results: list[tuple[str, str]] = []
    pdf_root = Path(pdf_dir)

    if not pdf_root.is_dir():
        logger.error("PDF directory not found: %s", pdf_dir)
        return results

    for state_dir in sorted(pdf_root.iterdir()):
        if not state_dir.is_dir():
            continue
        # Skip hidden / special directories
        if state_dir.name.startswith("."):
            continue

        state_name = state_dir.name

        if state_filter and state_name.lower() != state_filter.lower():
            continue

        for pdf_file in sorted(state_dir.glob("*.pdf")):
            results.append((state_name, str(pdf_file)))

    return results


def tree_output_path(output_dir: str, state: str, pdf_path: str) -> str:
    """Compute the output .tree.json path for a given PDF."""
    pdf_name = Path(pdf_path).stem
    state_out_dir = os.path.join(output_dir, state)
    os.makedirs(state_out_dir, exist_ok=True)
    return os.path.join(state_out_dir, f"{pdf_name}.tree.json")


def run_tree_generation(
    pdf_path: str,
    state: str,
    output_dir: str,
    model: str,
    force: bool = False,
    max_time: int = 3600,  # 60 min max per PDF
) -> dict | None:
    """Generate tree for a single PDF.  Returns the tree dict or None on skip/error."""
    out_path = tree_output_path(output_dir, state, pdf_path)

    if os.path.isfile(out_path) and not force:
        logger.info("SKIP  %s  (tree already exists at %s)", pdf_path, out_path)
        return None

    logger.info("PROCESSING  [%s]  %s", state, pdf_path)
    t0 = time.time()

    try:
        config_loader = ConfigLoader()
        opt = config_loader.load({
            "model": model,
            "if_add_node_id": "yes",
            "if_add_node_summary": "yes",
            "if_add_doc_description": "yes",
            "if_add_node_text": "yes",
        })

        # Run in a separate thread with a hard time limit
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(page_index_main, pdf_path, opt)
            try:
                result = future.result(timeout=max_time)
            except concurrent.futures.TimeoutError:
                elapsed = time.time() - t0
                logger.error(
                    "TIMEOUT  [%s]  %s  after %.1fs (limit %ds) — skipping",
                    state, pdf_path, elapsed, max_time,
                )
                return None

        # Add state metadata
        result["state"] = state
        result["source_pdf"] = pdf_path

        elapsed = time.time() - t0
        num_pages = len(result.get("structure", []))
        logger.info(
            "DONE   [%s]  %s  —  %.1fs  (%d top-level nodes)",
            state,
            pdf_path,
            elapsed,
            num_pages,
        )

        # Persist
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info("Saved to %s", out_path)

        return result

    except Exception:
        elapsed = time.time() - t0
        logger.exception(
            "FAILED  [%s]  %s  after %.1fs", state, pdf_path, elapsed
        )
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate PageIndex trees for state guideline PDFs."
    )
    parser.add_argument(
        "--state",
        type=str,
        default=None,
        help="Only process PDFs for this state (e.g. 'Colorado').",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=None,
        help="Process a single PDF file (full path).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=pageindex_config.PAGEINDEX_MODEL,
        help=f"Gemini model name (default: {pageindex_config.PAGEINDEX_MODEL}).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=pageindex_config.PAGEINDEX_OUTPUT_DIR,
        help=f"Output directory for tree JSON files (default: {pageindex_config.PAGEINDEX_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate trees even if output file already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files to process without actually running generation.",
    )
    args = parser.parse_args()

    # Single PDF mode
    if args.pdf:
        if not os.path.isfile(args.pdf):
            logger.error("PDF not found: %s", args.pdf)
            sys.exit(1)
        # Infer state from path
        parts = Path(args.pdf).parts
        state = "Unknown"
        for i, p in enumerate(parts):
            if p == "workers_comp_state_specific_guidelines" and i + 1 < len(parts):
                state = parts[i + 1]
                break

        if args.dry_run:
            print(f"Would process: [{state}] {args.pdf}")
            return

        run_tree_generation(args.pdf, state, args.output_dir, args.model, args.force)
        return

    # Batch mode
    pdfs = discover_pdfs(pageindex_config.PAGEINDEX_PDF_DIR, args.state)

    if not pdfs:
        logger.warning("No PDFs found in %s", pageindex_config.PAGEINDEX_PDF_DIR)
        sys.exit(1)

    logger.info("Found %d PDFs across %d states", len(pdfs), len(set(s for s, _ in pdfs)))

    if args.dry_run:
        for state, path in pdfs:
            out = tree_output_path(args.output_dir, state, path)
            exists = os.path.isfile(out)
            status = "EXISTS" if exists else "NEW"
            print(f"  [{status}]  [{state}]  {path}")
        return

    # Process PDFs
    os.makedirs(args.output_dir, exist_ok=True)
    success = 0
    skipped = 0
    failed = 0
    total_time = 0.0

    for state, pdf_path in pdfs:
        t0 = time.time()
        result = run_tree_generation(pdf_path, state, args.output_dir, args.model, args.force)
        elapsed = time.time() - t0
        total_time += elapsed

        if result is None:
            out_path = tree_output_path(args.output_dir, state, pdf_path)
            if os.path.isfile(out_path):
                skipped += 1
            else:
                failed += 1
        else:
            success += 1

    print("\n" + "=" * 60)
    print("TREE GENERATION COMPLETE")
    print("=" * 60)
    print(f"  Total PDFs:  {len(pdfs)}")
    print(f"  Success:     {success}")
    print(f"  Skipped:     {skipped}")
    print(f"  Failed:      {failed}")
    print(f"  Total time:  {total_time:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
