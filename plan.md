# CopyGuard Discovery Service — Technical Design & Execution Plan

## 1) System Architecture Diagram (text format)

```text
[Client / API Consumer]
          |
          v
  [FastAPI Router Layer]
          |
          v
 [Discovery Orchestrator Service]
    |           |            |
    |           |            +--> [Candidate Ranker]
    |           |
    |           +--> [Content Pipeline]
    |                 |- URL Fetcher (HTTP client)
    |                 |- Article Extractor (Trafilatura)
    |                 |- Normalizer/Cleaner
    |
    +--> [Query Generation Engine]
              |
              v
     [Google Custom Search Client]
              |
              v
      [Candidate URL Collector]

Shared support modules:
- Config & Secrets Manager
- Validation Schemas (Pydantic)
- Rate Limiter / Retry Policy
- Structured Logging + Tracing
- Optional Persistence (SQLite/Postgres) for job/candidate metadata
```

---

## 2) Proposed Folder Structure

```text
backend/
  app/
    main.py
    api/
      routes_discovery.py
      dependencies.py
    core/
      config.py
      logging.py
      errors.py
      rate_limit.py
    models/
      request.py
      response.py
      domain.py
    services/
      discovery_orchestrator.py
      query_generator.py
      google_search_client.py
      url_collector.py
      content_fetcher.py
      extractor.py
      normalizer.py
      candidate_ranker.py
    repositories/
      job_repository.py
      candidate_repository.py
    clients/
      google_cse.py
      http_client.py
    utils/
      text_utils.py
      url_utils.py
    tests/
      unit/
      integration/
      contract/
  requirements.txt
  README.md
```

Hackathon-friendly note: if time is tight, start with in-memory repositories and keep repository interfaces so DB-backed storage can be added later without API breakage.

---

## 3) Data Flow

1. Client sends original article payload to Discovery API.
2. API validates request and creates a discovery job context.
3. Query generator creates multiple search queries from title/body/key phrases/entities.
4. Google CSE client executes bounded search requests with retries/backoff.
5. URL collector deduplicates/canonicalizes URLs and filters obvious low-value links.
6. Content pipeline fetches each URL, extracts article text via Trafilatura (or fallback extractor), and normalizes text.
7. Candidate ranker scores relevance against source article signals (keyword overlap, named entities, title similarity, content length sanity).
8. Service returns structured candidate articles + metadata + ranking score.
9. Optional persistence stores job status, query set, and extracted candidates for traceability/debugging.

---

## 4) Database Schema (optional but recommended)

If persistence is required for async jobs and auditing:

### `discovery_jobs`
- `job_id` (UUID, PK)
- `created_at` (timestamp)
- `status` (enum: queued, running, completed, failed)
- `source_title` (text)
- `source_hash` (text)
- `query_count` (int)
- `error_code` (text, nullable)
- `error_message` (text, nullable)

### `discovery_queries`
- `id` (UUID, PK)
- `job_id` (FK -> discovery_jobs.job_id)
- `query_text` (text)
- `query_index` (int)
- `executed_at` (timestamp)

### `candidate_articles`
- `candidate_id` (UUID, PK)
- `job_id` (FK)
- `url` (text)
- `canonical_url` (text)
- `domain` (text)
- `title` (text, nullable)
- `raw_text` (text, nullable)
- `normalized_text` (text, nullable)
- `extraction_confidence` (float, nullable)
- `ranking_score` (float)
- `source_query` (text)
- `fetched_at` (timestamp)
- `status` (enum: extracted, skipped, failed)
- `failure_reason` (text, nullable)

Indexes:
- `candidate_articles(job_id, ranking_score DESC)`
- `candidate_articles(canonical_url)`
- `discovery_queries(job_id)`

---

## 5) API Contract Definitions

### `POST /v1/discovery/candidates`
Purpose: synchronous discovery for hackathon speed.

### `POST /v1/discovery/jobs`
Purpose: create async job for production mode.

### `GET /v1/discovery/jobs/{job_id}`
Purpose: fetch job status and summary.

### `GET /v1/discovery/jobs/{job_id}/candidates`
Purpose: fetch discovered candidates once complete.

---

## 6) Request/Response Schemas

### Request: `DiscoveryRequest`
- `source_id` (string, optional)
- `article_title` (string, optional)
- `article_text` (string, required)
- `article_url` (string, optional)
- `language` (string, default `en`)
- `max_queries` (int, default 6, max 12)
- `max_results_per_query` (int, default 10, max 20)
- `max_candidates` (int, default 40, max 100)
- `include_debug` (bool, default false)

Schema notes:
- If `article_title` is missing, query generation falls back to keyphrase + entity-driven phrase queries.
- Compute `estimated_api_calls = max_queries * ceil(max_results_per_query / 10)` to account for pagination (Google CSE returns up to 10 results per API call, so results beyond page 1 require additional calls).
- Enforce `estimated_api_calls <= 12` by default for paid-tier mode, with a stricter configurable free-tier profile (recommended `<= 4`) to preserve daily quota.

### Response: `DiscoveryResponse`
- `job_id` (string)
- `status` (string)
- `source_fingerprint` (string)
- `queries` (array of strings, optional unless debug)
- `candidates` (array of `CandidateArticle`)
- `stats` (object)
  - `queries_executed` (int)
  - `urls_collected` (int)
  - `urls_processed` (int)
  - `candidates_returned` (int)
  - `duration_ms` (int)

### `CandidateArticle`
- `candidate_id` (string)
- `url` (string)
- `canonical_url` (string)
- `domain` (string)
- `title` (string, nullable)
- `snippet` (string, nullable)
- `normalized_text` (string)
- `ranking_score` (float)
- `signals` (object)
  - `keyword_overlap` (float)
  - `title_similarity` (float)
  - `entity_overlap` (float)
  - `content_length` (int)
- `source_query` (string)
- `extraction_status` (string)

### Error response: `ErrorResponse`
- `error_code` (string)
- `message` (string)
- `details` (object, optional)
- `request_id` (string)

---

## 7) Service Boundaries

In scope (Discovery Service):
- Request validation and orchestration
- Query generation
- Search API integration
- URL collection/deduplication
- Content extraction/normalization
- Candidate scoring/ranking
- Structured output for downstream service

Out of scope:
- Similarity verdicting/plagiarism decision
- Evidence packaging and legal narrative generation
- DMCA document creation and dispatch

---

## 8) Error Handling Strategy

Error classes:
- `ValidationError` (400)
- `AuthConfigError` (500 misconfiguration)
- `ProviderRateLimitError` (429 / mapped upstream)
- `ProviderTemporaryError` (502/503 with retry)
- `ExtractionError` (partial failure per URL, not fatal)
- `InternalDiscoveryError` (500)

Practices:
- Fail fast on invalid request.
- Per-URL extraction failures are isolated; continue processing others.
- Use timeout budgets per stage (search, fetch, extract).
- Emit structured logs with `request_id`, `job_id`, `url`, and stage.
- Return partial results with warning counters where possible.

---

## 9) Rate Limiting Strategy

Layers:
1. **Client-facing API limit** (per API key/IP): token bucket (e.g., 30 req/min).
2. **Provider budget control**: per-minute and daily quota guards for Google CSE.
3. **Worker concurrency caps**: default max 10 concurrent URL fetch/extract tasks per request.
4. **Circuit breaker**: if CSE errors spike, short-circuit to protect quota.

Behavior:
- On API limit breach: 429 with retry-after.
- On provider quota exhaustion: 503/429 with explicit `error_code=SEARCH_QUOTA_EXCEEDED`.

---

## 10) Search Query Generation Strategy

Input signals:
- Title terms (high weight)
- Top TF-IDF/keyphrase terms from body
- Named entities (people/org/product)
- Unique quoted fragments (short exact substrings)

Query set composition (example 4–8 queries):
1. Exact title (quoted if concise)
2. Title + 2 strongest entities
3. 6–10 keyphrase bag query
4. Two exact phrase queries from distinct paragraphs
5. Brand/site-exclusion variations (reduce self-domain noise)

Quality controls:
- Deduplicate semantically similar queries.
- Enforce max token length per query.
- Language-aware stopword filtering.

---

## 11) Candidate Ranking Strategy

Score components (weighted sum, initial baseline tuned for title+content signal balance):
- `title_similarity` (0.25)
- `keyword_overlap` (0.30)
- `entity_overlap` (0.20)
- `phrase_match_density` (0.15)
- `content_quality_signal` (0.10) (length, extraction confidence, boilerplate ratio)

Formula:
- Each component score is normalized to `[0.0, 1.0]`, so `final_score` is also in `[0.0, 1.0]`.
- `final_score = 0.25*title_similarity + 0.30*keyword_overlap + 0.20*entity_overlap + 0.15*phrase_match_density + 0.10*content_quality_signal`

Normalization examples:
- `title_similarity`: cosine similarity between title embeddings.
- `keyword_overlap`: overlap ratio (e.g., Jaccard) on normalized keyword sets.
- `entity_overlap`: intersection-over-union on extracted entity sets.

Tuning guidance:
- Recalibrate weights using a labeled validation set and monitor precision@K/recall@K.
- Increase `entity_overlap` weight for entity-dense domains; increase `phrase_match_density` for long-form editorial content.

Post-processing:
- Domain diversity boost to avoid one-site dominance.
- Canonical URL deduplication.
- Penalty for very short/low-content pages.

Output:
- Return top N candidates sorted by `ranking_score` with signals for downstream explainability.

---

## 12) Development Roadmap (small tasks)

1. Bootstrap FastAPI module layout + config management.
2. Define Pydantic contracts for requests/responses/errors.
3. Implement query generation service with unit tests.
4. Implement Google CSE client wrapper (timeouts, retries, quota handling).
5. Implement URL canonicalization + dedupe module.
6. Implement content fetcher with safe HTTP defaults.
7. Implement Trafilatura extraction adapter + fallback handling.
8. Implement normalization pipeline (cleanup, unicode normalize, whitespace, language-safe casing).
9. Implement candidate ranking module + scoring tests.
10. Implement orchestration service combining all stages.
11. Add API routes (sync first, async optional).
12. Add structured logging, request IDs, and metrics counters.
13. Add integration tests with mocked Google CSE + mocked URL fetch/extraction.
14. Add optional persistence adapters and migrations.
15. Final hardening: rate limits, failure injection tests, timeout tuning.

---

## 13) Recommended Git Commit Sequence

1. `chore(discovery): scaffold service package structure and config`
2. `feat(discovery): add API contracts and validation schemas`
3. `feat(discovery): implement query generation engine with tests`
4. `feat(discovery): integrate google custom search client with retry/timeout`
5. `feat(discovery): add URL canonicalization and deduplication`
6. `feat(discovery): add extraction pipeline with trafilatura adapter`
7. `feat(discovery): add text normalization and candidate ranking`
8. `feat(discovery): implement discovery orchestrator and API endpoints`
9. `test(discovery): add integration and contract tests`
10. `chore(discovery): add observability, rate limiting, and docs`

---

## 14) Risks & Mitigation Strategies

1. **Google API quota exhaustion**  
   Mitigation: strict quotas, caching repeated queries, backoff, alerting.

2. **Low extraction quality on dynamic pages**  
   Mitigation: extractor fallback chain, extraction confidence score, skip noisy pages.

3. **High latency from multi-URL processing**  
   Mitigation: async concurrency limits, timeout budgets, early cutoff after enough strong candidates.

4. **False positives from weak ranking**  
   Mitigation: richer relevance signals, tune weights with validation dataset, keep explainable score breakdown.

5. **Operational instability in hackathon timeline**  
   Mitigation: implement sync path first, in-memory repositories first, defer async DB complexity behind interfaces.

6. **Security/abuse via arbitrary URL fetching**  
   Mitigation: URL validation, block local/private IP ranges, strict request timeouts, user-agent controls.
