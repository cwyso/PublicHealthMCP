#!/usr/bin/env bash
# Stop: cheap end-of-turn sanity check.
# Per-edit testing happens in test-on-edit.sh; this just catches collection-time
# breakage (import errors, syntax problems across the suite) without running tests.
set -uo pipefail
[ -d tests ] || exit 0
command -v pytest >/dev/null 2>&1 || exit 0

out=$(pytest --collect-only -q 2>&1)
rc=$?
# rc 5 = "no tests collected" — fine, suite just hasn't been written yet
if [ $rc -ne 0 ] && [ $rc -ne 5 ]; then
  echo "Test suite fails to collect — likely an import or syntax error:" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
