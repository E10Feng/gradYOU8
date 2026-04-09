"""
Slice bulletin_full.tree.json into college-specific and domain-specific trees.

Node groups (subject to change as WashU bulletin structure evolves):
  0  Preface
  1  About This Bulletin
  2  About Washington University in St. Louis
  3  Undergraduate Study            → cross_school
  4  Admission Procedures          → cross_school
  5  Financial Support             → cross_school
  6  Tuition & Fees                → cross_school
  7  Majors (all schools)          → cross_school
  8  Minors (all schools)          → cross_school
  9  Architecture (leaf, p70)     → architecture
  10 Architecture (branch, p70)    → architecture
  11 Art                            → art
  12 Arts & Sciences               → arts_sciences
  13 Business                      → business
  14 Engineering                   → engineering
  15 Beyond Boundaries Program     → cross_school (combined with Interdisciplinary)
  16 Interdisciplinary Opportunities → cross_school (combined with Beyond Boundaries)
  17 VA Appendix: Undergraduate Programs → university
  18 Index                         → university

Usage:
  py split_bulletin_trees.py
"""

import json
import copy
from pathlib import Path

SRC = Path(__file__).parent.parent / "data" / "bulletin_full.tree.json"
OUT_DIR = Path(__file__).parent.parent / "data"

# ── Node group definitions ────────────────────────────────────────────────────
# Each entry: (output_filename, [top-level node indices])
# Empty list means "take all unmatched nodes".
NODE_GROUPS = {
    "arts_sciences":  [12],
    "engineering":    [14],
    "business":       [13],
    "architecture":   [9, 10],   # leaf + branch (duplicate title, keep both)
    "art":           [11],
    # Beyond Boundaries + Interdisciplinary combined into cross_school
    "cross_school":   [3, 4, 5, 6, 7, 8, 15, 16],
    # Everything not explicitly listed above goes here
    "university":     [],
}

# Nodes that are explicitly claimed by named trees — exclude from "university"
# (everything else without a home goes to university)
EXPLICIT_INDICES = set()
for indices in NODE_GROUPS.values():
    EXPLICIT_INDICES.update(indices)


def load_tree():
    with open(SRC, "r", encoding="utf-8") as f:
        return json.load(f)


def slice_tree(tree, indices):
    """Return a new list containing only the top-level nodes at given indices."""
    return [copy.deepcopy(tree[i]) for i in indices if i < len(tree)]


def save_tree(nodes, filename):
    path = OUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)
    print(f"  -> {path.name}  ({len(nodes)} top-level node(s), "
          f"{sum(len(n.get('nodes', [])) for n in nodes)} total child nodes)")


def main():
    tree = load_tree()
    print(f"Loaded {len(tree)} top-level nodes from bulletin_full.tree.json\n")

    assigned_indices = set()
    for group_name, indices in NODE_GROUPS.items():
        if not indices:  # skip empty (unassigned catch-all)
            continue
        nodes = slice_tree(tree, indices)
        save_tree(nodes, f"bulletin_{group_name}.tree.json")
        assigned_indices.update(indices)

    # Remaining nodes → university tree
    university_indices = [i for i in range(len(tree)) if i not in assigned_indices]
    university_nodes = slice_tree(tree, university_indices)
    print(f"\n  -> bulletin_university.tree.json  "
          f"({len(university_nodes)} top-level node(s), "
          f"{sum(len(n.get('nodes', [])) for n in university_nodes)} child nodes)")
    print(f"      (unassigned indices: {university_indices})")
    save_tree(university_nodes, "bulletin_university.tree.json")

    print("\nDone.")


if __name__ == "__main__":
    main()
