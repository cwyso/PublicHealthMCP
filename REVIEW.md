# Review instructions

Source-of-truth review rules for PublicHealthMCP. Read by the local
`pr-reviewer` subagent today; the same file will feed the CI-integrated
reviewer when #21 lands. These are **review-only** rules — general project
conventions belong in `CLAUDE.md`.

## Severity

- 🔴 **Important** — bug, missing required test, violation of a project design rule
- 🟡 **Nit** — minor improvement, worth fixing but not blocking

Style and naming suggestions are 🟡 Nit at most.

## Always check (project-specific)

- **HIL rule.** Any change touching files matching `*chunk*`, `*embed*`,
  `*retriev*`, or `*rank*` MUST have a matching decision record at
  `.claude/decisions/<name>.md`. Flag missing decision records as 🔴 Important.
- **MCP tool docstrings.** New FastMCP tools (functions decorated with
  `@mcp.tool()`) MUST have a docstring — FastMCP exposes the docstring as the
  tool description to Claude clients. Missing docstring = 🔴 Important.
- **Runtime deps in both places.** A runtime dependency added by this PR
  must appear in BOTH `requirements.txt` AND
  `devcontainer/docker/dev-requirements.txt`. A new dep in one but not the
  other is 🔴 Important (CI builds from the latter; prod from the former).
  Pre-existing drift between the two files unrelated to the PR is out of
  scope for this review.
- **Test coverage of new behavior.** New code paths need at least one happy-path
  test and one failure-mode test. Missing either = 🔴 Important.
- **Tool proliferation / selection quality.** Agents select tools by
  name + description, so near-duplicate tools degrade selection. A new
  per-source tool must have semantics genuinely distinct from existing tools.
  Cross-source value belongs in capability tools (e.g. `get_recent`,
  `semantic_search`) that live in `src/aggregate.py`, NOT in N×M per-source
  lookalikes. Flag a new tool that merely re-slices what an existing tool
  already returns. 🟡 Nit normally; 🔴 Important if it duplicates an existing
  tool's data and intent.

## Cap the nits

Report at most 5 Nits per review. If more were found, end the summary with
"plus N similar items."

## Do NOT report

- Anything CI already enforces: `ruff check`, `black --check`, `pip-audit`,
  `docker build` — those gates run on every PR and red CI blocks merge
- Captured test fixtures under `tests/**/fixtures/` — real-world data, not
  code we wrote or maintain
- Documentation polish (typos, prose) unless the doc is now factually wrong

## Summary shape

Open the summary with a one-line tally:

```
2 Important, 3 Nits, 0 HIL violations
```

Then list findings grouped by severity. End with a verdict line:

```
Verdict: approve | request changes | comment only
```

If everything is clean, lead with "No blocking issues" and skip the detail body.
