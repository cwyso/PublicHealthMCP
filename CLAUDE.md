# Project Rules

## General
- Never auto-commit. Always wait for explicit user instruction before creating a git commit.
- Never push directly to main.
- Create a branch for each ticket.
- Test and edge case handling is king.

## PR review
- Before invoking `gh pr create`, always spawn the `pr-reviewer` subagent on
  the current branch's diff. See `REVIEW.md` for the rules it applies.
- If the reviewer reports Important findings, address them (or get explicit
  user override) before opening the PR.


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
fda-mcp/
├── devcontainer/
├── src/
│   └── server.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md

## Data Sources
- FDA RSS feeds: https://www.fda.gov/about-fda/contact-fda/rss-feeds
    - Drug approvals
    - Recalls
    - Safety alerts
- CDC RSS feeds
- NewsAPI.org (free tier) for broader public health news

## Planned MCP Tools
- `get_fda_recalls()` — latest FDA recalls
- `get_drug_approvals()` — recent drug approvals
- `get_safety_alerts()` — FDA safety alerts
- `get_public_health_news(topic: str)` — broader news via NewsAPI
- `semantic_search(query: str)` — RAG powered search over ingested content

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