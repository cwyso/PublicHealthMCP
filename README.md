# Public Health MCP

[![CI](https://github.com/cwyso/PublicHealthMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/cwyso/PublicHealthMCP/actions/workflows/ci.yml)

An MCP server that ingests public FDA and public health news and exposes it
as structured tools and resources for AI agents.

## Stack
- Python 3.11
- FastMCP
- Docker / docker-compose
- ChromaDB for semantic search (RAG) — planned
- Target deployment: AWS EC2

## Tools
- `health_check()` — server liveness check
- `fda_get_recalls(limit)` — latest FDA recalls and market withdrawals
- `fda_get_drug_updates(limit)` — FDA "What's New: Drugs" feed (all drug
  updates: guidances, workshops, AND approvals — the FDA publishes no
  approvals-only RSS feed)
- `fda_get_safety_alerts(limit)` — FDA MedWatch safety alerts
- `get_recent(sources, limit)` — newest items merged across every source

Planned: `get_public_health_news(topic)` (NewsAPI), `semantic_search(query)`
(RAG over ingested content), CDC sources.

## Run locally
```bash
cp .env.example .env
docker compose up --build
```

## Development
Install the dev dependencies, then enable the pre-commit hooks once:
```bash
pip install -r devcontainer/docker/dev-requirements.txt
pre-commit install
```
`black` and `ruff` then run automatically on every commit, with versions
pinned to match CI — so formatting/lint issues are caught locally instead of
on a pushed PR. Run them against everything with `pre-commit run --all-files`.

## Local PR review
Before opening a PR, ask Claude Code to *"Use the pr-reviewer subagent to
review my current diff."* The subagent reads `REVIEW.md`, `CLAUDE.md`, and
`.claude/decisions/*.md`, then reports findings by severity. Free,
on-demand, runs in a fresh context independent of whoever wrote the code.
A CI-integrated equivalent is tracked in issue #21.
