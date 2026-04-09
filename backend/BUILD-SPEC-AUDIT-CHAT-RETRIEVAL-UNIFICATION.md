# Build Spec: Audit/Chat Retrieval Unification

## Goal

Make audit retrieval use the exact same evidence-selection pipeline as chat to eliminate drift (e.g., CS minor pulling CS+Math/major requirements).

## Problem

- Chat and audit historically used different retrieval flows.
- Audit occasionally selected mixed/adjacent sources, causing requirement contamination.
- Debugging became difficult because correctness depended on path-specific retrieval behavior.

## Design

1. **Single shared evidence gatherer**
   - Use one function for hierarchical node selection + evidence assembly.
   - Inputs: query and retrieval budget config.
   - Outputs: combined evidence text, sources, search diagnostics, branch diagnostics.

2. **Shared retrieval budget contract**
   - Define one config object (`CHAT_RETRIEVAL_CONFIG`) for:
     - `max_branches`
     - `max_nodes`
     - `char_budget`
     - `per_node_cap`
   - Both chat and audit evidence collection must use this config.

3. **Audit path calls shared collector**
   - Requirements/audit evidence collection (`agentic_collect_evidence`) delegates to shared gatherer with the same config as chat.
   - No separate branch/node budget tuning in audit.

4. **Diagnostics parity**
   - Keep `branches` and `search` diagnostics in both chat and audit collection paths.
   - Enables direct side-by-side debugging.

## Implementation

- `services/agentic_retriever.py`
  - Added `CHAT_RETRIEVAL_CONFIG`.
  - `agentic_retrieve` now calls `_gather_tree_evidence(..., **CHAT_RETRIEVAL_CONFIG)`.
  - `agentic_collect_evidence` now calls `_gather_tree_evidence(..., **CHAT_RETRIEVAL_CONFIG)`.

## Verification Plan

1. Run `cs minor` via chat and audit debug mode.
2. Compare selected source titles/page ranges and search diagnostics.
3. Confirm both paths use identical retrieval budgets and source ordering characteristics.
4. Regression spot-check:
   - `computational biology major`
   - `computer science minor`
   - one policy query (e.g., pass/fail)

