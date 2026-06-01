---
name: ranking-strategy
description: Use whenever retrieval ranking or reranking is being designed or changed for the RAG layer. Forces a structured comparison of options and STOPS for a human decision. Do not implement ranking without going through this skill.
---
# Ranking / reranking strategy — decision skill

When ranking comes up, DO NOT pick an approach and implement it. Instead:

1. State what is being ranked and the retrieval setup (embedding model, vector store,
   number of candidates retrieved before ranking).
2. Present 2-3 options. For each: method (pure vector similarity, hybrid BM25 + vector,
   cross-encoder rerank, recency/authority boosting), latency and cost impact, tradeoffs
   (relevance vs. speed vs. complexity), and how source recency/authority factors in
   (recalls and alerts age out).
3. Recommend one, with tradeoffs explicit enough to overrule.
4. STOP. Wait for the human to choose. Record .claude/decisions/ranking.md before code.
