# gradYOU8 Backend Debug - tree traversal inconsistency

## Problem
The tree traversal (Step 1 LLM) inconsistently picks page ranges:
- "Area B biology major" → pages 0-1 (index, wrong) or 338-340 (correct)
- ~50% success rate

## Root Cause
LLM routing is non-deterministic — sometimes MiniMax picks the wrong section.

## Proposed Fix: Hybrid Approach
1. **Keyword match first**: extract key terms from query, search tree directly for matching nodes
2. **LLM routing only as fallback**: when keyword match is low-confidence

Key terms to match:
- "area A/B/C" + "biology major" → find biology major section, return all area sub-sections
- "computational biology" → find genomics/computational biology specialization
- "math requirements" + "biology" → find biology major → find math course listings

## Implementation Plan
Modify tree_retrieve to:
1. Extract key entity terms (major, specialization, requirement type)
2. Walk the tree to find matching school/department nodes
3. If found with high confidence → use those page ranges
4. If low confidence → call LLM routing as now
