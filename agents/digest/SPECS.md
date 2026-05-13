# Digest Adapter Specs

API reference for implementing new digest adapters across research, medical, legal, and security domains.

## How to Use This Document

Each adapter spec maps directly to the implementation touchpoints below. Read the spec, follow the pattern in an existing adapter (e.g., `reddit.py` for simple JSON APIs, `ethresearch.py` for forum-style APIs, `packages.py` for multi-source adapters).

### Implementation Checklist (per adapter)

1. **Create** `src/digest/adapters/{key}.py` -- adapter class with `name` and `fetch()`
2. **Edit** `src/digest/adapters/__init__.py` -- import + add to `ADAPTERS` dict
3. **Edit** `src/digest/credibility.py` -- add to `SOURCE_TIERS` + `_per_item_bonus()` case
4. **Edit** `src/digest/ranking.py` -- add to `PLATFORM_WEIGHTS`
5. **Edit** `src/digest/expansion.py` -- add platform-specific `ExpandedQuery` fields if needed
6. **Create** `tests/test_{key}.py` -- unit tests for `_build_item()` + engagement + edge cases

### Adapter Protocol

```python
class Adapter(Protocol):
    name: str
    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]: ...
```

### Item Model

```python
class Item(BaseModel):
    source: str          # adapter key ("hn", "pubmed", etc.)
    title: str
    url: str
    author: str | None
    timestamp: datetime
    engagement: int      # normalized engagement score (log-scaled in ranking)
    summary: str | None  # platform-specific summary text
    raw: dict[str, Any]  # source-specific data read by credibility._per_item_bonus()
```

### Common Patterns

- Auth: `os.environ.get("KEY_NAME", "")`, return `[]` if missing and required
- HTTP: `httpx.get(..., timeout=30.0)`
- Per-term limits: `per_term_limit = max(limit // max(len(terms), 1), 10)`
- Dedupe: `seen: dict[str, Item]` keyed by platform-specific ID within `fetch()`
- Build: private `_build_item()` method converts API response to `Item`

---

## Research Adapters

### arxiv

| Field | Value |
|-------|-------|
| Adapter key | `arxiv` |
| Base URL | `http://export.arxiv.org/api/query` |
| Auth | None |
| Rate limit | 1 req / 3 seconds (per-client, not per-key) |
| Format | Atom XML (namespace `http://www.w3.org/2005/Atom`) |
| Credibility tier | DELIBERATE |
| Platform weight | 2.0 |
| Priority | T2 |

**Search endpoint:**

```
GET http://export.arxiv.org/api/query
  ?search_query=all:{term}
  &start=0
  &max_results={limit}
  &sortBy=submittedDate
  &sortOrder=descending
```

Query field prefixes: `ti:` (title), `au:` (author), `abs:` (abstract), `cat:` (category, e.g. `cs.CR`). Combine with `AND`, `OR`, `ANDNOT`.

**Engagement mapping:** None. arXiv provides zero citation, download, or view counts. As standalone, set `engagement = 0` and rely on recency. When paired with Semantic Scholar (composite mode), use S2 `citationCount`.

**Raw dict fields:** `arxiv_id`, `categories`, `primary_category`, `pdf_url`, `authors`, `comment`

**Dedupe key:** `arxiv_id` (e.g., `2401.12345`)

**Per-item bonus:** None standalone. If enriched with S2, use S2 bonus rules.

**Implementation notes:**
- XML-only -- use `xml.etree.ElementTree` with Atom namespace
- 3-second rate limit is hard-enforced, must sleep between requests
- Use `published` timestamp (not `updated`) for recency scoring
- Pagination unreliable past offset 1000
- RSS feed (`http://export.arxiv.org/rss/cs.AI`) only shows daily new submissions, not search results
- Consider composite: search arXiv, then batch-enrich via S2 `GET /paper/arXiv:{id}` for citations
- Consider adding `arxiv_categories: list[str]` to `ExpandedQuery` for category-scoped searches
- ID parsing: use non-greedy regex `r"/abs/(.+?)(?:v\d+)?$"` to handle both modern IDs (`2401.12345v3`) and pre-2007 IDs (`cs.LG/0701234v2`)
- Title and summary fields contain inline newlines/indentation -- collapse whitespace before storage
- `arxiv:comment` is optional but useful (often contains venue: "Accepted at NeurIPS 2025")
- Implemented in `agents/digest/src/digest/adapters/arxiv.py` (2026-05-13)

---

### semanticscholar

| Field | Value |
|-------|-------|
| Adapter key | `semanticscholar` |
| Base URL | `https://api.semanticscholar.org/graph/v1` |
| Auth | Optional `S2_API_KEY` env var, header `x-api-key` |
| Rate limit | 1 RPS with key, ~100 req/5min without |
| Format | JSON |
| Credibility tier | DELIBERATE |
| Platform weight | 2.5 |
| Priority | T1 |

**Search endpoint:**

```
GET /paper/search
  ?query={term}
  &offset=0
  &limit={limit}
  &fields=title,url,authors,year,citationCount,influentialCitationCount,citationVelocity,tldr,externalIds,publicationDate,venue,openAccessPdf
```

Bulk search (supports sorting, cheaper):

```
GET /paper/search/bulk
  ?query={term}
  &sort=citationCount:desc
  &fields=title,year,citationCount,publicationDate
```

Single paper by arXiv ID (for composite enrichment):

```
GET /paper/arXiv:{arxiv_id}
  ?fields=citationCount,influentialCitationCount,citationVelocity,tldr
```

Batch lookup (POST, up to 500 IDs):

```
POST /paper/batch
  ?fields=citationCount,influentialCitationCount,tldr
Body: {"ids": ["arXiv:2401.12345", "DOI:10.1234/..."]}
```

**Engagement mapping:** `citationCount + influentialCitationCount * 5`

**Raw dict fields:** `paperId`, `citationCount`, `influentialCitationCount`, `citationVelocity`, `tldr`, `year`, `externalIds`, `venue`, `openAccessPdf`

**Dedupe key:** `paperId`

**Per-item bonus:**
- `influentialCitationCount > 50` -> 0.4
- `influentialCitationCount > 10` -> 0.2

**Implementation notes:**
- Default response returns almost nothing -- must explicitly request `fields=`
- `tldr` field provides AI-generated summary -- use as `Item.summary`. **Only available on `/paper/search`, NOT on `/paper/search/bulk`** (bulk returns 400 "Unrecognized or unsupported fields: [tldr]")
- `externalIds` contains `ArXiv`, `DOI`, `PubMed`, `SSRN`, `DBLP`, `MAG`, `CorpusId` -- useful for cross-adapter dedup
- `openAccessPdf` is often `{url: "", status: null, license: null}` for closed-access papers -- treat empty-string url as None
- Batch endpoint (`POST /paper/batch`) is essential for composite enrichment (avoid 1 RPS per-paper)
- **Unauthenticated rate limit is severe in practice**: nominally ~100 req/5min but bursty calls hit 429 within seconds and the cooldown is long (multiple minutes from the same IP). The adapter MUST soft-fail on 429: return [] for the failing term and continue with other terms rather than crashing.
- 1 RPS authenticated limit is strict but predictable -- set `S2_API_KEY` for any real usage
- `/paper/search` has no native publication-date filter; client-side filter on `publicationDate` (format `YYYY-MM-DD`)
- Some papers have `publicationDate: null` but a `year` -- fall back to year midpoint (July 1) for timestamp
- Covers ~215M papers, gaps in humanities/social sciences
- Can resolve SSRN papers via `externalIds.SSRN`
- Implemented in `agents/digest/src/digest/adapters/semanticscholar.py` (2026-05-13)

---

### openalex

| Field | Value |
|-------|-------|
| Adapter key | `openalex` |
| Base URL | `https://api.openalex.org` |
| Auth | Required since Feb 2025. Free key via `OPENALEX_EMAIL` env var (polite pool, header `mailto:{email}`) or `OPENALEX_API_KEY` (param `api_key`) |
| Rate limit | 100k credits/day (search = 10 credits), max 10 req/s |
| Format | JSON |
| Credibility tier | DELIBERATE |
| Platform weight | 2.0 |
| Priority | T2 |

**Search endpoint:**

```
GET /works
  ?search={term}
  &filter=from_publication_date:{since_date}
  &sort=publication_date:desc
  &per_page={limit}
  &select=id,doi,title,cited_by_count,counts_by_year,fwci,type,open_access,authorships,publication_date
```

Semantic search: `?search.semantic={term}` (AI-powered meaning-based search).

Filter combos: `cited_by_count:>50`, `type:article`, `open_access.is_oa:true`, `topics.id:T456`.

**Engagement mapping:** `cited_by_count`

**Raw dict fields:** `id`, `doi`, `cited_by_count`, `counts_by_year`, `fwci`, `type`, `open_access`, `concepts`, `authorships`

**Dedupe key:** `id` (OpenAlex work ID, e.g. `W1234567890`)

**Per-item bonus:**
- `fwci > 3.0` -> 0.4 (3x field average)
- `fwci > 1.0` -> 0.2 (above field average)

**Implementation notes:**
- 470M+ works (broadest coverage of any free API)
- `fwci` (field-weighted citation impact) > 1.0 means above average for its field; `null` for too-new papers -- preserve as `None`, do not coerce to 0.0
- `counts_by_year` shows citation trajectory -- useful for trend detection in differential digests
- `concepts` field enables automatic topic classification; concept `id` is a URL -- store the trailing segment (e.g. `C2776760102`)
- Can resolve SSRN papers via DOI or title search (SSRN has no API)
- XPAC works (190M+ additional records) excluded by default -- add `include_xpac=true` for full coverage
- Credit system: list/search = 10 credits each, entity lookup = 1 credit
- **Auth is not strictly required in practice** despite the docs' "Required since Feb 2025" note -- anonymous requests still succeed, just with lower rate limit. Adapter precedence: `OPENALEX_API_KEY` (api_key param) > `OPENALEX_EMAIL` (mailto param, polite pool) > anonymous.
- DOIs come back as full URLs (`https://doi.org/10.1234/...`); normalize bare DOIs to the URL form for consistency.
- `id` field is `https://openalex.org/W1234567890`; dedupe key is the trailing `W…` segment.
- `select=` param is essential -- default response is ~30KB per item; the adapter requests only the 11 fields it uses.
- Implemented in `agents/digest/src/digest/adapters/openalex.py` (2026-05-13)
- `select` parameter is critical for performance -- always specify only needed fields

---

### crossref

| Field | Value |
|-------|-------|
| Adapter key | `crossref` |
| Base URL | `https://api.crossref.org` |
| Auth | None. Polite pool via `CROSSREF_EMAIL` env var (header `mailto:{email}`) |
| Rate limit | ~50 req/s in polite pool |
| Format | JSON |
| Credibility tier | DELIBERATE |
| Platform weight | 1.5 |
| Priority | T3 |

**Search endpoint:**

```
GET /works
  ?query={term}
  &filter=from-pub-date:{since_date}
  &sort=is-referenced-by-count
  &order=desc
  &rows={limit}
  &select=DOI,title,is-referenced-by-count,type,publisher,subject,published,author
  &mailto={email}
```

Deep pagination: use `cursor=*` and follow `next-cursor` in response.

**Engagement mapping:** `is-referenced-by-count`

**Raw dict fields:** `DOI`, `is-referenced-by-count`, `type`, `publisher`, `subject`, `license`

**Dedupe key:** DOI

**Per-item bonus:** None (citation counts from Crossref skew toward traditional publishing).

**Implementation notes:**
- Metadata-only search (no abstracts or full text) -- search quality is worse than S2/OpenAlex for topical queries
- Response nested under `message.items`
- Citation counts only reflect Crossref-registered citations (misses preprints, theses)
- Always use `mailto` -- without it you share the public pool with bots
- Max 1000 rows per request
- Best used as secondary enrichment (DOI resolution, publisher metadata) rather than primary search
- 160M+ records, strongest for DOI resolution

---

### SSRN (routing note -- no adapter)

SSRN has no public API. Elsevier (owner since 2016) does not expose structured endpoints.

**Recommended routing:**
1. **OpenAlex** -- search by title or DOI. SSRN is one of their top indexed sources.
2. **Semantic Scholar** -- `externalIds.SSRN` field identifies SSRN papers. Search by keyword returns SSRN preprints.
3. **Scopus API** (Elsevier) -- requires institutional API key. Returns SSRN metadata via DOI.
4. **RSS feeds** -- per-author and per-series feeds exist on ssrn.com for new-paper alerts.

No dedicated adapter needed. OpenAlex and Semantic Scholar adapters cover SSRN content.

---

## Medical Adapters

### pubmed

| Field | Value |
|-------|-------|
| Adapter key | `pubmed` |
| Base URL | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` |
| Auth | Optional `NCBI_API_KEY` env var (param `api_key`) |
| Rate limit | 3 req/s without key, 10 req/s with key |
| Format | JSON (esearch, esummary) + XML (efetch) |
| Credibility tier | DELIBERATE |
| Platform weight | 2.5 |
| Priority | T1 |

**Two-step fetch:**

Step 1 -- search for PMIDs:

```
GET /esearch.fcgi
  ?db=pubmed
  &term={term}
  &retmax={limit}
  &sort=date
  &datetype=pdat
  &mindate={since_date}
  &retmode=json
  &api_key={key}
```

Returns `esearchresult.idlist` (array of PMID strings).

Step 2 -- fetch summaries:

```
GET /esummary.fcgi
  ?db=pubmed
  &id={pmid1},{pmid2},...
  &retmode=json
  &api_key={key}
```

Returns `result.{pmid}.title`, `.sortpubdate`, `.source` (journal), `.authors`, `.pubtype`.

Step 3 (optional) -- enrich with citation data via iCite:

```
GET https://icite.od.nih.gov/api/pubs
  ?pmids={pmid1},{pmid2},...
  &fl=pmid,citation_count,relative_citation_ratio,cited_by_clin,is_clinical
```

**Engagement mapping:** `citation_count` from iCite (0 if iCite step skipped)

**Raw dict fields:** `pmid`, `doi`, `journal`, `pub_types`, `citation_count`, `relative_citation_ratio`, `is_clinical`, `mesh_terms`

**Dedupe key:** PMID

**Per-item bonus:**
- `relative_citation_ratio > 5.0` -> 0.4
- `relative_citation_ratio > 1.0` -> 0.2
- `is_clinical == true` -> +0.1

**Implementation notes:**
- Use esummary (JSON) instead of efetch (XML-only) for metadata -- simpler parsing
- iCite enrichment is optional but highly valuable -- adds citation_count + relative_citation_ratio
- iCite accepts batches of PMIDs (comma-separated), no auth needed
- iCite returns `relative_citation_ratio: null` for too-new papers (no citation field yet) -- preserve as `None`, not `0.0`, so per-item bonus can distinguish "uncited" from "not scored"
- `sortpubdate` format is `YYYY/MM/DD HH:MM` (with time) or `YYYY/MM/DD` -- accept both
- DOI is buried in `articleids` list as `{idtype: "doi", value: "..."}` -- not a top-level field
- `retmax` caps at 10,000 -- use WebEnv/QueryKey for larger result sets
- MeSH terms enable precise medical topic filtering
- Consider adding `pubmed_mesh: list[str]` to `ExpandedQuery`
- 36M+ abstracts indexed
- Implemented in `agents/digest/src/digest/adapters/pubmed.py` (2026-05-13)

---

### biorxiv

| Field | Value |
|-------|-------|
| Adapter key | `biorxiv` |
| Base URL | `https://api.biorxiv.org/` |
| Auth | None |
| Rate limit | Undocumented (~1 req/s safe) |
| Format | JSON |
| Credibility tier | PASSIVE |
| Platform weight | 0.8 |
| Priority | T3 |

**Search endpoint:** None. Date-range browsing only.

```
GET /details/{server}/{from_date}/{to_date}/{cursor}
```

- `server`: `biorxiv` or `medrxiv`
- Dates: `YYYY-MM-DD`
- Returns 100 results per page, paginate with cursor (0, 100, 200, ...)
- Response: `collection[]` with `doi`, `title`, `authors`, `abstract`, `date`, `category`, `version`, `published`

**Engagement mapping:** None from API. Set `engagement = version` (more revisions = community interest). If `published` is non-null, set `engagement += 10` (accepted by journal = strong quality signal).

**Raw dict fields:** `doi`, `category`, `author_corresponding`, `version`, `type`, `published`

**Dedupe key:** DOI

**Per-item bonus:** None (no engagement data available).

**Implementation notes:**
- **No search endpoint.** Must fetch by date range and filter client-side by term matching in title/abstract.
- For narrow topics, this yields many irrelevant results -- high API cost for low yield.
- **Preferred workaround:** Use Semantic Scholar search with `venue:bioRxiv` or `venue:medRxiv` filter instead.
- Keep this adapter for "what's new in preprints" broad date scans only.
- `published` field (non-null = accepted by journal) is the strongest quality signal.
- Category filtering: append `?category=cell_biology` to endpoint.

---

### clinicaltrials

| Field | Value |
|-------|-------|
| Adapter key | `clinicaltrials` |
| Base URL | `https://clinicaltrials.gov/api/v2/` |
| Auth | None |
| Rate limit | ~50 req/min |
| Format | JSON (deeply nested) |
| Credibility tier | VERIFIED |
| Platform weight | 1.5 |
| Priority | T2 |

**Search endpoint:**

```
GET /studies
  ?query.term={term}
  &pageSize={limit}
  &sort=LastUpdatePostDate:desc
  &countTotal=true
  &format=json
```

Filter examples: `filter.overallStatus=RECRUITING`, `filter.phase=PHASE3`, `query.cond={condition}`, `query.intr={intervention}`.

Pagination: opaque `nextPageToken` (not offset-based).

**Engagement mapping:** `enrollment_count + phase_score` where phase_score: Phase 4 = 40, Phase 3 = 30, Phase 2 = 20, Phase 1 = 10, Early Phase 1 = 5, N/A = 0.

**Raw dict fields:** `nctId`, `phase`, `enrollmentCount`, `overallStatus`, `conditions`, `interventions`, `leadSponsor`, `startDate`

**Dedupe key:** `nctId`

**Per-item bonus:**
- Phase 3 or Phase 4 -> 0.4
- Phase 2 -> 0.2
- `enrollmentCount > 1000` -> 0.3

**Implementation notes:**
- Response is deeply nested: `studies[].protocolSection.{identificationModule,statusModule,designModule,...}`
- Extract fields via careful path traversal, not flat dict access
- `overallStatus` values: RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, TERMINATED, WITHDRAWN, SUSPENDED, NOT_YET_RECRUITING
- ISO 8601 dates, CommonMark markdown in text fields
- `totalCount` (with `countTotal=true`) indicates topic popularity
- Legacy v1 API retired June 2024 -- only v2 works
- **Use `urllib.request` not `httpx`**: the CT.gov edge WAF performs TLS fingerprinting and returns 403 to httpx (including when mimicking curl's exact headers). stdlib `urllib.request` passes through. This is the only adapter that needs the workaround.
- A trial can list multiple phases (`["PHASE1", "PHASE2"]`); the highest weight wins for engagement scoring (use a `_top_phase` helper).
- Dates can arrive as `YYYY-MM-DD`, `YYYY-MM`, or `YYYY` -- accept all three.
- `enrollmentInfo` may be missing entirely on early-registration trials; default to 0.
- Implemented in `agents/digest/src/digest/adapters/clinicaltrials.py` (2026-05-13)

---

### openfda

| Field | Value |
|-------|-------|
| Adapter key | `openfda` |
| Base URL | `https://api.fda.gov/` |
| Auth | Optional `OPENFDA_API_KEY` env var (param `api_key`) |
| Rate limit | 240 req/min with key, 40 req/min without |
| Format | JSON |
| Credibility tier | VERIFIED |
| Platform weight | 1.0 |
| Priority | T3 |

**Search endpoints (focus on drug adverse events first):**

```
GET /drug/event.json
  ?search={term}+AND+receivedate:[{since_YYYYMMDD}+TO+{now_YYYYMMDD}]
  &limit={limit}
```

Count endpoint (aggregate stats, no individual results):

```
GET /drug/event.json
  ?search={term}
  &count=patient.reaction.reactionmeddrapt.exact
```

Other datasets: `/drug/label.json`, `/drug/enforcement.json`, `/device/event.json`, `/food/enforcement.json`.

**Engagement mapping:** `meta.results.total` as volume signal (total matching adverse event reports). Per-item: `serious * 5 + len(reactions)`.

**Raw dict fields:** `safetyreportid`, `serious`, `seriousnessdeath`, `reactions`, `drugs`, `receivedate`, `primarysource_qualification`, `meta_total`

**Dedupe key:** `safetyreportid`

**Per-item bonus:**
- `serious == 1` -> 0.3
- `seriousnessdeath == 1` -> 0.5

**Implementation notes:**
- Date format is `YYYYMMDD` (not ISO) -- convert with `strftime("%Y%m%d")`
- `limit` max is 100 per call. No deep pagination -- use date-range windowing for bulk pulls.
- Reports are NOT deduplicated -- same event may appear in multiple reports
- No causal link between drugs and reactions in multi-drug reports
- Focus on drug/event first, expand to other sub-APIs later
- `primarysource.qualification` values: 1=Physician, 2=Pharmacist, 3=Other health professional, 5=Consumer -- use as credibility signal

---

### who

| Field | Value |
|-------|-------|
| Adapter key | `who` |
| Base URL | `https://www.who.int/api/emergencies/diseaseoutbreaknews` |
| Auth | None |
| Rate limit | Undocumented |
| Format | JSON (OData-style, HTML embedded in content fields) |
| Credibility tier | VERIFIED |
| Platform weight | 1.0 |
| Priority | T4 |

**Search endpoint:** No keyword search. Fetch all and filter client-side.

```
GET https://www.who.int/api/emergencies/diseaseoutbreaknews
  ?$orderby=PublicationDate desc
  &$top={limit}
```

OData filter syntax (undocumented, may not work): `$filter=contains(Title,'{term}')`.

**Engagement mapping:** None. Set `engagement = 1` (all WHO DONs are significant). Rank by recency only.

**Raw dict fields:** `Id`, `DonId`, `CountryName`, `DiseaseNames`, `PublicationDate`

**Dedupe key:** `DonId` (e.g., `DON588`)

**Per-item bonus:** None (all DONs are high-authority by default).

**Implementation notes:**
- No search/filter by topic -- must filter client-side by matching terms against `Title`, `DiseaseNames`
- Content fields (`Epidemiology`, `Assessment`, `Response`) contain raw HTML inside JSON strings -- strip tags for `Item.summary`
- Low volume: few dozen per month. Good for outbreak alerts, not broad digests.
- OData-style API -- filtering capabilities are poorly documented
- Consider: only useful in watch/alert mode for health topics

---

### cdc

| Field | Value |
|-------|-------|
| Adapter key | `cdc` |
| Base URL | `https://tools.cdc.gov/api/v2/resources/` |
| Auth | None |
| Rate limit | Undocumented |
| Format | JSON + RSS |
| Credibility tier | VERIFIED |
| Platform weight | 0.8 |
| Priority | T4 |

**Search endpoint:**

```
GET media
  ?topic={term}
  &sort=-datepublished
  &max={limit}
```

RSS feed (MMWR Weekly): `https://tools.cdc.gov/api/v2/resources/media/342778.rss`

Full content retrieval: `GET media/{id}/syndicate`

**Engagement mapping:** None reliable. Set `engagement = 1`. Rank by recency.

**Raw dict fields:** `id`, `name`, `mediaType`, `topics`, `datePublished`, `dateContentLastReviewed`

**Dedupe key:** `id`

**Per-item bonus:** None.

**Implementation notes:**
- MMWR publication schedule has been irregular (government funding lapses)
- Content is HTML embedded in JSON/RSS -- needs sanitization
- No full-text search of article bodies -- topic filter only
- MMWR articles are also indexed in PubMed -- may want to dedupe cross-adapter
- Low volume, high authority -- best for health alert digests

---

## Legal Adapters

### courtlistener

| Field | Value |
|-------|-------|
| Adapter key | `courtlistener` |
| Base URL | `https://www.courtlistener.com/api/rest/v4/` |
| Auth | Required. `COURTLISTENER_TOKEN` env var, header `Authorization: Token {key}` |
| Rate limit | 5,000 req/hr |
| Format | JSON |
| Credibility tier | DELIBERATE |
| Platform weight | 2.0 |
| Priority | T2 |

**Search endpoint:**

```
GET /search/
  ?q={term}
  &type=o
  &order_by=dateFiled desc
  &filed_after={since_date}
```

Search types: `o` = opinions, `r` = RECAP dockets, `oa` = oral arguments.

Supports Solr syntax in `q`: range queries `citeCount:[10 TO *]`, boolean `term1 AND term2`.

**Engagement mapping:** `citeCount` (how many times cited by other opinions)

**Raw dict fields:** `id`, `caseName`, `court`, `court_id`, `dateFiled`, `citeCount`, `citation`, `docketNumber`, `snippet`

**Dedupe key:** `id`

**Per-item bonus:**
- `citeCount > 100` -> 0.4
- `citeCount > 20` -> 0.2
- Supreme Court (`court_id` in `["scotus"]`) -> +0.3

**Implementation notes:**
- Free registration, generous rate limits
- `type=o` for case law, `type=r` for PACER docket entries
- Court hierarchy provides quality signal: SCOTUS > Circuit (ca1-ca11, cadc, cafc) > District
- Counts above 2,000 hits are approximate (~6% error)
- Fields use camelCase, not snake_case
- Pagination returns `next`/`previous` URLs
- Maintenance window: Thursdays 21:00-23:59 PT
- **Auth is not strictly required** in practice -- anonymous requests still work, just at a lower rate ceiling. Adapter sends `Authorization: Token` header only when `COURTLISTENER_TOKEN` is set.
- **Top-level `id` field does not exist** in the response despite the SPECS-listed "dedupe key: id" -- the canonical dedupe key is `cluster_id`. Multiple sibling opinions (concurring, dissenting) share one cluster, so deduping by `cluster_id` keeps one entry per case.
- `judge` is a string, not an array; multi-judge panels are semicolon-separated (e.g. `"Gibbons; Thapar; Larsen"`)
- `absolute_url` is relative (`/opinion/.../`) -- prepend the site base when building Item URLs
- `snippet` is `None` for results returned without highlighted matches
- Implemented in `agents/digest/src/digest/adapters/courtlistener.py` (2026-05-13)

---

### federalregister

| Field | Value |
|-------|-------|
| Adapter key | `federalregister` |
| Base URL | `https://www.federalregister.gov/api/v1/` |
| Auth | None |
| Rate limit | Undocumented, generous. Max 2,000 results per query. |
| Format | JSON |
| Credibility tier | VERIFIED |
| Platform weight | 1.2 |
| Priority | T1 |

**Search endpoint:**

```
GET /documents.json
  ?conditions[term]={term}
  &conditions[publication_date][gte]={since_date}
  &per_page={limit}
  &order=newest
  &fields[]=title,abstract,document_number,type,agencies,publication_date,page_views,significant,comments_close_on,html_url,regulations_dot_gov_url
```

Document types: `conditions[type][]=Rule`, `Proposed Rule`, `Notice`, `Presidential Document`.

**Engagement mapping:** `page_views.count + (50 if significant else 0)`

**Raw dict fields:** `document_number`, `type`, `page_views`, `significant`, `agencies`, `abstract`, `comments_close_on`, `regulations_dot_gov_url`

**Dedupe key:** `document_number`

**Per-item bonus:**
- `significant == true` -> 0.3
- `page_views > 10000` -> 0.4
- `page_views > 1000` -> 0.2

**Implementation notes:**
- No auth, clean JSON, well-documented -- easiest legal API to implement
- `fields[]` parameter is critical for performance -- always specify only needed fields
- `significant` flag (EO 12866) identifies economically important rules; usually `null`, occasionally `true`
- **`comment_count` is NOT a valid field on the list endpoint** -- the API returns 400. The comment count lives on the per-document detail endpoint nested under `dockets[].documents[].comment_count`. To use comment_count as engagement you would need a second API call per document. We use `page_views.count` instead -- noisier but available without an extra round-trip.
- `page_views` is returned as `{count: <int>, last_updated: <str>}` -- read `.count`
- `comments_close_on` date indicates active rulemaking (open deadlines = high engagement)
- `agencies` is an array of objects with `name` and `raw_name` -- extract first agency name for display
- Max 2,000 results per query -- use date-range windowing for larger pulls
- Cross-reference to regulations.gov via `regulations_dot_gov_url`
- Implemented in `agents/digest/src/digest/adapters/federalregister.py` (2026-05-13)

---

### regulations

| Field | Value |
|-------|-------|
| Adapter key | `regulations` |
| Base URL | `https://api.regulations.gov/v4/` |
| Auth | Required. `REGULATIONS_GOV_KEY` env var (from api.data.gov), header `X-Api-Key` |
| Rate limit | 1,000 req/hr |
| Format | JSON:API (data/attributes/relationships) |
| Credibility tier | DELIBERATE |
| Platform weight | 1.5 |
| Priority | T3 |

**Search endpoint:**

```
GET /documents
  ?filter[searchTerm]={term}
  &filter[postedDate][ge]={since_date}
  &page[size]={limit}
  &sort=-postedDate
```

Filter additions: `filter[documentType]=Proposed Rule`, `filter[agencyId]=EPA`.

**Engagement mapping:** `numberOfCommentsReceived` (from document detail endpoint, requires second call)

**Raw dict fields:** `documentId`, `documentType`, `agencyId`, `docketId`, `numberOfCommentsReceived`, `openForComment`, `commentEndDate`

**Dedupe key:** `documentId`

**Per-item bonus:**
- `numberOfCommentsReceived > 10000` -> 0.4
- `numberOfCommentsReceived > 1000` -> 0.2
- `openForComment == true` -> +0.1

**Implementation notes:**
- JSON:API format: data under `data[].attributes`, not flat
- Comment count requires fetching document detail (second API call per item) -- batch or limit
- `objectId` (internal) needed for comment lookup, not `documentId`
- Max 5,000 results (250 per page, 20 pages) -- paginate with `lastModifiedDate` windowing for bulk
- `DEMO_KEY` exists for testing but is severely rate-limited
- Staging API at `api-staging.regulations.gov`

---

### congress

| Field | Value |
|-------|-------|
| Adapter key | `congress` |
| Base URL | `https://api.congress.gov/v3/` |
| Auth | Required. `CONGRESS_API_KEY` env var (param `api_key`) |
| Rate limit | 5,000 req/hr, max 250 results per page |
| Format | JSON (append `&format=json`, default is XML) |
| Credibility tier | DELIBERATE |
| Platform weight | 1.5 |
| Priority | T2 |

**Search endpoint:**

```
GET /bill
  ?query={term}
  &fromDateTime={since_datetime}
  &sort=updateDate+desc
  &limit={limit}
  &format=json
  &api_key={key}
```

Cosponsor count (second call per bill):

```
GET /bill/{congress}/{type}/{number}/cosponsors
  ?format=json
  &api_key={key}
```

Bill types: `hr` (House), `s` (Senate), `hjres`, `sjres`, `hconres`, `sconres`, `hres`, `sres`.

**Engagement mapping:** `cosponsor_count * 2 + action_count`. Cosponsors require a second API call -- batch or limit to top N bills.

**Raw dict fields:** `billNumber`, `billType`, `congress`, `latestAction`, `cosponsor_count`, `committees`, `title`, `updateDate`

**Dedupe key:** `{congress}-{billType}-{billNumber}` (e.g., `119-hr-1234`)

**Per-item bonus:**
- Cosponsor count > 50 -> 0.4
- Cosponsor count > 10 -> 0.2

**Implementation notes:**
- **Always append `&format=json`** -- default is XML
- Cosponsor count requires second call per bill -- expensive. Consider: fetch top N bills, enrich only those.
- `latestAction.text` provides status summary (e.g., "Passed House", "Signed by President")
- Action progression is a quality signal: further along = more significant
- Historical data before 43rd Congress lacks sponsors/cosponsors/amendments
- Empty elements are suppressed (not null) -- check for key existence
- No full-text search of bill content -- search by subject terms or titles only

---

### eurlex

| Field | Value |
|-------|-------|
| Adapter key | `eurlex` |
| Base URL | `https://publications.europa.eu/webapi/rdf/sparql` |
| Auth | None |
| Rate limit | 60-second query timeout, ~5 concurrent requests |
| Format | SPARQL results (XML or JSON) |
| Credibility tier | VERIFIED |
| Platform weight | 1.0 |
| Priority | T4 |

**Query method:** POST with `query` parameter containing SPARQL.

```sparql
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex ?title ?date WHERE {
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_document ?date .
  ?exp cdm:expression_belongs_to_work ?work .
  ?exp cdm:expression_title ?title .
  ?exp cdm:expression_uses_language
    <http://publications.europa.eu/resource/authority/language/ENG> .
  FILTER(CONTAINS(LCASE(?title), "{term_lower}"))
  FILTER(?date >= "{since_date}"^^xsd:date)
} ORDER BY DESC(?date) LIMIT {limit}
```

**Engagement mapping:** Citation count via `cdm:work_cited_by` relationship count (requires additional query). Default: `engagement = 1`.

**Raw dict fields:** `celex_number`, `title`, `date`, `resource_type`, `in_force`

**Dedupe key:** CELEX number

**Per-item bonus:** None practical (citation graph query is expensive).

**Implementation notes:**
- SPARQL is complex -- template the query with f-string substitution
- 60s timeout means queries must be focused (always use FILTER + LIMIT)
- Unbound variables cause full-scan timeouts -- never leave variables unbound
- CELEX numbers are not 1:1 with acts (consolidated texts, corrigenda get separate CELEX)
- CDM ontology: `cdm:resource_legal_in-force` distinguishes live law from repealed
- Document type hierarchy: Regulations > Directives > Decisions
- Lower priority due to SPARQL complexity and niche audience

---

### uklegislation

| Field | Value |
|-------|-------|
| Adapter key | `uklegislation` |
| Base URL | `https://www.legislation.gov.uk/` |
| Auth | None |
| Rate limit | Undocumented |
| Format | Atom XML |
| Credibility tier | VERIFIED |
| Platform weight | 0.8 |
| Priority | T4 |

**Search endpoint:**

```
GET /search
  ?text={term}
  &start-year={since_year}
  &results-count={limit}
```

Append `/data.feed` to get Atom XML (without it, returns HTML).

Effects (amendments) per legislation:

```
GET /changes/affected/{type}/{year}/{number}/data.feed
```

Legislation types: `ukpga` (Public General Acts), `uksi` (Statutory Instruments), `asp` (Scottish), `eur` (retained EU law).

**Engagement mapping:** Effects count (number of amendments applied) from `/changes/affected/` sub-resource. Default: `engagement = 1` (avoid second call unless enriching).

**Raw dict fields:** `id`, `title`, `type`, `year`, `number`, `effects_count`, `extent`

**Dedupe key:** legislation identifier (e.g., `ukpga/2024/1`)

**Per-item bonus:** None practical.

**Implementation notes:**
- **Atom XML only** -- no JSON output. Needs XML parser (shared with arXiv).
- CORS only on `/data.xml` and `/data.feed` paths
- Effects count from `/changes/` endpoints is the best engagement proxy (more amendments = more legislative significance)
- `extent` (geographic applicability: E+W, S, NI) is metadata, not engagement
- Experimental Lex API at `lex.lab.i.ai.gov.uk` offers Parquet bulk downloads (updated weekly)
- Lower priority for non-UK-focused digests

---

## Security Enhancements

### Shodan (existing adapter enhancements)

The `shodan` adapter is already implemented. These are enhancement specs.

**InternetDB fallback** (free, keyless):

```
GET https://internetdb.shodan.io/{ip}
```

Returns: `{"ip": "1.2.3.4", "ports": [80, 443], "vulns": ["CVE-..."], "cpes": [...], "hostnames": [...], "tags": [...]}`

- Use when `SHODAN_API_KEY` is unset for IP-specific lookups
- Updated weekly (stale vs main API's real-time)
- Rate limit: undocumented but higher than main API. Bans IP on abuse (~1 hour).

**Facets endpoint** (free, unlimited, no query credits):

```
GET https://api.shodan.io/shodan/host/count
  ?key={key}
  &query={term}
  &facets=org:10,country:10,port:10,vuln:10,product:10
```

Returns total count + top facet values with counts. Zero query credits consumed.

Available facets: `org`, `domain`, `port`, `asn`, `country`, `city`, `os`, `product`, `version`, `ssl.version`, `vuln`. Append `:N` to limit top values.

**Exploits API** (separate base URL):

```
GET https://exploits.shodan.io/api/search
  ?query={term}
  &key={key}
```

Filters: `author`, `cve`, `platform`, `port`, `type`. Returns: `_id`, `cve[]`, `description`, `source` (ExploitDB, Metasploit, etc.).

Also: `GET /api/count?query={term}` for totals without results.

**Enhancement implementation:**
- Add `_search_internetdb(ip)` method as fallback in `fetch()` when `_api_key` is empty
- Add `facet_summary(query)` method for aggregate exposure stats
- Consider exploits as separate enrichment step (different base URL, different data shape)

**Implementation status (2026-05-13):**
- InternetDB fallback: **done**. Keyless `fetch()` routes IP-shaped query terms (parsed via `ipaddress.ip_address`) to `internetdb.shodan.io/{ip}`. CIDR notation and partial IPs are skipped. Non-IP terms return `[]` since InternetDB has no search.
- Facets endpoint: **done**. Authenticated `fetch()` follows each `/shodan/host/search` with a `/shodan/host/count` call requesting `org:10,country:10,port:10,vuln:10,product:10`. Emits one aggregate `Item` per query term with `raw.kind="facet_summary"`, `engagement=total`, and `raw.facets` containing the normalized facet values.
- Exploits API: not yet wired -- would require CVE-pattern detection in query terms and a new code path against `exploits.shodan.io/api/search`.
- See `agents/digest/src/digest/adapters/shodan.py`.

---

## Summary Table

| Key | Domain | Auth | Rate Limit | Engagement Signal | Tier | Weight | Format | Priority |
|-----|--------|------|------------|-------------------|------|--------|--------|----------|
| **Existing** | | | | | | | | |
| hn | Tech | None | None | points + comments | DELIBERATE | 2.0 | JSON | -- |
| github | Tech | gh CLI | 5000/hr | stars + forks + issues | DELIBERATE | 1.0 | JSON | -- |
| reddit | Tech | None | ~10/min | score + comments | DELIBERATE | 1.5 | JSON | -- |
| youtube | Tech | yt-dlp | None | views + likes | PASSIVE | 0.5 | JSON | -- |
| ethresearch | Web3 | None | None | views + likes + posts | DELIBERATE | 2.5 | JSON | -- |
| snapshot | Web3 | None | None | votes + scores | VERIFIED | 1.5 | JSON | -- |
| polymarket | Web3 | None | None | volume traded | VERIFIED | 0.8 | JSON | -- |
| packages | Tech | None | None | downloads | PASSIVE | 0.3 | JSON | -- |
| coingecko | Web3 | None | 30/min | market cap rank | PASSIVE | 0.4 | JSON | -- |
| blockscout | Web3 | None | None | tx value | VERIFIED | 1.2 | JSON | -- |
| shodan | Security | SHODAN_API_KEY | 1/s | vulns + tags | DELIBERATE | 1.0 | JSON | -- |
| **Research** | | | | | | | | |
| semanticscholar | Research | S2_API_KEY (opt) | 1 RPS | citations + influential | DELIBERATE | 2.5 | JSON | T1 |
| pubmed | Medical | NCBI_API_KEY (opt) | 10/s | citations (via iCite) | DELIBERATE | 2.5 | JSON+XML | T1 |
| arxiv | Research | None | 1/3s | none (pair with S2) | DELIBERATE | 2.0 | XML | T2 |
| openalex | Research | OPENALEX_EMAIL | 10/s | cited_by_count + fwci | DELIBERATE | 2.0 | JSON | T2 |
| crossref | Research | CROSSREF_EMAIL (opt) | 50/s | is-referenced-by-count | DELIBERATE | 1.5 | JSON | T3 |
| **Medical** | | | | | | | | |
| clinicaltrials | Medical | None | 50/min | enrollment + phase | VERIFIED | 1.5 | JSON | T2 |
| openfda | Medical | OPENFDA_API_KEY (opt) | 240/min | report count + serious | VERIFIED | 1.0 | JSON | T3 |
| biorxiv | Medical | None | ~1/s | none (version count) | PASSIVE | 0.8 | JSON | T3 |
| who | Medical | None | Unknown | none (recency only) | VERIFIED | 1.0 | JSON | T4 |
| cdc | Medical | None | Unknown | none (recency only) | VERIFIED | 0.8 | JSON+RSS | T4 |
| **Legal** | | | | | | | | |
| federalregister | Legal | None | Generous | comment_count + significant | VERIFIED | 1.2 | JSON | T1 |
| courtlistener | Legal | COURTLISTENER_TOKEN | 5000/hr | citeCount | DELIBERATE | 2.0 | JSON | T2 |
| congress | Legal | CONGRESS_API_KEY | 5000/hr | cosponsors + actions | DELIBERATE | 1.5 | JSON | T2 |
| regulations | Legal | REGULATIONS_GOV_KEY | 1000/hr | comment count | DELIBERATE | 1.5 | JSON:API | T3 |
| openfda | Legal/Med | OPENFDA_API_KEY (opt) | 240/min | report count | VERIFIED | 1.0 | JSON | T3 |
| eurlex | Legal | None | 60s timeout | citation graph | VERIFIED | 1.0 | SPARQL | T4 |
| uklegislation | Legal | None | Unknown | effects count | VERIFIED | 0.8 | XML | T4 |

## Implementation Order

### Tier 1 -- High value, clean APIs (implement first)

1. **semanticscholar** -- richest engagement signals (citations, influential citations, velocity), JSON, TLDR summaries, covers SSRN content. Best research adapter.
2. **pubmed** -- medical cornerstone, 36M+ abstracts, pairs with cancer-predisposition skill. iCite enrichment adds citation data.
3. **federalregister** -- no auth needed, clean JSON, comment counts + significance flags. Easiest legal API.
4. **Shodan enhancements** -- existing adapter, low effort. InternetDB fallback + facets endpoint.

### Tier 2 -- Good value, moderate complexity

5. **arxiv** -- XML parsing required. Best as composite with S2 for citation enrichment.
6. **openalex** -- broadest academic coverage (470M works), FWCI normalization, SSRN routing. Requires email for polite pool.
7. **courtlistener** -- clean JSON API with citation counts. Free token registration.
8. **clinicaltrials** -- deeply nested JSON but high value for medical/pharma topics.
9. **congress** -- cosponsor count needs second API call. Valuable for policy monitoring.

### Tier 3 -- Niche or complex

10. **crossref** -- secondary enrichment for DOI resolution. Lower search quality than S2/OpenAlex.
11. **regulations** -- JSON:API format adds parsing complexity. Free key from api.data.gov.
12. **openfda** -- multiple sub-APIs, non-standard date format. Start with drug/event only.
13. **biorxiv** -- no search API. Prefer S2 `venue:bioRxiv` filter for search; keep native for date scans.

### Tier 4 -- Complex format or low volume

14. **who** -- no search, HTML in JSON, low volume. Best for watch/alert mode only.
15. **cdc** -- irregular publication, no engagement signals. Niche.
16. **eurlex** -- SPARQL adds significant complexity. Niche EU-focused.
17. **uklegislation** -- XML only, niche UK-focused.
