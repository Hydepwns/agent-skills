# TODO

## Open

### Skills

- [ ] **incident-response** -- on-call playbooks, severity classification, runbook creation, blameless postmortem/RCA. Closes gap between observability-designer and focused-fix
- [ ] **elixir-otp** -- OTP architecture beyond raxol: supervision trees, gen_server design, clustering, hot code reloading, Erlang observer
- [ ] **zk-optimization** -- ZK circuit performance engineering: constraint counting, recursion patterns, proving system trade-offs (Plonk vs Groth16)
- [ ] **api-contract** -- REST/GraphQL/gRPC spec-first design, consumer contract testing, schema evolution, breaking change detection
- [ ] **container-strategy** -- Dockerfile best practices, multi-stage builds, image scanning, deployment patterns (blue-green, canary)

### CI/CD

- [ ] **Release automation** -- version bumping, changelog (all agents frozen at 0.1.0, deferred: no consumers)
- [ ] **Snyk agent-scan** gate (deferred: server returning 503)

### Agent security

- [ ] Run `uvx snyk-agent-scan@latest --skills ./skills/` (blocked: snyk server 503)
- [ ] Add snyk to CI: `uvx snyk-agent-scan@latest --ci --json --skills`
- [ ] Evaluate `guard install claude` for real-time PreToolUse hooks
- [ ] Evaluate Skill IDs ([skill-id-standard](https://github.com/gendigitalinc/skill-id-standard)) for integrity verification
- [ ] Track AARTS spec evolution (currently v0.1)
- [ ] Track Sage MCP interception support (not in v0.8.0, needed for our 8 MCP agents)

### Digest adapters

Expand beyond tech/crypto. Full API specs in `agents/digest/SPECS.md`.

**Tier 1** (clean APIs, implement first):

- [x] Semantic Scholar -- JSON, citationCount + influentialCitationCount, tldr as summary, soft-fails on 429 (done 2026-05-13; set `S2_API_KEY` for real usage)
- [x] PubMed -- JSON esearch + esummary + iCite (XML efetch avoided; key optional, done 2026-05-13)
- [x] Federal Register -- JSON, keyless, page_views + significant flag (done 2026-05-13; comment_count not available on list endpoint — see SPECS.md note)
- [x] Shodan enhancements -- InternetDB fallback + facets endpoint shipped 2026-05-13. Exploits API deferred (needs CVE-pattern routing).

**Tier 2** (moderate complexity):

- [x] arXiv -- Atom XML, no engagement (engagement=0; S2 composite enrichment deferred), 3s rate-limit respected (done 2026-05-13)
- [x] OpenAlex -- JSON, 470M+ works, fwci bonus, polite pool via OPENALEX_EMAIL (done 2026-05-13)
- [x] CourtListener -- JSON opinions search, citeCount engagement, SCOTUS bonus, anonymous works (done 2026-05-13)
- [x] ClinicalTrials.gov -- JSON v2 API, enrollment + phase engagement, keyless, urllib not httpx (done 2026-05-13)
- [ ] Congress.gov -- JSON, cosponsor count needs 2nd call, free key

**Tier 3-4** (niche): Crossref, regulations.gov, openFDA, bioRxiv, WHO DON, CDC MMWR, EUR-Lex, UK Legislation

**Shared infra**: XML parser (arXiv/PubMed/UK Legislation), ExpandedQuery extensions, credibility + ranking updates

### Benchmarking

- [ ] **Live benchmark run** -- update expired Anthropic API key, run `skill-bench.py compare` with real API calls
- [ ] **Autoresearch integration** -- wire skill-bench as verify command, iterate on skill content to maximize correctness
- [ ] **Cursor rules comparison** -- source community `.cursorrules` files, run head-to-head vs skills
- [ ] **Multi-skill suites** -- add test suites for code-review, tdd, security-audit beyond python-patterns

### Research backlog

- [ ] Review alirezarezvani marketing/PM skills for hidden gems
- [ ] Watch for new skills repos in Claude Code ecosystem

---

## Completed

### 2026-05-14 -- Documentation drift fix

Audited CLAUDE.md, README.md, and `agents/digest/README.md` against the actual repository state after the multi-day adapter + DRY-refactor work. Numbers and lists are now consistent across all three docs.

Drift corrected:

- `771 tests` -> `1,106 tests` (CLAUDE.md, two places)
- `11 sources / 11 adapters` -> `18` (CLAUDE.md structure block + agent table; README agent + meta-skill tables; digest/README description + architecture diagram + credibility tier list)
- README's Workflow table listed 3 skills that don't exist (`prd-to-issues`, `triage-issue`, `grill-me`) and was missing 2 real ones (`property-testing`, `refactoring-strategy`). Now matches `skills/` exactly.
- `digest/README.md` "All platforms" CLI example removed (the 11-platform list became misleading after the 7 new adapters); replaced with a pointer to `digest list-platforms`.
- `digest/README.md` API Specs section updated to reflect Tier 1 + most of Tier 2 are now implemented.
- Added a one-line note in CLAUDE.md and `digest/README.md` pointing to `agents/shared/src/shared/` as the canonical home for shared helpers.

Verification:

- Skills count: 53 in docs == 53 in `skills/` directory
- Agents count: 8 in docs == 8 in `agents/` (excluding `shared/` library)
- All 53 skills appear in the README's Skills section; no phantom entries
- Cross-doc grep for the old patterns (`771 tests`, `11 sources`, the three phantom skill names) returns nothing

Audience-specific content kept in both docs (intentional, not duplication): README has user-facing install paths (plugin, npx, chezmoi) and full skill descriptions; CLAUDE.md has contributor conventions (no mocks, ruff, type hints) and "Adding a skill" steps. The numbers that previously diverged are now sourced consistently -- worth considering a doc-lint check that asserts these numbers match the filesystem, but deferred.

### 2026-05-13 -- DRY refactor: promote helpers to shared package

Final pass of the DRY sweep -- promoted the digest-local helpers up to `agents/shared/` so sentinel, scribe, and watchdog can use them too.

New shared modules:

- `shared/dates.py` -- `parse_iso_utc`, `parse_date_utc`, `since_date`, `cutoff_datetime`
- `shared/http.py` -- `fetch_json`, `fetch_text`
- `shared/coerce.py` -- `coerce_int`, `coerce_float`, `format_authors_etal`

`agents/digest/src/digest/adapters/_helpers.py` shrank from ~190 lines to a 30-line re-export façade -- digest adapters keep their `from digest.adapters._helpers import ...` lines untouched. No adapter file needed to change.

Refactored outside digest:

- `sentinel/monitor.py` -- replaced `httpx.get + raise_for_status` boilerplate with `fetch_json`; replaced inline `fromisoformat(...replace("Z"...))` with `parse_iso_utc`
- `scribe/analyzer.py` -- replaced inline `fromisoformat` in message-timestamp parsing with `parse_iso_utc`, keeping the epoch-ms fallback path
- `watchdog/checks.py` -- two `fromisoformat(pr["createdAt"]...)` and `fromisoformat(issue["createdAt"]...)` call sites replaced with `parse_iso_utc`

Verification:

- **1,106 tests pass across all 9 agent suites** (shared 56, digest 538, sentinel 55, scribe 114, watchdog 33, autoresearch 74, recall 102, prepper 65, patchbot 69)
- Cross-agent grep for `fromisoformat...replace("Z"...)` returns only `shared/dates.py` (canonical implementation)
- Only `shared/http.py` and `semanticscholar.py` (intentional, for 429 status-check) import httpx directly

Cumulative impact across today's four DRY passes:

- ~280 lines of duplication removed across the agent fleet
- 11 shared helpers with 56 dedicated tests
- 4 silent crash bugs fixed as a side-effect (adapters with raw `raise_for_status` and no try/except now soft-fail)
- One canonical implementation per concern; one import statement per consumer

### 2026-05-13 -- DRY refactor: HTTP fetch helpers

Extracted the repeated `httpx.get + raise_for_status + json + try/except → return []` boilerplate into shared `fetch_json` and `fetch_text` helpers. Every adapter in the digest agent now goes through these, except Semantic Scholar (which keeps direct httpx for its 429-status-code soft-fail).

New helpers in `adapters/_helpers.py`:

- `fetch_json(url, *, method="GET", default=None, **httpx_kwargs)` -- catches HTTP + JSON parse errors, returns `default` on failure. Accepts any `httpx.request` kwarg (params, headers, json body, follow_redirects, etc.). Method param added so snapshot's GraphQL POST works without a separate helper.
- `fetch_text(url, *, default="", **httpx_kwargs)` -- same shape for XML / RSS / plaintext endpoints. Used by arxiv.

Adapters refactored (15 total): federalregister, openalex, courtlistener, pubmed (3 call sites), shodan (3 call sites including the previously-uncovered InternetDB 404 handler), arxiv (XML via fetch_text), coingecko (3), blockscout (3), ethresearch, polymarket, hackernews, reddit, snapshot (POST via `method="POST"`), packages (3 -- hex/crates/npm).

Side-effect upgrades:

- ethresearch, polymarket, hackernews, reddit, packages all previously had raw `httpx.get + raise_for_status` with NO try/except, so a single network error would crash the whole adapter. They now soft-fail to an empty result, matching the rest of the codebase.
- shodan's keyless InternetDB path collapsed from a 12-line try/except/status-check block to a single helper call (the helper's default-on-non-2xx behavior handles the 404 case implicitly).

Final state:

- 5 new unit tests for the fetch helpers (default-on-error contract, custom default shape preservation, POST method routing implicit via existing snapshot tests)
- Only `_helpers.py` and `semanticscholar.py` import httpx directly. Every other adapter goes through the helpers.
- Full suite: 538 tests pass (was 533 → +5 helper tests)
- Live smoke: HN returns real stories with point counts; Polymarket returns real prediction markets with volume

### 2026-05-13 -- DRY refactor: older adapters

Extended the shared `adapters/_helpers.py` helpers to the original 11 adapters (hackernews/github/reddit/youtube/polymarket/snapshot/ethresearch/coingecko/blockscout/packages/shodan). Six adapters had ISO-timestamp duplication; the rest use epoch timestamps and didn't need refactoring.

Refactored to use `parse_iso_utc`:

- `polymarket._parse_timestamp` -- removed (now inline via helper at the one call site)
- `github` -- two inline `datetime.fromisoformat(row["createdAt"].replace(...))` call sites collapsed via helper
- `ethresearch` -- one inline if/else block collapsed to a single line
- `blockscout._parse_timestamp` -- body reduced to one line; signature kept because the test imports it directly
- `packages._parse_timestamp` -- body reduced to one line; epoch fallback preserved (packages-specific "sort missing dates as very old" semantic)
- `shodan` -- one missed inline call site inside the per-host `_build_item` flow

Final survey: every remaining adapter-local `_parse/_format/_coerce` helper has a legitimate adapter-specific reason (XML element traversal, single-string-to-list extraction, decimal-string monetary parsing, different fallback semantic).

- Net: ~30 more lines of duplication removed
- No leftover `fromisoformat(...replace("Z", "+00:00"))` outside `_helpers.py`
- Full suite: 533 tests still pass (same as after the first refactor pass -- no new tests needed since the helpers were already covered)
- Live smoke: polymarket fetched 2 real prediction markets via the refactored code path

### 2026-05-13 -- DRY refactor: shared adapter helpers

Extracted duplicated helpers from 8 adapters into `agents/digest/src/digest/adapters/_helpers.py`. Eliminated ~120 lines of pure duplication across coerce/format/parse functions.

- New `_helpers.py` (~130 lines, 40 unit tests in `test_adapter_helpers.py`):
  - `coerce_int(value) -> int` -- replaced 6 identical 7-line copies
  - `coerce_float(value) -> float | None` -- replaced 2 identical copies; preserves None for "not scored yet" signals
  - `format_authors_etal(names: list[str]) -> str | None` -- single helper now used by arxiv, pubmed, semanticscholar, openalex, courtlistener. Each adapter does API-specific name extraction (nested dicts, semicolon split) at its own boundary.
  - `parse_date_utc(value, formats=("%Y-%m-%d",))` -- strptime-based, accepts custom format tuples for PubMed (`%Y/%m/%d`) and ClinicalTrials (multi-precision fallback)
  - `parse_iso_utc(value)` -- fromisoformat-based, used by FederalRegister and arXiv for flexible ISO timestamps
  - `since_date(days, fmt="%Y-%m-%d") -> str | None` -- ISO by default, slash format for PubMed
  - `cutoff_datetime(days) -> datetime | None` -- companion for client-side date filtering
- Refactored 8 adapters: federalregister, pubmed, semanticscholar, shodan, arxiv, openalex, courtlistener, clinicaltrials
- Each adapter's tests updated to verify the helper is wired correctly (vs the old local-method tests)
- Full digest suite: **533 tests pass** (was 493 → +40 new helper tests)
- Live smoke: FederalRegister still fetches real data; URL+parsing still correct

### 2026-05-13 -- ClinicalTrials.gov digest adapter

Fourth Tier 2 adapter for digest. JSON v2 API `/studies`, keyless. Response is deeply nested under `protocolSection` with module sub-dicts; adapter traverses paths carefully rather than using flat access.

- `agents/digest/src/digest/adapters/clinicaltrials.py` (~190 lines)
- 39 tests, no mocks. Synthetic study dicts mirror real v2 shape verified on 2026-05-13.
- Wired: registry, `credibility.SOURCE_TIERS` (VERIFIED -- registered trials with regulatory oversight), `_per_item_bonus` (PHASE3/4=0.4, PHASE2=0.2, enrollment>1000=+0.3, capped at 0.5), `ranking.PLATFORM_WEIGHTS` (1.5).
- Engagement = `enrollment_count + phase_score` where phase_score weights: PHASE4=40, PHASE3=30, PHASE2=20, PHASE1=10, EARLY_PHASE1=5, NA=0. Multi-phase trials use the highest weight.
- **Uses urllib not httpx**: ClinicalTrials.gov's edge WAF rejects httpx (TLS fingerprinting) with 403 regardless of headers. stdlib urllib passes through. This is the only adapter that needs the workaround; documented inline + in SPECS.
- Date parsing accepts `YYYY-MM-DD`, `YYYY-MM`, and `YYYY` formats (some early-registration trials use partial dates).
- Live API: 5 GLP-1 weight loss trials across PHASE1-4 + NA, with real sponsors (Roche, NIAAA, Lilly), enrollment counts, conditions, statuses.
- Full digest suite: 493 tests pass (was 454)

### 2026-05-13 -- CourtListener digest adapter

Third Tier 2 adapter for digest. Single-step `/api/rest/v4/search/?type=o` (opinions). Optional `COURTLISTENER_TOKEN` (header `Authorization: Token`); anonymous works in practice.

- `agents/digest/src/digest/adapters/courtlistener.py` (~150 lines)
- 38 tests, no mocks. Synthetic dicts match real /search/ shape verified against courtlistener.com on 2026-05-13.
- Wired: registry, `credibility.SOURCE_TIERS` (DELIBERATE), `_per_item_bonus` (citeCount thresholds 20/100 + SCOTUS bonus +0.3, capped at 0.5), `ranking.PLATFORM_WEIGHTS` (2.0).
- Engagement = `citeCount`. SCOTUS opinions get a +0.3 court-prestige bonus regardless of cite count.
- **Dedupe by `cluster_id`**, not `id` (SPECS lied -- there's no top-level `id` field). This collapses concurring/dissenting sibling opinions into one digest slot per case.
- `judge` is a string with semicolon-separated panel members; adapter renders single-judge as is, multi-judge as "First et al."
- `absolute_url` is relative; adapter prepends `https://www.courtlistener.com` to build Item URL.
- Live API: 5 first-amendment opinions across 5 different courts (Oklahoma Civ App, California Ct App, Pennsylvania Super Ct, Oregon Ct App, 9th Circuit) with citations, judges, dates.
- Full digest suite: 454 tests pass (was 416)

### 2026-05-13 -- OpenAlex digest adapter

Second Tier 2 adapter for digest. JSON `/works` search with field selection (`select=` param) to keep responses small. Optional auth via `OPENALEX_API_KEY` (param) or `OPENALEX_EMAIL` (polite pool, mailto param).

- `agents/digest/src/digest/adapters/openalex.py` (~175 lines)
- 35 tests, no mocks. Synthetic dicts mirror real /works response shape verified against api.openalex.org on 2026-05-13.
- Wired: registry, `credibility.SOURCE_TIERS` (DELIBERATE), `_per_item_bonus` (FWCI thresholds 1.0/3.0), `ranking.PLATFORM_WEIGHTS` (2.0).
- Engagement = `cited_by_count`. FWCI > 3.0 = 0.4 bonus (3x field avg), > 1.0 = 0.2.
- `null` FWCI is preserved as `None` (not 0.0) so bonus function distinguishes "too new to score" from "below field avg".
- DOI normalization: full URL if returned; wrap bare DOI in `https://doi.org/`; URL preferred over OpenAlex page as the Item URL.
- Work ID extraction from `https://openalex.org/W1234567890` URLs. Concept IDs trimmed to trailing segment.
- Open access metadata flattened to `{is_oa, oa_url, oa_status}` in raw.
- SPECS note: auth is NOT strictly required in practice despite docs claiming so since Feb 2025.
- Live API: 5 zero-knowledge papers fetched with FWCI, OA status, multi-author lists, recent publication dates.
- Full digest suite: 416 tests pass (was 381)

### 2026-05-13 -- arXiv digest adapter

First Tier 2 adapter for digest. Atom XML parser using stdlib `xml.etree.ElementTree` -- no extra dependencies. No engagement signal (arXiv doesn't expose views or citations); `Item.engagement` is always 0 and ranking falls back to recency.

- `agents/digest/src/digest/adapters/arxiv.py` (~165 lines)
- 27 tests, no mocks. Synthetic XML strings parsed via `ET.fromstring` mirror the real Atom shape verified against export.arxiv.org on 2026-05-13.
- Wired: registry, `credibility.SOURCE_TIERS` (DELIBERATE -- intentional submission), `ranking.PLATFORM_WEIGHTS` (2.0).
- `_respect_rate_limit()` enforces 3s spacing between requests with `time.monotonic()`; first request doesn't sleep. Both behaviors covered by unit tests via monkeypatched time.
- ID extraction handles modern (`2401.12345v3`) and pre-2007 (`cs.LG/0701234v2`) arXiv IDs with one non-greedy regex.
- Title and abstract text are inline-wrapped in the XML; adapter collapses whitespace to single spaces before storage.
- `engagement = 0` by design. A future S2 composite enrichment via `GET /paper/arXiv:{id}` would inject citation counts -- left for later since it's a multi-adapter wiring change, not a single-adapter feature.
- Live API: 3 diffusion-model papers fetched with primary categories, multi-author lists, abstracts.
- Full digest suite: 381 tests pass (was 354)

### 2026-05-13 -- Shodan adapter enhancements

Two enhancements to the existing shodan adapter: InternetDB keyless fallback + facets summary item.

- **InternetDB fallback**: when `SHODAN_API_KEY` is unset, IP-shaped query terms (single IPv4 / IPv6, parsed via stdlib `ipaddress`) route to `internetdb.shodan.io/{ip}` instead of returning `[]`. CIDR notation and partial IPs are correctly rejected. Adds `raw.kind="internetdb"` to those items.
- **Facets endpoint**: authenticated `fetch()` now follows each per-host search with a `/shodan/host/count` call (zero query credits) requesting `org:10,country:10,port:10,vuln:10,product:10`. Emits a single aggregate Item per query term with `raw.kind="facet_summary"`, total as engagement, and normalized top facets in raw.
- Per-host items now also carry `raw.kind="host"` so downstream consumers can distinguish the three item kinds.
- 26 tests (8 existing + 18 new), no mocks. Live smoke: keyless InternetDB lookup of 8.8.8.8 + 1.1.1.1 returned both with real port lists and hostnames.
- Exploits API deferred -- would need CVE-pattern detection on query terms and a separate base URL flow.
- SPECS.md updated with implementation status.
- Full digest suite: 354 tests pass (was 336)

### 2026-05-13 -- Semantic Scholar digest adapter

Third Tier 1 adapter for digest. Single-step `/paper/search` with full fields list; client-side date filtering since the API has no native pubdate parameter. Optional `S2_API_KEY` env var.

- `agents/digest/src/digest/adapters/semanticscholar.py` (~160 lines)
- 33 tests, no mocks (synthetic API-shape dicts; shapes confirmed against live `/paper/search/bulk` response before writing)
- Wired into adapter registry, `credibility.SOURCE_TIERS` (DELIBERATE), `credibility._per_item_bonus` (influentialCitationCount thresholds 10/50), `ranking.PLATFORM_WEIGHTS` (2.5)
- Engagement = citationCount + 5\*influentialCitationCount; tldr.text -> Item.summary
- Soft-fails on 429: returns [] for the rate-limited term, continues with remaining terms instead of crashing
- Two SPECS corrections: `tldr` is NOT supported on `/paper/search/bulk` (400); unauth rate limit is more aggressive than the SPECS suggests in practice — cooldown can run minutes from a single IP
- Full digest suite: 336 tests pass (was 303)
- Live API: rate-limited 429 from this IP today, exercised the soft-fail path; happy path covered by 33 unit tests against confirmed-real shapes

### 2026-05-13 -- PubMed digest adapter

Second Tier 1 adapter for digest. Three-step pipeline (esearch -> esummary -> iCite) using only JSON endpoints (efetch XML avoided per SPECS suggestion). Optional `NCBI_API_KEY` env var.

- `agents/digest/src/digest/adapters/pubmed.py` (~190 lines)
- 31 tests, no mocks (synthetic API-shape dicts for esummary + iCite responses)
- Wired into adapter registry, `credibility.SOURCE_TIERS` (DELIBERATE), `credibility._per_item_bonus` (RCR + clinical bonuses), and `ranking.PLATFORM_WEIGHTS` (2.5)
- iCite enrichment is tolerant of failure -- engagement falls back to 0 if the citation API errors, preserving the adapter's primary search-step value
- Authors rendered as "First et al." for multi-author papers, single name for solo
- DOI extracted from nested `articleids` list, not a top-level field
- Full digest suite: 303 tests pass (was 272)
- Live API smoke-tested end-to-end: 5 mrna-vaccine papers fetched with journals, authors, DOIs

### 2026-05-13 -- Federal Register digest adapter

First Tier 1 legal adapter for digest. Keyless JSON, official rulemaking record, VERIFIED credibility tier.

- `agents/digest/src/digest/adapters/federalregister.py` (~150 lines)
- 24 tests, no mocks (synthetic API-shape dicts following the polymarket pattern)
- Wired into adapter registry, `credibility.SOURCE_TIERS` (VERIFIED), `credibility._per_item_bonus`, and `ranking.PLATFORM_WEIGHTS` (1.2)
- Discovered SPECS.md inaccuracy: `comment_count` is NOT a valid field on the list endpoint (returns 400) -- only available on per-document detail endpoint. Switched engagement signal to `page_views.count`. SPECS.md corrected.
- Full digest suite: 272 tests pass (was 248)
- Live API smoke-tested end-to-end

### 2026-05-13 -- Paul Graham voice profiles + corpus

Expanded the `voice` skill from 1 author to 4 by adding three era-specific PG profiles grounded in all 229 of his essays.

- 3 voice profiles: `pg-early.md` (2001-2004, 35 essays), `pg-startup.md` (2005-2015, 135 essays), `pg-late.md` (2016-present, 60 essays)
- All anchors verbatim from source files, spot-checked. Each profile follows `voice-template.md` (8 mandatory sections, ~90 lines, matching Chapman density)
- Built local research corpus at `corpus/pg-essays/`: `_fetch_pg.py` (stdlib parallel HTML→text fetcher), `_slugs.txt`, README. Essay text gitignored for copyright; corpus rebuilds in ~60s
- SKILL.md updated: Available voices table, blend invocation examples, reading guide
- Methodology: 1 inventory agent + 10 foreground reader/analyst agents (background sub-agents blocked by sandbox), 3 era syntheses
- Lint passes

### 2026-04-19 -- Skill benchmark harness

Built `benchmarks/skill-bench.py` to empirically measure whether skills improve Claude's output. AST-based pattern detection (no mocks, no manual eval). Autoresearch-compatible METRIC output.

- Benchmark harness: Typer CLI with `compare` (API) and `evaluate` (offline) commands
- Python-patterns suite: 5 tasks (pathlib, type hints, pydantic, comprehensions, context managers), 15 AST checks
- Dry run validated: 0/15 no-context vs 15/15 droo-stack (live run pending API key)
- Designed autoresearch integration: mutable file = skill markdown, verify = skill-bench, guard = skills-lint

### 2026-04-18 -- Skill audit, consolidation, framework improvements

52 skills, 8 agents + shared, 771 tests, 0 lint errors.

- Consolidated 53 -> 50 -> 52: merged overlaps, added property-testing + refactoring-strategy
- Extracted patterns from taste-skill (persona priming) and superpowers-marketplace (verification-before-completion)
- Shared abstractions (agents/shared/), CI (GitHub Actions, Python 3.10/3.12), 30 CLI integration tests
- Skill quality: "What You Get" enforced (52/52), structural splits, anti-pattern examples, argument-hints

### 2026-04-10..16 -- Foundation

- 8 agents with MCP servers (31 tools), 11 digest adapters, SQLite FTS5 recall
- Scribe agent (114 tests), AARTS hooks (136 tests), proactive triggers
- Skill splits, output sections, 40+ skills across 6 extraction phases
