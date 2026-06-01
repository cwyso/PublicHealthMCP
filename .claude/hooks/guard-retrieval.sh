#!/usr/bin/env bash
# Blocks edits to RAG retrieval logic unless a human decision record exists.
set -uo pipefail
input=$(cat)
path=$(printf '%s' "$input" | python3 -c "import sys,json;print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)
case "$path" in
  *chunk*|*embed*)
    if [ ! -f .claude/decisions/chunking.md ]; then
      echo "Blocked: '$path' touches chunking/embedding but .claude/decisions/chunking.md does not exist. Run the chunking-strategy skill, get a human decision, and record it first." >&2
      exit 2
    fi ;;
  *retriev*|*rank*|*rerank*)
    if [ ! -f .claude/decisions/ranking.md ]; then
      echo "Blocked: '$path' touches retrieval/ranking but .claude/decisions/ranking.md does not exist. Run the ranking-strategy skill, get a human decision, and record it first." >&2
      exit 2
    fi ;;
esac
exit 0
