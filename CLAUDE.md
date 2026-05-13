# CLAUDE.md

## Project Overview

Agent-skills: 53 Claude Code skills and 8 autonomous agents (31 MCP tools, 1,106 tests) for polyglot development, web3, ZK, UI/UX, and systems programming. Skills provide context-injection for Claude Code sessions. Agents are standalone tools with CLIs and MCP servers.

## Structure

```
skills/                   # 53 Claude Code skills (context-injection via SKILL.md)
  <name>/SKILL.md         # Entry point per skill, with frontmatter + trigger clauses
agents/                   # 8 autonomous agents (standalone tools)
  digest/                 # Multi-platform activity digest (18 sources)
  recall/                 # Knowledge capture + FTS5 search + MCP server
  scribe/                 # Session insight extractor (writes to recall)
  autoresearch/           # Domain-agnostic autonomous experiment runner
  watchdog/               # Continuous repo health monitor
  prepper/                # Pre-session context builder
  sentinel/               # On-chain contract monitor
  patchbot/               # Polyglot dependency updater
scripts/                  # Repo tooling (skills-lint.sh)
.claude-plugin/           # Plugin distribution (plugin.json, marketplace.json)
```

## Skills

53 skills across 4 categories. Each lives in `skills/<name>/` with a `SKILL.md` entry point. Sub-files use YAML frontmatter with `impact`, `impactDescription`, and `tags` fields.

**Domain** (14): claude-api, droo-stack, raxol, noir, solidity-audit, zk-x-ray, ethskills, design-ux, nix, native-code, blockscout, coingecko, web-asset-generator, cancer-predisposition-variant-analyst

**Workflow** (11): tdd, code-review, prd-to-plan, focused-fix, release, qa, design-an-interface, ubiquitous-language, playwright, property-testing, refactoring-strategy

**Infrastructure** (11): mcp-server-builder, ci-cd-pipeline-builder, dependency-auditor, observability-designer, database-designer, performance-profiler, git-guardrails, git-worktree-manager, env-secrets-manager, tech-debt-tracker, security-audit

**Meta** (17): polymath, architect, agent-designer, adversarial-reviewer, self-improving-agent, codebase-onboarding, rag-architect, llm-cost-optimizer, digest, recall, voice, autoresearch, watchdog, prepper, sentinel, patchbot, skill-creator

### Lint

```bash
./scripts/skills-lint.sh
```

Validates: frontmatter fields, trigger clauses, file references, cross-skill links, "What You Get" sections.

### Adding a skill

1. Create `skills/<name>/SKILL.md` with frontmatter: `name`, `description` (include `TRIGGER when:` / `DO NOT TRIGGER`), `metadata`
2. Add sub-files with YAML frontmatter (`impact`, `impactDescription`, `tags` as comma-separated string)
3. Run `./scripts/skills-lint.sh`

## Agents

8 agents, each self-contained with Typer CLI, pydantic models, FastMCP server, and tests. Install: `cd agents/<name> && pip install -e ".[dev]"`

All agents expose MCP servers via `<agent> serve` (stdio transport). Configure in `~/.mcp.json`:

```json
{ "mcpServers": { "<agent>": { "command": "<agent>", "args": ["serve"] } } }
```

| Agent        | CLI            | Key commands                                                                                                          | MCP tools |
| ------------ | -------------- | --------------------------------------------------------------------------------------------------------------------- | --------- |
| digest       | `digest`       | `generate <topic> [-p hn,github,reddit,youtube,...]`. 18 adapters total; `digest list-platforms` to enumerate.        | 7         |
| recall       | `recall`       | `add`, `search [--min-relevance]`, `list`, `get`, `delete`, `stale`, `stats`, `extract`, `serve`                      | 8         |
| scribe       | `scribe`       | `watch [--once] [--idle-minutes N]`, `analyze <sid> --project PATH`, `stats`, `recent`, `serve`                       | 3         |
| autoresearch | `autoresearch` | `init <name> --metric <m> --verify <cmd>`, `run`, `loop`, `dashboard`, `status`                                       | 3         |
| watchdog     | `watchdog`     | `scan <repo>`, `report`, `watch --config watchdog.toml`                                                               | 2         |
| prepper      | `prepper`      | `brief [--budget N] [--task HINT]`, `inject`, `watch [--once]`, `alerts`, `serve`                                     | 3         |
| sentinel     | `sentinel`     | `check --address 0x...`, `watch --config sentinel.toml`, `alerts`                                                     | 2         |
| patchbot     | `patchbot`     | `scan`, `update`, `pr`                                                                                                | 3         |

### Tests

```bash
cd agents/<name> && python -m pytest tests/ -v
```

1,106 tests total across all agents + shared, 0 mocks. Shared helpers (HTTP, dates, value coercion) live in `agents/shared/src/shared/` and are imported by every agent that talks to an external API.

## Conventions

- Markdown files use YAML frontmatter
- Skills use `SKILL.md` as entry point; agents use `README.md`
- No mocks in tests
- Shell scripts: `set -euo pipefail`, shellcheck compliant
- Python: type hints, pathlib, pydantic, ruff for lint+format
- TypeScript: strict mode, zod for validation
