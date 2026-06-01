#!/usr/bin/env bash
# PostToolUse: when a .py file is written, run the matching test file (if any).
# Fast feedback right after the edit, no penalty on non-code turns.
set -uo pipefail

input=$(cat)
path=$(printf '%s' "$input" | python3 -c "import sys,json;print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Only act on Python files
case "$path" in
  *.py) ;;
  *) exit 0 ;;
esac

# Need pytest and a tests dir to do anything useful
command -v pytest >/dev/null 2>&1 || exit 0
[ -d tests ] || exit 0

# Repo-relative path
rel="${path#$PWD/}"

# If the edit IS a test file, run just it
if [[ "$rel" == tests/* ]]; then
  target="$rel"
else
  # Map src/foo/bar.py -> tests/foo/test_bar.py (and src/bar.py -> tests/test_bar.py)
  stripped="${rel#src/}"
  dir=$(dirname "$stripped")
  base=$(basename "$stripped" .py)
  if [ "$dir" = "." ]; then
    target="tests/test_${base}.py"
  else
    target="tests/${dir}/test_${base}.py"
  fi
fi

if [ -f "$target" ]; then
  if ! pytest -q -x --ff "$target"; then
    echo "Tests failed for $target — fix before continuing." >&2
    exit 2
  fi
else
  # No matching test yet — just make sure the edited file imports cleanly
  if ! python3 -c "import ast,sys; ast.parse(open('$rel').read())" 2>/dev/null; then
    echo "Syntax error in $rel." >&2
    exit 2
  fi
fi
exit 0
