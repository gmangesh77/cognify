# Plan: INFRA-004 Settings Backend CRUD

## Overview
Create backend CRUD endpoints for all settings (domains, LLM config, API keys, SEO defaults, general config). Wire frontend hooks to real APIs, removing all mock data from production code.

## Phase 1: Database Models + Migration
- [ ] Add 5 SQLAlchemy tables to `src/db/tables.py`: DomainConfigRow, ApiKeyRow, LlmConfigRow, SeoDefaultsRow, GeneralConfigRow
- [ ] Create Alembic migration for all 5 tables
- [ ] Run migration and verify tables exist

## Phase 2: Repositories + Pydantic Schemas
- [ ] Create `src/db/settings_repositories.py` with PgDomainConfigRepo, PgApiKeyRepo, PgLlmConfigRepo, PgSeoDefaultsRepo, PgGeneralConfigRepo
- [ ] Create `src/api/schemas/settings.py` with all request/response models
- [ ] Create Pydantic domain models in `src/models/settings.py`

## Phase 3: Backend Router + Wiring
- [ ] Create `src/api/routers/settings.py` with all CRUD endpoints
- [ ] Wire repositories in `src/api/main.py` lifespan handler
- [ ] Register settings_router in `_register_routers()`

## Phase 4: Frontend API + Hook Update
- [ ] Create `frontend/src/lib/api/settings.ts` with all API functions
- [ ] Rewrite `frontend/src/hooks/use-settings.ts` to use real API calls
- [ ] Update topics domain selector to read from settings API

## Phase 5: Testing + Verification
- [ ] Run backend tests
- [ ] Run frontend tests
- [ ] E2E verification: save settings → restart → settings persist
