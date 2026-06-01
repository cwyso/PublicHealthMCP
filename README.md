# Public Health MCP

An MCP server that ingests public FDA and public health news and exposes it
as structured tools and resources for AI agents.

## Stack
- Python 3.11
- FastMCP
- Docker / docker-compose
- ChromaDB for semantic search (RAG)
- Deployed to AWS EC2

## Tools
- `get_fda_recalls()` — latest FDA recalls
- `get_drug_approvals()` — recent drug approvals
- `get_safety_alerts()` — FDA safety alerts
- `get_public_health_news(topic)` — broader news via NewsAPI
- `semantic_search(query)` — RAG-powered search across ingested content

## Run locally
```bash
cp .env.example .env
docker compose up --build
```
