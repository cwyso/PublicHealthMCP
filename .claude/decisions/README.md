# Decision records
One file per locked design decision (e.g. chunking.md, ranking.md).
Each should capture: the choice, the rationale, alternatives rejected, and the date.
The guard hook in .claude/hooks/guard-retrieval.sh blocks edits to RAG code until the
matching decision file exists here.
