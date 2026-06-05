# Public Health MCP

[![CI](https://github.com/cwyso/PublicHealthMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/cwyso/PublicHealthMCP/actions/workflows/ci.yml)

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

## Local PR review
Before opening a PR, ask Claude Code to *"Use the pr-reviewer subagent to
review my current diff."* The subagent reads `REVIEW.md`, `CLAUDE.md`, and
`.claude/decisions/*.md`, then reports findings by severity. Free,
on-demand, runs in a fresh context independent of whoever wrote the code.
A CI-integrated equivalent is tracked in issue #21.
