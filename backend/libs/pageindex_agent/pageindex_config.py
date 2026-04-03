"""
Configuration for the PageIndex agent module.

Environment variables:
    MINIMAX_API_KEY    — your Minimax API key
    MINIMAX_GROUP_ID   — your Minimax group ID
    MINIMAX_MODEL      — model for tree generation (default: MiniMax-M2.7)
    PAGEINDEX_OUTPUT_DIR — output directory for tree JSON files
    PAGEINDEX_PDF_DIR    — source PDF directory
"""

import os
from dotenv import load_dotenv

load_dotenv()


class PageIndexConfig:
    # Minimix model for tree generation and retrieval
    PAGEINDEX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    # Output directory for tree JSON files
    PAGEINDEX_OUTPUT_DIR = os.getenv("PAGEINDEX_OUTPUT_DIR", "output_pageindex")

    # Source PDF directory
    PAGEINDEX_PDF_DIR = os.getenv("PAGEINDEX_PDF_DIR", "workers_comp_state_specific_guidelines")

    # PDF parser backend (PyMuPDF is higher quality)
    PAGEINDEX_PDF_PARSER = os.getenv("PAGEINDEX_PDF_PARSER", "PyMuPDF")

    # Tree generation options
    TOC_CHECK_PAGE_NUM = int(os.getenv("PAGEINDEX_TOC_CHECK_PAGES", "20"))
    MAX_PAGE_NUM_EACH_NODE = int(os.getenv("PAGEINDEX_MAX_PAGES_NODE", "10"))
    MAX_TOKEN_NUM_EACH_NODE = int(os.getenv("PAGEINDEX_MAX_TOKENS_NODE", "20000"))

    # How many top tree nodes to retrieve per query
    RETRIEVAL_TOP_K = int(os.getenv("PAGEINDEX_RETRIEVAL_TOP_K", "5"))


pageindex_config = PageIndexConfig()
