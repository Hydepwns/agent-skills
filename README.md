# agent-skills

53 Claude Code skills and 8 autonomous agents. Polyglot dev, web3, ZK, genomics, UI/UX, systems programming.

## How skill loading works

This is probably your first question, so let's get it out of the way.

Skills are **lazy**. Claude Code reads the short trigger clause from each `SKILL.md` frontmatter -- _the first few lines per skill_ -- and only pulls in the full skill content when the trigger matches your conversation. The sub-files (examples, checklists, reference tables) stay out of context until they're actually needed.

What's always present: ~2-4 lines of trigger description per skill. What's lazy: everything else. 53 skills at a few lines each is a small fraction of the context window. The heavy content -- sometimes hundreds of lines of domain-specific reference -- only loads when you're actually working in that domain.

So no, installing all 53 won't bloat your sessions. I.E. the noir ZK skill isn't eating tokens while you're reviewing a PR.

## Skills

Each skill lives in `skills/<name>/` with a `SKILL.md` entry point.

### Domain

| Skill                                   | What it does                                                                             |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| `claude-api`                            | Anthropic SDK reference (Python, TS, Go, Elixir, Rust, Lua, cURL)                        |
| `droo-stack`                            | Polyglot patterns (Elixir, TS, Go, Rust, C, Zig, Python, Lua, Shell, Noir, Chezmoi)      |
| `raxol`                                 | Elixir TUI/agent framework (TEA agents, MCP, headless sessions)                          |
| `noir`                                  | ZK circuit design, Aztec contracts, constraint optimization                              |
| `solidity-audit`                        | Solidity dev standards, vulnerability taxonomy, Foundry-first audit                      |
| `zk-x-ray`                              | Pre-audit briefing for ZK + EVM hybrids (Noir + Solidity), public-input parity check     |
| `ethskills`                             | Ethereum tooling, framework selection, EIP/ERC standards                                 |
| `design-ux`                             | UI/UX design patterns, design tokens, accessibility, TUI aesthetics                      |
| `nix`                                   | Nix language, flakes, NixOS, Home Manager, packaging                                     |
| `native-code`                           | NIF development (C/Rust/Rustler), SIMD (Zig), BEAM native boundary                       |
| `coingecko`                             | CoinGecko/GeckoTerminal API: prices, markets, DEX pools, trending tokens                 |
| `blockscout`                            | Blockscout MCP: 16 tools for on-chain data across 8+ chains                              |
| `web-asset-generator`                   | Favicon, app icon, OG image, devicon generation and optimization                         |
| `cancer-predisposition-variant-analyst` | Ultra-rare variant interpretation, mechanistic paradox resolution, ACMG/ClinGen evidence |

### Workflow

| Skill                   | What it does                                                            |
| ----------------------- | ----------------------------------------------------------------------- |
| `tdd`                   | Test-driven development: vertical slices, mutation testing, polyglot    |
| `code-review`           | PR review: blast radius, security scan, SOLID checks, 40-item checklist |
| `prd-to-plan`           | PRD -> phased tracer-bullet vertical slices (and optionally GitHub issues) |
| `focused-fix`           | 5-phase bug fix: SCOPE -> TRACE -> DIAGNOSE -> FIX -> VERIFY            |
| `release`               | Conventional commits, semver bumping, changelog, readiness checks       |
| `qa`                    | Bug triage and issue creation; interactive QA with background explorer  |
| `design-an-interface`   | "Design It Twice" -- parallel sub-agents with divergent constraints     |
| `ubiquitous-language`   | DDD glossary extraction, canonical terms                                |
| `playwright`            | Browser automation testing with Playwright                              |
| `property-testing`      | Generative/property-based testing (Hypothesis, proptest, StreamData, fast-check) |
| `refactoring-strategy`  | Strangler fig, large renames, safe restructuring for polyglot codebases |

### Infrastructure

| Skill                    | What it does                                                    |
| ------------------------ | --------------------------------------------------------------- |
| `mcp-server-builder`     | OpenAPI -> MCP server scaffolding (Python FastMCP + TypeScript) |
| `ci-cd-pipeline-builder` | Stack detection -> GitHub Actions/GitLab CI generation          |
| `dependency-auditor`     | Multi-language vuln scanning + license compliance               |
| `observability-designer` | SLO/SLI design, burn rate alerting, dashboard generation        |
| `database-designer`      | Schema analysis, ERD generation, index optimization             |
| `performance-profiler`   | Polyglot profiling (Node/Python/Go/Elixir/Rust)                 |
| `git-guardrails`         | PreToolUse hooks to block dangerous git operations              |
| `git-worktree-manager`   | Parallel dev with deterministic port allocation                 |
| `env-secrets-manager`    | Leak detection, rotation, pre-commit setup                      |
| `tech-debt-tracker`      | Debt scanning, cost-of-delay prioritization                     |
| `security-audit`         | Security vulnerability scanning and compliance assessment       |

### Meta

| Skill                  | What it does                                                           |
| ---------------------- | ---------------------------------------------------------------------- |
| `polymath`             | Split-brain research: three-tier roster, polymath persona composition  |
| `architect`            | ADR workflows, dependency classification, pattern detection            |
| `agent-designer`       | Multi-agent architecture patterns, tool schemas, guardrails            |
| `adversarial-reviewer` | Three-persona devil's advocate review                                  |
| `self-improving-agent` | Auto-memory curation, pattern promotion lifecycle                      |
| `codebase-onboarding`  | Auto-generate onboarding docs, audience-aware                          |
| `rag-architect`        | RAG pipeline design: chunking, embedding, retrieval, evaluation        |
| `llm-cost-optimizer`   | 7 optimization techniques in priority order                            |
| `digest`               | Multi-platform activity digest (18 sources + differential mode)        |
| `recall`               | Knowledge base: query past decisions, patterns, gotchas                |
| `autoresearch`         | Check experiment status, run iterations, view dashboards               |
| `watchdog`             | Scan repos for stale PRs, failing CI, security advisories              |
| `prepper`              | Generate pre-session project briefings                                 |
| `sentinel`             | Monitor on-chain contracts for anomalous transactions                  |
| `patchbot`             | Scan and update outdated dependencies across ecosystems                |
| `voice`                | Writing voice calibration from studied authors, combinatorial blending |
| `skill-creator`        | Scaffold new skills with frontmatter, triggers, and sub-files          |

## Agents

Eight standalone tools, each with a Typer CLI, pydantic models, and a FastMCP server. They run independently of the skill system -- install them separately, talk to them over MCP.

| Agent          | What it does                                                               | MCP tools |
| -------------- | -------------------------------------------------------------------------- | --------- |
| `digest`       | Multi-platform activity digest (18 sources, differential, structured views)| 7         |
| `recall`       | Knowledge capture and retrieval (SQLite + FTS5)                            | 8         |
| `scribe`       | Session insight extractor (writes to recall)                               | 3         |
| `autoresearch` | Autonomous experiment runner (ML, Noir, Solidity)                          | 3         |
| `watchdog`     | Repo health monitor (PRs, CI, deps, advisories)                            | 2         |
| `prepper`      | Pre-session context builder (git, GitHub, deps, recall, sentinel)          | 3         |
| `sentinel`     | On-chain contract monitor via Blockscout (11 chains)                       | 2         |
| `patchbot`     | Polyglot dependency updater (Elixir, Rust, Node, Go, Python)               | 3         |

### MCP integration

Each agent doubles as an MCP server. Add to `~/.mcp.json`:

```json
{
  "mcpServers": {
    "digest": { "command": "digest", "args": ["serve"] },
    "recall": { "command": "recall", "args": ["serve"] },
    "scribe": { "command": "scribe", "args": ["serve"] },
    "autoresearch": { "command": "autoresearch", "args": ["serve"] },
    "watchdog": { "command": "watchdog", "args": ["serve"] },
    "prepper": { "command": "prepper", "args": ["serve"] },
    "sentinel": { "command": "sentinel", "args": ["serve"] },
    "patchbot": { "command": "patchbot", "args": ["serve"] },
    "coingecko": { "url": "https://mcp.api.coingecko.com/mcp" }
  }
}
```

See [TODO.md](TODO.md) for the roadmap.

## Install

### Claude Code plugin

```bash
/plugin install agent-skills@DROOdotFOO/agent-skills
```

Or add the marketplace first:

```bash
/plugin marketplace add DROOdotFOO/agent-skills
```

### npx

Pick individual skills:

```bash
npx skills@latest add DROOdotFOO/agent-skills/tdd
npx skills@latest add DROOdotFOO/agent-skills/code-review
npx skills@latest add DROOdotFOO/agent-skills/polymath
```

Or grab everything:

```bash
npx skills@latest add DROOdotFOO/agent-skills
```

### chezmoi

Add to `.chezmoiexternal.toml`:

```toml
[".agents/skills"]
    type = "archive"
    url = "https://github.com/DROOdotFOO/agent-skills/archive/main.tar.gz"
    stripComponents = 2
    include = ["*/skills/**"]
    refreshPeriod = "168h"
```

Then symlink into Claude Code:

```bash
mkdir -p ~/.claude/skills
for d in ~/.agents/skills/*/; do
    ln -sf "../../.agents/skills/$(basename "$d")" ~/.claude/skills/
done
```

### Manual

```bash
git clone https://github.com/DROOdotFOO/agent-skills.git ~/.agents/skills-repo
ln -s ~/.agents/skills-repo/skills ~/.agents/skills
```

### Agents

Each agent installs independently:

```bash
cd agents/<name> && pip install -e .
```

## Lint

```bash
./scripts/skills-lint.sh
```

Checks frontmatter, trigger clauses, file references, and cross-skill links.

## License

MIT
