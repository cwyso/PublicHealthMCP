# Project Rules

## General
- Never auto-commit. Always wait for explicit user instruction before creating a git commit.
- Never push directly to main.
- Create a branch for each ticket.
- Test and edge case handling is king.

## PR review (human-in-the-loop)
- Before invoking `gh pr create`, always spawn the `pr-reviewer` subagent on
  the current branch's diff. See `REVIEW.md` for the rules it applies.
- Always present the reviewer's full findings (the tally and every finding).
- If there are NO Important findings, you may address the Nits and proceed,
  telling me exactly what was fixed.
- If there is ANY Important finding, STOP: do not fix, dismiss, or open the PR
  until I decide what to address or override.
- I have final say on every finding.


# FDA MCP Server — Claude Code Context

## Project Overview
An MCP server that ingests public FDA and public health news, exposing it
as structured tools and resources for AI agents. Built with FastMCP, Python,
and Docker. Includes RAG via ChromaDB for semantic search. Deployed to AWS
EC2 with a live public URL.

## Goal
- Working MCP server in Docker
- Tools that expose FDA RSS feeds and public health news
- RAG layer for semantic search over ingested content
- Deployed to AWS EC2 with a live public URL
- Clean public GitHub repo with strong README

## Tech Stack
- Python 3.11
- FastMCP
- Docker + docker-compose
- httpx for HTTP requests
- python-dotenv for config
- ChromaDB for vector storage
- Sentence-transformers or OpenAI embeddings for RAG
- Anthropic Claude API for the LLM layer
- AWS EC2 for deployment

## Project Structure
PublicHealthMCP/
├── devcontainer/
├── src/
│   ├── server.py        # composition root: build_server(), health_check, wiring
│   ├── providers.py     # generic SourceProvider (binds the shared store, exposes a source's tools)
│   ├── cross_source.py  # tools spanning all sources (get_recent)
│   └── fda/
│       ├── ingestion.py # FeedItem, FeedStore, fetch/parse, refresh helpers, FDA_FEEDS registry
│       └── tools.py     # FDA tool functions + TOOL_FNS
├── tests/               # mirrors src/ (tests/fda/, tests/test_*.py)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml       # pytest / black / ruff config
├── requirements.txt     # runtime deps
└── README.md

## Data Sources
- FDA RSS feeds — recalls/market withdrawals, "What's New: Drugs", MedWatch
  safety alerts. Live feed URLs are defined in `src/fda/ingestion.py`
  (`FDA_FEEDS`), not duplicated here, to avoid drift. Notes: the drugs feed is
  a firehose (guidances, workshops, AND approvals — there is no approvals-only
  feed); the old `/about-fda/contact-fda/rss-feeds` index URL is dead.
- CDC RSS feeds — planned.
- NewsAPI.org (free tier) for broader public-health news — planned.

## MCP Tools
Shipped (names as exposed to clients; authoritative list lives in README and code):
- `health_check()`
- `fda_get_recalls(limit)`, `fda_get_drug_updates(limit)`, `fda_get_safety_alerts(limit)`
- `get_recent(sources, limit)` — newest items merged across all sources
Planned:
- `get_public_health_news(topic)` — broader news via NewsAPI
- `semantic_search(query)` — RAG-powered search over ingested content

## Build Order

### Build
1. Bare bones FastMCP server running locally
2. Dockerize it
3. Add FDA RSS feed ingestion
4. Expose as MCP tools
5. Add RAG layer — ChromaDB + embeddings + semantic search tool
6. Connect Claude to it and verify end-to-end

### Deploy
7. Set up AWS free tier account
8. Deploy Docker container to EC2
9. Get it running on a public URL
10. Polish README, push to GitHub

## HUMAN-IN-THE-LOOP — read before any retrieval work
Chunking and ranking/reranking are DESIGN DECISIONS owned by the human, not
implementation details to guess.
- Do NOT write or modify chunking, embedding, retrieval, or ranking code until a
  decision record exists in .claude/decisions/ for that choice.
- When such work comes up, invoke the chunking-strategy or ranking-strategy skill,
  present 2-3 options with tradeoffs, and STOP for the human to decide.
- A decision is "made" only when the human says so and it is recorded in
  .claude/decisions/<name>.md.