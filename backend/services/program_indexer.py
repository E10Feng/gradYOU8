"""
Program Indexer — fast, reliable program matching for WashU degree queries.

Approach:
  1. Pre-built synonym → canonical map (handles all common abbreviations instantly)
  2. Fast fuzzy substring match against program list
  3. LLM only as last-resort for genuinely ambiguous queries

This replaces fragile regex-based query rewriting.
"""
import json, re, sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).parent.parent
DATA_DIR = _BACKEND_ROOT.parent / "data"

# ── Canonical program name map (lowercase alias → canonical name) ─────────────────
_ALIAS_MAP: dict[str, str] = {}
_PROGRAMS_LIST: list[str] = []
_PROGRAMS_SIGNATURE: str = ""


def _build_alias_map() -> dict[str, str]:
    """Build lowercase alias → canonical name mapping from program titles."""
    aliases = {}

    # Hand-crafted canonical aliases for common abbreviations and variations
    # Format: "query variant (lowercased)" → "Canonical Program Name"
    canonicals = [
        # Computer Science — specific forms first (longest-match prefers these)
        ("computer science minor", "Computer Science Minor"),
        ("minor in computer science", "Computer Science Minor"),
        ("computer science major", "Computer Science Major"),
        ("cs major", "Computer Science Major"),
        ("cs minor", "Computer Science Minor"),
        # Biology
        ("bio major", "Biology Major"),
        ("biology", "Biology Major"),
        ("molecular biology", "Biology Major, Molecular Biology and Biochemistry Specialization"),
        ("computational biology", "Biology Major, Genomics and Computational Biology Specialization"),
        ("genomics and computational biology", "Biology Major, Genomics and Computational Biology Specialization"),
        ("biology major with specialization in genomics and computational biology", "Biology Major, Genomics and Computational Biology Specialization"),
        ("ecology and evolution", "Biology Major, Ecology and Evolution Specialization"),
        ("microbiology", "Biology Major, Microbiology Specialization"),
        ("neuroscience", "Biology Major, Neuroscience Specialization"),
        # Chemistry
        ("chem major", "Chemistry Major"),
        ("chemistry", "Chemistry Major"),
        ("biochemistry", "Chemistry Major, Biochemistry Specialization"),
        # Physics
        ("phys major", "Physics Major"),
        ("physics", "Physics Major"),
        ("astrophysics", "Astrophysics Major"),
        # Mathematics
        ("math major", "Mathematics Major"),
        ("maths major", "Mathematics Major"),
        ("mathematics", "Mathematics Major"),
        ("applied math", "Applied Mathematics Major"),
        # Economics
        ("econ major", "Economics Major"),
        ("economics", "Economics Major"),
        # Data Science
        ("data science", "Data Science Major"),
        # Engineering
        ("engineering major", "Engineering Major Requirements"),
        ("biomedical engineering", "Biomedical Engineering"),
        # Earth, Environmental, and Planetary Sciences
        ("earth science major", "Earth, Environmental, and Planetary Sciences Major"),
        ("earth science", "Earth, Environmental, and Planetary Sciences Major"),
        ("earth environmental and planetary sciences", "Earth, Environmental, and Planetary Sciences Major"),
        ("eeps major", "Earth, Environmental, and Planetary Sciences Major"),
        ("eeps", "Earth, Environmental, and Planetary Sciences Major"),
        ("earth science minor", "Earth Science Minor"),
        # Environmental
        ("environmental science", "Environmental Science Major"),
        ("environmental studies", "Environmental Studies Minor"),
        # Humanities
        ("english literature", "English Literature Major, Creative Writing Specialization"),
        ("english", "English Literature Major, Creative Writing Specialization"),
        ("history", "History Major"),
        ("philosophy", "Philosophy Major"),
        ("political science", "Political Science Major, American Politics Specialization"),
        ("psychology", "Psychological & Brain Sciences Major Requirements and Specializations"),
        ("sociology", "Sociology Major"),
        # Arts
        ("art major", "Art Major"),
        ("music major", "Music Major, General Concentration (BMus)"),
        ("drama major", "Drama Major"),
        ("dance major", "Dance Major"),
        # Languages
        ("french", "French Major"),
        ("spanish", "Spanish Minor"),
        ("german", "Germanic Languages and Literatures Major"),
        ("japanese", "East Asian Languages and Cultures Major, Chinese Specialization"),
        ("chinese", "East Asian Languages and Cultures Major, Chinese Specialization"),
        ("korean", "East Asian Languages and Cultures Major, Korean Specialization"),
        # Combined majors
        ("math and economics", "Mathematics and Economics Major"),
        ("economics and computer science", "Economics and Computer Science Major"),
        # Minors (abbreviations — full names handled above)
        ("math minor", "Mathematics Minor"),
        ("bio minor", "Biology Minor"),
        ("physics minor", "Physics Minor"),
        ("stats minor", "Statistics Minor"),
        ("writing minor", "Writing Minor"),
    ]

    for alias_lower, canonical in canonicals:
        aliases[alias_lower] = canonical

    return aliases


def _build_programs_list() -> list[str]:
    """Walk the tree and collect canonical program names."""
    split_names = [
        "bulletin_architecture.tree.json",
        "bulletin_arts_sciences.tree.json",
        "bulletin_engineering.tree.json",
        "bulletin_art.tree.json",
        "bulletin_university.tree.json",
        "bulletin_cross_school.tree.json",
        "bulletin_business.tree.json",
    ]
    split_paths = [DATA_DIR / n for n in split_names if (DATA_DIR / n).exists()]

    merged_structure: list[dict] = []
    if split_paths:
        for p in split_paths:
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                merged_structure.extend(raw)
            elif isinstance(raw, dict):
                merged_structure.extend(raw.get("structure", []))
        tree = {"structure": merged_structure}
    else:
        tree_path = DATA_DIR / "bulletin_full.tree.json"
        if not tree_path.exists():
            return []
        with open(tree_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        tree = raw if isinstance(raw, dict) else {"structure": raw}
    seen = set()
    programs = []

    def walk(nodes):
        for node in nodes:
            title = (node.get("title") or "").strip()
            title = title.replace("&#39;", "'").replace("&amp;", "&")

            lower_title = title.lower()
            is_program = (
                (" major" in lower_title or " minor" in lower_title
                 or " concentration" in lower_title or " specialization" in lower_title)
                and len(title) > 4
                and title not in seen
            )
            if is_program:
                seen.add(title)
                programs.append(title)
            if node.get("nodes"):
                walk(node["nodes"])

    walk(tree.get("structure", []))
    return programs


def get_alias_map() -> dict[str, str]:
    global _ALIAS_MAP
    if not _ALIAS_MAP:
        _ALIAS_MAP = _build_alias_map()
    return _ALIAS_MAP


def get_programs_list() -> list[str]:
    global _PROGRAMS_LIST, _PROGRAMS_SIGNATURE
    split_names = [
        "bulletin_architecture.tree.json",
        "bulletin_arts_sciences.tree.json",
        "bulletin_engineering.tree.json",
        "bulletin_art.tree.json",
        "bulletin_university.tree.json",
        "bulletin_cross_school.tree.json",
        "bulletin_business.tree.json",
        "bulletin_full.tree.json",
    ]
    parts = []
    for name in split_names:
        p = DATA_DIR / name
        if p.exists():
            try:
                parts.append(f"{name}:{int(p.stat().st_mtime)}:{p.stat().st_size}")
            except Exception:
                parts.append(f"{name}:x")
    signature = "|".join(parts)
    if not _PROGRAMS_LIST or signature != _PROGRAMS_SIGNATURE:
        _PROGRAMS_LIST = _build_programs_list()
        _PROGRAMS_SIGNATURE = signature
    return _PROGRAMS_LIST


def _fuzzy_search(query: str, programs: list[str], top_n: int = 5) -> list[tuple[str, int]]:
    """
    Fast fuzzy search: score programs by query word overlap.
    Returns top N (program_name, score) pairs.
    """
    # Extract significant words from query (3+ chars, no stopwords)
    stopwords = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
        "her", "was", "one", "our", "out", "what", "when", "where", "who",
        "will", "with", "from", "this", "that", "these", "those", "have", "had",
        "they", "them", "their", "would", "could", "should", "which", "your",
        "about", "into", "more", "some", "such", "only", "any", "how", "most",
        "courses", "course", "class", "classes", "require", "requirements",
        "need", "needed", "units", "credits", "major", "minor", "for", "what",
        "about", "tell", "me", "does", "which", "show", "list", "all",
    }
    q_words = [w.strip(".,!?;:()[]{}") for w in query.lower().split()
               if len(w.strip(".,!?;:()[]{}")) >= 3 and w.lower() not in stopwords]

    if not q_words:
        return []

    scored = []
    for prog in programs:
        prog_lower = prog.lower()
        score = 0
        for word in q_words:
            if re.search(r'\b' + re.escape(word) + r'\b', prog_lower):
                score += 3  # whole word match
            elif word in prog_lower:
                score += 1  # substring match
        # Boost for shorter, more specific titles
        if score > 0:
            score += max(0, (80 - len(prog)) // 20)
        scored.append((prog, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]


def extract_programs_from_query(query: str) -> list[str]:
    """
    Match a user query to canonical WashU program names.

    Strategy (fast, no LLM at query time):
      1. Check pre-built alias map (handles all common abbreviations)
      2. Fuzzy substring search against programs list
      3. Return best matches

    Returns list of matched program names.
    """
    programs = get_programs_list()
    if not programs:
        return []

    alias_map = get_alias_map()
    q_lower = query.lower().strip()

    # Step 1: Pre-built alias lookup
    # Try full query first, then progressively shorter
    if q_lower in alias_map:
        return [alias_map[q_lower]]

    # Step 2: Find the longest matching alias (prefer specific over generic).
    # "biology major with specialization in genomics..." beats "biology" alone.
    best_alias_len = 0
    best_canonical = ""
    for alias_lower, canonical in alias_map.items():
        if len(alias_lower) > best_alias_len and re.search(r'\b' + re.escape(alias_lower) + r'\b', q_lower):
            best_alias_len = len(alias_lower)
            best_canonical = canonical
    if best_canonical:
        return [best_canonical]

    # Step 3: Fuzzy search
    candidates = _fuzzy_search(query, programs, top_n=5)
    if candidates and candidates[0][1] >= 3:
        return [candidates[0][0]]

    # Step 4: If no strong match, return top fuzzy result if reasonable
    if candidates:
        best_score = candidates[0][1]
        # Require a minimum confidence threshold
        if best_score >= 2:
            return [candidates[0][0]]

    return []


# ── Build index on module load ─────────────────────────────────────────────────
get_programs_list()
get_alias_map()

if __name__ == "__main__":
    test_queries = [
        # Alias matches
        "cs major requirements",
        "what courses for the math major?",
        "tell me about computational biology",
        "bio major with genomics",
        "I want to study economics",
        # Fuzzy matches
        "what classes do I need for physics?",
        "computer science minor",
        "combined major in math and economics",
        "environmental science requirements",
        # Non-matches
        "tell me about the weather today",
        "who is the president",
    ]
    for q in test_queries:
        matches = extract_programs_from_query(q)
        print(f"Q: {q}")
        print(f"  -> {matches}")
        print()
