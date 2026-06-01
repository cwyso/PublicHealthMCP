---
name: chunking-strategy
description: Use whenever chunking of ingested documents is being designed or changed for the RAG layer. Forces a structured comparison of options against the actual data and STOPS for a human decision. Do not implement chunking without going through this skill.
---
# Chunking strategy — decision skill

When chunking comes up, DO NOT pick an approach and implement it. Instead:

1. Characterize the data. PublicHealthMCP has two very different shapes:
   - Short, structured items (recalls, safety alerts, drug approvals)
   - Long prose (news articles)
   These likely want DIFFERENT strategies.
2. Present 2-3 concrete options. For each: method (fixed-size, recursive/structural,
   semantic), chunk size + overlap in tokens and why, tradeoffs (retrieval precision vs.
   context completeness, cost, complexity), and how metadata (source, date, type) is kept
   for filtering.
3. Recommend one, but make tradeoffs explicit enough for the human to overrule.
4. STOP. Wait for the human to choose. Once chosen, write .claude/decisions/chunking.md
   (the choice, the rationale, the date) BEFORE any code is written.
