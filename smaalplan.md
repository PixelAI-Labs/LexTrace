# smaallplan.md — Task Breakdown
# Commit target: chore(config): implement environment-based configuration loader

---

## Dependency Graph & Task Breakdown

### Dependency Graph (Topological Order)

```
core/config.py ──────────────────────────────────────────────────────┐
      │                                                            │
core/logging.py ◀── (config)                                       │
      │                                                            │
core/exceptions.py ◀── (config, logging)                           │
      │                                                            │
core/rate_limiter.py ◀── (config, logging, exceptions)               │
      │                                                            │
discovery/schemas/requests.py ◀── (exceptions)                     │
      │                                                            │
discovery/schemas/responses.py ◀── (exceptions)                    │
      │                                                            │
discovery/utils/text_utils.py ◀── (logging)                        │
      │                                                            │
discovery/services/query_generator.py ◀── (config, logging, text_utils)
      │                                                            │
discovery/infrastructure/google_search.py ◀── (config, logging, exceptions)
      │                                                            │
discovery/infrastructure/web_scraper.py ◀── (config, logging, exceptions)
      │                                                            │
discovery/services/search_engine.py ◀── (google_search, rate_limiter, logging)
      │                                                            │
discovery/services/candidate_collector.py ◀── (config, logging, query_generator)
      │                                                            │
discovery/services/content_normalizer.py ◀── (config, logging, text_utils)
      │                                                            │
discovery/services/content_extractor.py ◀── (web_scraper, content_normalizer, rate_limiter, logging)
      │                                                            │
discovery/services/candidate_ranker.py ◀── (config, logging, query_generator, content_normalizer)
      │                                                            │
discovery/api/deps.py ◀── (config, rate_limiter)                    │
      │                                                            │
discovery/api/routes/health.py ◀── (google_search, logging)         │
      │                                                            │
discovery/api/routes/discovery.py ◀── (all services, schemas, deps) │
      │                                                            │
discovery/app.py ◀── (routes, deps, exception handlers)            │
      │                                                            │
copyguard/__init__.py ◀── (app)                                   │
```

---

### 1. First Component to Implement: core/config.py

### 2. Why It Must Come First

Every single component in the service depends on configuration — API keys, timeouts, rate limits, feature flags, paths, TTLs. Without a unified config subsystem, each module would independently parse environment variables, leading to inconsistent defaults, duplicate validation logic, and hard-to-audit settings spread across the codebase.

### 3. Future Components Depending on It

All of them. The full list:
- `core/logging.py`, `core/exceptions.py`, `core/rate_limiter.py`
- `discovery/config.py` (extends core)
- `discovery/infrastructure/google_search.py`, `discovery/infrastructure/web_scraper.py`
- `discovery/services/` — all 6 services
- `discovery/api/deps.py`, `discovery/api/routes/discovery.py`, `discovery/api/routes/health.py`
- `discovery/app.py`

### 4. Files to Create

| File | Purpose |
|---|---|
| `copyguard/__init__.py` | Package marker |
| `copyguard/core/__init__.py` | Package marker (exports `settings` instance) |
| `copyguard/core/config.py` | All config classes + `settings` singleton |
| `copyguard/core/py.typed` | PEP 561 marker for typed package |
| `tests/unit/__init__.py` | Test package marker |
| `tests/unit/test_config.py` | Config unit tests |

**Existing files to modify:**
| File | Action |
|---|---|
| `backend/requirements.txt` | Add `pydantic-settings>=2.0` |

### 5. Acceptance Criteria

1. **No hardcoded secrets/values** — every externalizable value is loaded from config
2. **Environment override** — ENV vars take precedence over defaults (e.g., `GOOGLE_API_KEY` overrides yaml value)
3. **Valid Pydantic model** — config is a typed Pydantic `BaseSettings` instance; invalid config raises `ValidationError` on startup
4. **Sections for each subsystem** — `google`, `content_extraction`, `rate_limiting`, `discovery`, `logging`, `app` each have namespaced sub-configs
5. **Unit testable** — config values can be overridden in tests via `model_construct` or fixture
6. **Startup validation** — missing required fields (e.g., `google.api_key`) fail fast with `ValidationError`
7. **Importable without side effects** — `from copyguard.core.config import settings` succeeds without initializing any other subsystem