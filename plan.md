CopyGuard — Discovery Service: Technical Design & Execution Plan
Project: CopyGuard (AI-Powered Article Piracy Detection)
Service in scope: Discovery Service
Tech stack: FastAPI · Python 3.11+ · Google Custom Search API · Trafilatura

1. System Architecture Diagram

                         ┌─────────────────────────────────────────────────────────┐
                         │                  CopyGuard Platform                       │
                         │                                                          │
                         │   ┌──────────────┐        ┌──────────────────────────┐   │
                         │   │   Frontend   │──────▶│    Gateway / FastAPI     │   │
                         │   │   (React)    │◀──────│    (Aggregated API)      │   │
                         │   └──────────────┘        └───────────┬──────────────┘   │
                         │                                          │                  │
                         │                   ┌─────────────────────┼────────────┐    │
                         │                   │                     │            │    │
                         │          ┌────────▼────────┐  ┌────────▼────┐  ┌───▼────┐ │
                         │          │ Discovery Svc   │  │ Similarity  │  │  DMCA  │ │
                         │          │  (this spec)    │  │   Engine    │  │  Svc   │ │
                         │          └────────┬────────┘  └─────────────┘  └────────┘ │
                         │                   │                                   │    │
                         └───────────────────┼───────────────────────────────────┘    │
                         ┌───────────────────▼───────────────────────────────────────┐ │
                         │              External Integrations                        │ │
                         │  ┌──────────────────────┐  ┌────────────────────────────┐  │ │
                         │  │ Google Custom Search │  │    Content Extraction     │  │ │
                         │  │       API            │  │    (Trafilatura / requests)│  │ │
                         │  └──────────────────────┘  └────────────────────────────┘  │ │
                         └───────────────────────────────────────────────────────────┘ │
                         └─────────────────────────────────────────────────────────────┘
Discovery Service — Internal Architecture

  ┌──────────────────────────────────────────────────────────────────────────────┐
  │                          Discovery Service (copyguard/discovery/)            │
  │                                                                          [SVC] │
  │  Incoming Request                                                            │
  │       │                                                                     │
  │       ▼                                                                     │
  │  ┌─────────────┐   ┌─────────────────┐   ┌──────────────────────┐        │
  │  │  Router /   │──▶│  Query          │──▶│  Search              │        │
  │  │  Schemas    │   │  Generator      │   │  Engine (Google API) │        │
  │  └─────────────┘   └─────────────────┘   └──────────┬───────────┘        │
  │                                                      │                    │
  │                                        ┌─────────────▼─────────────┐      │
  │                                        │  Candidate Collector      │      │
  │                                        │  (URL deduplication)      │      │
  │                                        └─────────────┬─────────────┘      │
  │                                                      │                    │
  │                                        ┌─────────────▼─────────────┐      │
  │                                        │  Content Extractor        │      │
  │                                        │  (Trafilatura + requests) │      │
  │                                        └─────────────┬─────────────┘      │
  │                                                      │                    │
  │                                        ┌─────────────▼─────────────┐      │
  │                                        │  Content                  │      │
  │                                        │  Normalizer & Cleaner     │      │
  │                                        └─────────────┬─────────────┘      │
  │                                                      │                    │
  │                                        ┌─────────────▼─────────────┐      │
  │                                        │  Candidate Ranker         │      │
  │                                        │  (Scoring & Ordering)     │      │
  │                                        └─────────────┬─────────────┘      │
  │                                                      │                    │
  │  Outgoing Response ◀────────────────────────────────┘                    │
  └──────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────────┐
  │                          Shared / Core (copyguard/core/)                     │
  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
  │  │  Config     │  │  Rate        │  │  Error         │  │  Logging /    │  │
  │  │  Manager    │  │  Limiter     │  │  Handlers      │  │  Observability│  │
  │  └─────────────┘  └──────────────┘  └────────────────┘  └────────────────┘  │
  └──────────────────────────────────────────────────────────────────────────────┘
2. Folder Structure

backend/                           # Python package root — FastAPI application
├── main.py                       # FastAPI app entry point + legacy API stubs
├── requirements.txt              # All Python dependencies
│
├── core/                         # Shared across all services
│   ├── __init__.py
│   └── config.py                 # Pydantic Settings — env var configuration
│
├── discovery/                    # Discovery Service
│   ├── __init__.py
│   │
│   ├── schemas/                  # Pydantic models
│   │   ├── __init__.py
│   │   ├── requests.py           # DiscoveryRequest, DiscoveryOptions
│   │   └── responses.py          # DiscoveryResponse, CandidateArticle, etc.
│   │
│   ├── services/                 # Business logic (framework-agnostic)
│   │   ├── __init__.py
│   │   └── query_generator.py    # Generates search queries from article text
│   │
│   └── utils/                    # Shared utilities
│       ├── __init__.py
│       └── text_utils.py         # Keyword extraction, HTML stripping, normalisation
│
frontend/                         # React frontend (separate)
tests/                            # Test suite (parallel to backend)
├── conftest.py                   # Pytest fixtures
└── unit/
    ├── test_config.py
    ├── test_schemas.py
    ├── test_text_utils.py
    └── test_query_generator.py

3. Data Flow

┌─────────────────────────────────────────────────────────────────┐
│                       REQUEST FLOW                              │
│                                                                 │
│  Client                                                         │
│    │                                                           │
│    │  POST /discover { article_text, title?, url? }             │
│    ▼                                                           │
│  ┌──────────────┐                                             │
│  │ FastAPI      │  ◀── Validate request schema                │
│  │ Router       │  ◀── Rate limit check (per API key/IP)     │
│  └──────┬───────┘                                             │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────┐                                             │
│  │ Query        │  Extract keywords / title / sentences       │
│  │ Generator    │  Generate 3–8 search queries               │
│  └──────┬───────┘                                             │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────┐                                             │
│  │ Search       │  For each query:                           │
│  │ Engine       │    - Check rate limit bucket               │
│  │ (Google API) │    - Call Google Custom Search API         │
│  │              │    - Collect top-N results per query       │
│  └──────┬───────┘                                             │
│         │                                                      │
│         ▼                                                      │
│  ┌───────────────┐                                            │
│  │ Candidate     │  - Deduplicate URLs (set-based)           │
│  │ Collector     │  - Filter known domains (self, whitelisted)│
│  │               │  - Cap at configurable MAX_CANDIDATES (50)  │
│  └───────┬───────┘                                            │
│          │                                                     │
│          ▼                                                     │
│  ┌───────────────┐                                            │
│  │ Content       │  For each candidate URL (async, pooled): │
│  │ Extractor     │    - HTTP GET with timeout (15s)          │
│  │               │    - Trafilatura.extract()                │
│  │               │    - Fallback: readability-lxml           │
│  └───────┬───────┘                                            │
│          │                                                     │
│          ▼                                                     │
│  ┌───────────────┐                                            │
│  │ Content       │  - Strip HTML / scripts / styles          │
│  │ Normalizer    │  - Normalize whitespace / unicode         │
│  │               │  - Optional: sentence-level chunking      │
│  └───────┬───────┘                                            │
│          │                                                     │
│          ▼                                                     │
│  ┌───────────────┐                                            │
│  │ Candidate     │  - TF-IDF similarity to original         │
│  │ Ranker        │  - Keyword overlap score                  │
│  │               │  - Structural similarity (heading match)   │
│  │               │  - Final composite score [0.0 – 1.0]     │
│  │               │  - Sort descending, return top candidates  │
│  └───────┬───────┘                                            │
│          │                                                     │
│          ▼                                                     │
│  ┌───────────────┐                                            │
│  │ Response      │  Assemble DiscoveryResponse               │
│  │ Assembler     │  Return to client                         │
│  └───────────────┘                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
Async Concurrency Strategy

  Search Phase:      Sequential per query (rate-limit constrained)
  Extraction Phase:  Semaphore-constrained async (default: 10 concurrent extractions)
  Ranking Phase:     Synchronous (CPU-light, in-memory)
4. Database Schema
Note: For the Discovery Service, no database is required for initial implementation. Candidates are returned directly to the caller. State is held in-memory for the duration of a request.

If persistence is needed later (for caching or rate limit tracking), use Redis keys.

Optional Persistence Layer (Future)

-- Redis (recommended for caching + rate limiting)
-- Key: "discovery:{request_id}"          → TTL 1 hour
-- Key: "rate:{api_key}:{minute}"        → TTL 60s
For the hackathon implementation, an in-memory cache with TTL is sufficient.

5. API Contract Definitions
5.1 Primary Endpoint: POST /api/v1/discover
Request

{
  "article_text": "string (required, 100–50000 chars)",
  "title": "string (optional, max 500 chars)",
  "source_url": "string (optional, valid URL)",
  "options": {
    "max_candidates": "integer (optional, default=20, max=50)",
    "search_depth": "string (optional, 'shallow'|'deep', default='shallow')",
    "include_content": "boolean (optional, default=true)"
  }
}
Response (200 OK)

{
  "request_id": "uuid",
  "status": "completed",
  "original_title": "string or null",
  "queries_used": ["string"],
  "total_urls_collected": 42,
  "candidates": [
    {
      "rank": 1,
      "url": "https://example.com/article",
      "domain": "example.com",
      "title": "Article Title",
      "rank_score": 0.94,
      "keyword_coverage": 0.87,
      "content_preview": "First ~300 chars of extracted content...",
      "text_length": 1245,
      "publish_date": "2024-03-15" | null,
      "language": "en" | null
    }
  ],
  "metadata": {
    "total_candidates": 20,
    "queries_generated": 5,
    "extraction_time_ms": 4821,
    "search_time_ms": 1340,
    "total_time_ms": 6261
  }
}
Error Responses
Status	Body
400	{ "detail": "article_text is required and must be between 100 and 50000 characters" }
422	Pydantic validation error (standard FastAPI)
429	{ "detail": "Rate limit exceeded. Retry after 60 seconds." }
500	{ "detail": "Discovery failed", "request_id": "uuid", "reason": "string" }
503	{ "detail": "Search service temporarily unavailable" }
5.2 Health Check: GET /api/v1/health

{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "google_search": "ok",
    "content_extraction": "ok"
  }
}
6. Request / Response Schemas (Pydantic Models)

# — Requests —

class DiscoveryOptions(BaseModel):
    max_candidates: int = Field(default=20, ge=1, le=50)
    search_depth: Literal["shallow", "deep"] = "shallow"
    include_content: bool = True


class DiscoveryRequest(BaseModel):
    article_text: str = Field(..., min_length=100, max_length=50_000)
    title: Optional[str] = Field(None, max_length=500)
    source_url: Optional[HttpUrl] = None
    options: DiscoveryOptions = Field(default_factory=DiscoveryOptions)

# — Responses —

class CandidateArticle(BaseModel):
    rank: int
    url: str
    domain: str
    title: Optional[str]
    rank_score: float = Field(..., ge=0.0, le=1.0)
    keyword_coverage: float = Field(..., ge=0.0, le=1.0)
    content_preview: str
    text_length: int
    publish_date: Optional[str] = None
    language: Optional[str] = None


class DiscoveryMetadata(BaseModel):
    total_candidates: int
    queries_generated: int
    extraction_time_ms: int
    search_time_ms: int
    total_time_ms: int


class DiscoveryResponse(BaseModel):
    request_id: str
    status: Literal["completed", "partial", "failed"]
    original_title: Optional[str]
    queries_used: List[str]
    total_urls_collected: int
    candidates: List[CandidateArticle]
    metadata: DiscoveryMetadata
7. Service Boundaries

┌─────────────────────────────────────────────────────────────────┐
│                     Discovery Service Boundary                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  PUBLIC API (FastAPI Router)                               │  │
│  │  POST /discover   GET /health                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SERVICE LAYER (Framework-agnostic business logic)         │  │
│  │                                                             │  │
│  │  QueryGenerator  ──▶  SearchEngine  ──▶  CandidateCollector│  │
│  │         │                                    │              │  │
│  │         ▼                                    ▼              │  │
│  │  ContentExtractor  ──▶  ContentNormalizer  ──▶  Ranker     │  │
│  │                                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  INFRASTRUCTURE LAYER (External API clients)              │  │
│  │  GoogleSearchClient   WebScraper (httpx + Trafilatura)    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CORE SHARED (cross-service concerns)                     │  │
│  │  Config   Exceptions   Rate Limiter   Logging              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ── OUT OF SCOPE ─────────────────────────────────────────────  │
│  Similarity Engine (next service)                               │
│  Evidence Generation (next service)                            │
│  DMCA PDF Generation (next service)                            │
│  Auth / User Management (platform concern)                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
Interface to Downstream Services
The Discovery Service returns fully structured CandidateArticle objects to the caller (the aggregator API gateway). Downstream services receive:


# Downstream interface (output only — no direct service-to-service calls needed)
List[CandidateArticle]  # Already ranked with scores
No gRPC, message queue, or direct API calls between services are needed at the hackathon stage. The aggregator assembles the final response.

8. Error Handling Strategy
Layered Error Handling

Layer 1: FastAPI Exception Handlers  (global, in app.py)
        - HTTPException → structured JSON responses
        - RequestValidationError → 422 with field-level details
        - Custom AppException → 5xx / 4xx mapped to appropriate status

Layer 2: Service-level try/except   (in each service class)
        - GoogleSearchError → raise DiscoveryException("search_failed")
        - ExtractionError   → log, continue to next URL, record failure in metadata
        - RateLimitError    → raise DedicatedRateLimitException

Layer 3: HTTP client-level retry     (in infrastructure clients)
        - httpx retry: 3 attempts, exponential backoff (1s, 2s, 4s)
        - Timeout: 15s per request
Exception Hierarchy

# core/exceptions.py

class CopyGuardException(Exception):
    """Base exception for all CopyGuard application errors."""
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DiscoveryException(CopyGuardException):      pass
class SearchServiceException(DiscoveryException):  pass
class ExtractionException(DiscoveryException):    pass
class RateLimitException(CopyGuardException):     pass
class ConfigurationException(CopyGuardException):  pass
Partial Failure Tolerance
If 1 candidate URL fails to extract → skip and continue
Track total_urls_collected vs len(candidates) in response metadata
If >50% of candidates fail → set status: "partial" in response
If all candidates fail → set status: "failed" and return empty candidates list
9. Rate Limiting Strategy
Multi-Tier Rate Limiting
Tier	Scope	Limit	Window	Action on Exceed
API Gateway	Per IP / API Key	10 req	1 minute	429 + Retry-After header
Google Search API	Per API Key	100 queries	1 day	429 from Google; fallback queue
Content Extraction	Per domain	20 req	1 minute	Per-domain backoff (30s)
Implementation

# core/rate_limiter.py    Token Bucket algorithm

class TokenBucketRateLimiter:
    def __init__(self, rate: int, per_seconds: int):
        # rate = tokens per refill interval
        self.capacity = rate
        self.tokens = rate
        self.refill_rate = rate / per_seconds

    async def acquire(self, tokens: int = 1) -> bool:
        # Returns True if allowed, False if limited
        # Non-blocking: check + decrement in one atomic operation
Resilience Pattern

Google API Rate Limit Hit
         │
         ▼
  ┌──────────────────┐
  │ Exponential      │
  │ backoff          │
  │ (max 3 retries)  │
  └────────┬─────────┘
           │
      Success?
      │         │
     Yes       No
      │         │
      ▼         ▼
  Continue   Log error
             Mark query failed
             Return partial result
10. Search Query Generation Strategy
Goal
Generate 3–8 diverse, high-precision queries that maximize recall of potential pirated copies while minimizing irrelevant results.

Strategy A: Keyword-Based Queries (Primary — for shallow depth)

1. Title Query:       "{title}"              (exact phrase, in quotes)
2. Core Keyword Pair:  top-2 TF-IDF keywords + title fragment
3. Topic Phrase:       3–4 most salient noun phrases
4. Author/Source:      "{author_name}" site:known_news_domain  (if author provided)
5. Randomized variant: "{keyword1} {keyword2} tutorial/article"
Strategy B: Nuanced Queries (for deep depth)

6. Question form:      "how to {key_phrase}"
7. Listicle form:      "{key_phrase} complete guide/list/overview"
8. Synonym variant:   Replace key terms with common synonyms
Implementation

# discovery/services/query_generator.py

class QueryGenerator:
    def __init__(self, max_queries: int = 8):
        self.max_queries = max_queries

    def generate(self, article_text: str, title: str | None = None) -> List[str]:
        # 1. Run TF-IDF keyword extraction (top-K keywords)
        # 2. If title: generate exact-phrase query + title variants
        # 3. Generate keyword pair queries (combinatorial, deduped)
        # 4. Rank by estimated precision (exact match > keyword pair > general)
        # 5. Return top N queries
Query Prioritization

Priority 1: Exact title match  (highest precision)
Priority 2: Top keyword pairs (high precision)
Priority 3: Single keyword + generic term  (moderate recall)
Priority 4: Topic noun phrase  (lower precision, higher recall)
11. Candidate Ranking Strategy
Scoring Pipeline
Each candidate receives a composite score from 0.0 to 1.0:


composite_score = (
    0.30 × keyword_coverage      +   # % of original keywords found in candidate
    0.25 × text_similarity       +   # Cosine similarity of TF-IDF vectors
    0.25 × structural_similarity +   # Heading order match, section overlap
    0.15 × title_match_score     +   # Levenshtein ratio of titles
    0.05 × domain_popularity        # Alexa/Tranco rank (dampen high-traffic legit sites)
)
Ranking Steps

1. Extract keywords from original article (TF-IDF, top-30 keywords)
2. For each candidate:
     a. keyword_coverage = |found_keywords| / |original_keywords|
     b. text_similarity  = cosine_similarity(tfidf(original), tfidf(candidate))
     c. structural_sim    = normalized_longest_common_subsequence(headings)
     d. title_match_score = 1 - (levenshtein_distance / max(len_a, len_b))
     e. domain_score     → penalize domain if on whitelist; boost if on pirate blacklist
3. Compute weighted composite score
4. Sort descending by composite_score
5. Return top N candidates (default 20, max 50)
Blacklist / Whitelist

PIRATE_DOMAINS_BLACKLIST = [
    "scrapehero.com", "webcache.googleusercontent.com", "cc.bingj.com"
]

TRUSTED_DOMAINS_WHITELIST = [
    "nytimes.com", "theguardian.com", "medium.com", ...  # low-piracy sites to de-prioritize
]
12. Development Roadmap (Ordered Implementation Tasks)
Phase 0 — Foundation (Day 1)
#	Task	Description
0.1	Bootstrap project structure	Create pyproject.toml, update requirements.txt, set up copyguard/ package layout
0.2	Config system	Load env vars → core/config.py. Single source of truth for all settings
0.3	Custom exception hierarchy	core/exceptions.py with all custom exception classes
0.4	Structured logging	core/logging.py — JSON logs, request ID context, loglevel from env
0.5	Base test harness	tests/conftest.py, fixtures for mocked Google API, in-memory candidates
0.6	__init__.py exports	Ensure all modules export cleanly with no circular imports
Phase 1 — Core Data Structures (Day 1–2)
#	Task	Description
1.1	Define Pydantic schemas	discovery/schemas/requests.py and responses.py — fully typed
1.2	Write unit tests for schemas	Validate edge cases (empty strings, oversized input, invalid URLs)
1.3	API dependency injection	discovery/api/deps.py — provide config, rate limiter to routes
Phase 2 — Query Generation (Day 2)
#	Task	Description
2.1	Keyword extraction module	TF-IDF via sklearn or scipy. Pure function: extract_keywords(text, top_k)
2.2	Query generator service	discovery/services/query_generator.py — implements all 5 query strategies
2.3	Unit tests for QueryGenerator	Test with known article, verify query count, diversity, format
Phase 3 — Search & Collection (Day 2–3)
#	Task	Description
3.1	Google Search API client	discovery/infrastructure/google_search.py — httpx client, auth header, error mapping
3.2	Search engine service	discovery/services/search_engine.py — orchestrate multi-query search
3.3	Candidate collector	discovery/services/candidate_collector.py — URL deduplication, domain filtering
3.4	Rate limiter	core/rate_limiter.py — TokenBucket, in-memory
3.5	Integration test	Mock Google API response → verify URL collection
Phase 4 — Content Extraction (Day 3)
#	Task	Description
4.1	Web scraper	discovery/infrastructure/web_scraper.py — httpx client setup, timeout, retry
4.2	Trafilatura integration	content_extractor.py — trafilatura.extract(), fallback chain
4.3	Content normalizer	discovery/services/content_normalizer.py — HTML stripping, unicode norm., whitespace
4.4	Async pool executor	Cap concurrent extractions with asyncio.Semaphore(max_concurrent=10)
4.5	Unit tests for extractor	Mock HTTP responses, verify extraction + normalization
Phase 5 — Ranking (Day 3–4)
#	Task	Description
5.1	TF-IDF vectorizer setup	sklearn.feature_extraction.text.TfidfVectorizer
5.2	Candidate ranker	discovery/services/candidate_ranker.py — all 5 scoring components
5.3	Blacklist/whitelist	Domain lists as config-loaded constants
5.4	Ranker unit tests	Compute score for synthetic candidates, verify ordering
Phase 6 — API Assembly (Day 4)
#	Task	Description
6.1	FastAPI app factory	discovery/app.py — lifespan, CORS, middleware, custom exception handlers
6.2	Discovery route	discovery/api/routes/discovery.py — orchestrate all services end-to-end
6.3	Health route	discovery/api/routes/health.py — check Google API connectivity
6.4	Global error handler	Map all exceptions to structured JSON error responses
6.5	Full integration test	Real (or mock) end-to-end: article in → candidates out
Phase 7 — Polish (Day 5)
#	Task	Description
7.1	Performance profiling	Measure total_time_ms breakdown; identify bottlenecks
7.2	Error message quality	Ensure every failure returns actionable error messages
7.3	Dockerfile	Single-stage Dockerfile for the discovery service
7.4	API documentation	Auto-generated Swagger/OpenAPI at /docs
7.5	Dry-run with real articles	Run 3–5 real articles through the system, manually verify candidate quality
13. Recommended Git Commit Sequence

1.  chore: initialize discovery service package structure
2.  chore: add project dependencies to requirements.txt (httpx, trafilatura, sklearn...)
3.  feat(config): implement environment-based configuration loader
4.  feat(logging): add structured JSON logging with request ID context
5.  feat(exceptions): add custom exception hierarchy with HTTP mapping
6.  feat(schemas): define Pydantic request/response schemas for discovery endpoint
7.  test(schemas): add unit tests for schema validation and edge cases
8.  feat(query-generator): implement TF-IDF keyword extraction
9.  feat(query-generator): implement multi-strategy query generation
10. test(query-generator): add unit tests with known articles
11. feat(google-search): implement Google Custom Search API client
12. feat(search-engine): orchestrate multi-query search with rate limiting
13. feat(candidate-collector): implement URL deduplication and domain filtering
14. feat(rate-limiter): implement token bucket rate limiter
15. test(rate-limiter): add unit tests for rate limit enforcement
16. feat(extractor): implement web scraper with httpx + retry
17. feat(extractor): integrate Trafilatura for content extraction
18. feat(normalizer): implement content cleaning and normalization
19. test(extractor): add unit tests for extraction pipeline
20. feat(ranker): implement multi-factor candidate scoring
21. feat(ranker): add blacklist/whitelist domain handling
22. test(ranker): add unit tests for scoring and ordering
23. feat(api): implement FastAPI app factory with lifespan and middleware
24. feat(api): implement POST /discover endpoint orchestrating all services
25. feat(api): implement GET /health endpoint with dependency checks
26. fix: handle partial failures gracefully in discovery pipeline
27. test(api): add integration tests for end-to-end discovery flow
28. docs: add OpenAPI schema documentation
29. chore: add Dockerfile for discovery service
14. Risks and Mitigation Strategies
Risk	Likelihood	Impact	Mitigation
Google Search API quota exceeded	Medium	High	Queue queries with backoff; cache results; configurable max queries per run
Content extraction fails on JS-rendered sites	High	Medium	Trafilatura primary, readability-lxml fallback, newspaper3k tertiary fallback
Pirated content behind paywalls / logins	High	Medium	Skip with log warning; note in publish_date: null; no score penalty
Query generation produces spam queries	Medium	Medium	Threshold filter: skip queries with >30% stopwords; enforce min 2 non-stopword tokens
Google blocking requests from server IP	Low	High	Use User-Agent rotation; respect robots.txt; add jitter between requests
Rate limit errors cause service crash	Low	High	All external calls wrapped in try/except; graceful degradation to partial results
Very large articles → memory pressure	Low	Medium	Cap article_text at 50,000 chars; semaphore on async extractions
Candidate ranker produces unreliable scores	Medium	High	Tune weights with real data; log score distribution; expose raw scores in response metadata
Noisy candidates (forums, Reddit, StackOverflow)	Medium	Low	Whitelist known legitimate platforms; domain popularity penalization in ranker
Concurrent requests exhausting Google quota for all users	Medium	High	Per-IP + per-API-key rate limiting; circuit breaker after 3 consecutive 429s
Summary
The Discovery Service follows a pipeline architecture with clear separation between the API layer, service layer, and infrastructure layer. Each pipeline stage is independently testable and replaceable. The design prioritizes:

Resilience over correctness: Every external call is wrapped with retry logic, timeouts, and graceful degradation
Observability: Structured logs with request_id correlate every step
Hackathon velocity: No database, no message queue — in-memory with async concurrency
Production foundations: Modular structure enables easy upgrade to Redis/PostgreSQL when needed