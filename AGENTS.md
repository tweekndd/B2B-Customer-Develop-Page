# AI Trade Customer Analyzer — Agent Guide

A FastAPI web application for foreign trade customer discovery, AI analysis, scoring, and multi-source email finding. Monolithic Python backend with Jinja2 frontend.

## Quick Start

```bash
pip install -r requirements.txt
set DEEPSEEK_API_KEY=sk-xxx
set SERPAPI_API_KEY=xxx       # or TAVILY_API_KEY
python main.py                # → http://localhost:8000
```

## Essential Commands

| Command | Purpose |
|---------|---------|
| `python main.py` | Run production (autocreate dirs, no reload) |
| `python -m uvicorn main:app --reload` | Dev with hot reload |
| `pytest tests/` | Run all tests (isolated SQLite DB) |
| `pytest tests/test_X.py -v` | Single test file |

**Never** run `python main.py` with `reload=True` on Windows — it causes route registration bugs (`main.py:101-107` comment explains). Use `uvicorn --reload` instead.

## Architecture Overview

```
main.py (FastAPI app)
  ├── app/api/          ← 7 route modules (injected via APIRouter)
  ├── app/services/     ← ~20 service modules (business logic)
  ├── app/templates/    ← Jinja2 HTML (Chinese UI)
  ├── app/static/       ← Single JS, Single CSS
  └── app/database.py   ← SQLAlchemy models + auto-migration
```

### API Routing (`app/api/__init__.py`)

All routes mount under `/api` prefix. Sub-modules use `router = APIRouter(tags=[...])` **without** prefix — the prefix is inherited. 7 sub-routers are merged into one:

| Module | Tags | Key endpoints |
|--------|------|--------------|
| `customers.py` | customers | CRUD, import/export, analyze, add-emails |
| `discovery.py` | discovery | Search tasks, SSE stream, keyword expansion |
| `sync.py` | sync | Multi-device data sync (export/import JSON) |
| `config.py` | config | Read/write JSON config files, schema validation |
| `hunter.py` | hunter | Hunter.io email lookup |
| `tomba.py` | tomba | Tomba.io email lookup |
| `waterfall.py` | waterfall | Multi-source cascaded email discovery |

### Service Layer (`app/services/`)

Key service responsibilities and data flow:

1. **Discovery Flow**: `search_task_service.py` orchestrates the full pipeline:
   - `keyword_expander.py` → AI generates related keywords in target language
   - `google_discovery.py` or `tavily_discovery.py` → search web (runtime-switchable via `set_search_engine()`)
   - `company_filter.py` → filter out social media, news, etc.
   - `url_normalizer.py` → normalize URLs
   - `deduplication.py` → domain + fuzzy name dedup
   - `website_scraper.py` → scrape /about /services etc.
   - `email_extractor.py` → extract target-prefix emails
   - `keyword_analyzer.py` → hit positive/negative keywords
   - `deepseek_analyzer.py` → AI analysis (company type, hook, etc.)
   - `scoring_engine.py` → 5-dimension rule-based scoring

2. **Email Discovery**: `waterfall_discovery.py` cascades:
   - `hunter_service.py` → `tomba_service.py` → `prospeo_service.py` → scrape mailto:
   - Configurable via `EMAIL_DISCOVERY_MIN_RESULTS` (default 2)
   - Scoring: Tomba(30) > Prospeo(28) > Hunter(25) > scraped(10)

3. **Cache**: 5 cache tables with TTL-based cleanup via `cache_manager.py` + startup cleanup

## Database

**Default**: SQLite at `app/customers.db`  
**Override**: `DATABASE_URL` env var (PostgreSQL supported)

**8 tables**: Customer, SearchTask, SearchCache, WebsiteCache, AnalysisCache, HunterCache, TombaCache, ProspeoCache, EmailQuotaLog

**Auto-migration**: `init_db()` in `database.py:238` creates tables + adds missing columns via `ALTER TABLE ADD COLUMN`. Indexes are created with `CREATE INDEX IF NOT EXISTS`. No Alembic or migration tooling.

**Key Customer fields**: `scrape_status` / `ai_status` / `fail_reason` track processing state. `emails` is a JSON string, not a relation. Scores are individual columns (`industry_score`..`total_score`).

## Configuration

Two JSON config files in `app/services/`:

| File | Purpose | Editing |
|------|---------|---------|
| `industry_config.json` | Scoring rules, keywords, priority thresholds | Via `/api/config` UI or direct edit |
| `country_weights.json` | Country → score mapping | Same |

**Gotcha**: Both are `lru_cache`'d in `scoring_engine.py`. After writing, call `invalidate_config_cache()` + `invalidate_keyword_cache()`. The `/api/config` PUT endpoint handles this. Direct file edits require server restart.

## External APIs (all via env vars)

| API | Env var | Free tier | Notes |
|-----|---------|-----------|-------|
| DeepSeek | `DEEPSEEK_API_KEY` | Paid | AI analysis + keyword expansion. Model: `deepseek-v4-flash` |
| SerpAPI | `SERPAPI_API_KEY` | 250/mo | Google search |
| Tavily | `TAVILY_API_KEY` | 1000/mo | Web search (preferred if both configured) |
| Hunter.io | `HUNTER_API_KEY` | 25/mo | Email domain search |
| Tomba.io | `TOMBA_API_KEY` + `SECRET` | 25/mo | Richer email data (LinkedIn, phone, score) |
| Prospeo.io | `PROSPEO_API_KEY` | Paid | Search+Enrich, 1 credit/email |

**Search engine auto-detection**: If `TAVILY_API_KEY` set → Tavily; else if `SERPAPI_API_KEY` → SerpAPI. Override with `SEARCH_ENGINE=tavily|serpapi`.

## Key Patterns & Gotchas

### Testing
- Tests use **separate SQLite file** (`test_api.db`), not production DB
- `conftest.py` adds project root to `sys.path`
- Config files are **backed up** at session start and **restored** after each test (protects production config)
- Each test function drops and recreates all tables

### Async Architecture
- `main.py` uses `lifespan` context manager (not deprecated `@app.on_event`)
- Search tasks run via `asyncio.get_event_loop().create_task(...)` — fire-and-forget
- SSE streaming (`/discovery/task-stream/{id}`) pushes real-time progress to frontend
- All services that call external APIs are `async def`
- Some services (Hunter, Tomba, Prospeo clients) remain synchronous with `httpx` in sync mode

### Caching
- 5 cache tables, each with different TTL:
  - `search_cache`: 30 days
  - `website_cache`: 7 days
  - `analysis_cache`: content hash-based (permanent if content unchanged)
  - `hunter_cache` / `tomba_cache` / `prospeo_cache`: env configurable (default 7 days)
- Manual cache cleanup endpoint: `POST /admin/cleanup-cache`
- Cache hits don't consume API quotas

### Deduplication
- `deduplication.py` uses domain matching (primary) + fuzzy company name matching (fallback)
- Company name normalization removes legal suffixes (`Inc`, `S.A. de C.V.`, `GmbH`, etc.), punctuation, and stop words
- **Order matters**: complex suffix patterns must precede simple ones (e.g., `S.A. de C.V.` before `S.A.`)

### Multi-language Search
- `country_language_map.py` maps 130+ countries to Google hl/lr/cr parameters
- `keyword_expander.py` uses this to generate keywords in the target language
- `google_discovery.py` passes these params to SerpAPI

### Email Extraction
- `email_extractor.py` targets specific prefixes: `info`, `sales`, `contact`, `procurement`, `project`, `marketing`
- `waterfall_discovery.py` filters out generic blacklist prefixes (`noreply`, `support`, `postmaster`, etc.)

### Scoring Engine
5 dimensions (configurable via JSON):
- Industry match: 30pts (keyword weight * frequency, capped at weight max 5)
- Project match: 25pts (has projects page + industry content relevance)
- Company type: 20pts (EPC=20, Contractor=18, Manufacturer=12, etc.)
- Country priority: 15pts (from country_weights.json)
- Contact completeness: 10pts (tiered by email count)

Priority: A(≥80) > B(≥60) > C(≥40) > D

### Frontend
- Pure Jinja2 templates (no SPA framework)
- Shared JS in `app/static/js/app.js` with IntersectionObserver animations, number counting, fetch timeout helper
- SSE for real-time task progress (replaced polling in V3.1.1)
- Chinese language UI throughout

### Sync Script
- `sync.sh` supports `export|import|status` for multi-device data sharing
- Works via REST API endpoints (`/api/sync/export`, `/api/sync/import`)
- Designed for iCloud/Dropbox/USB workflows
