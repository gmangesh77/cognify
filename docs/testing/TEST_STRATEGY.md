# Test Strategy: Cognify

## 1. Testing Objectives
- Ensure all PRD acceptance criteria are verifiable through automated tests
- Maintain ≥80% code coverage on new code, ≥70% overall
- Catch regressions before they reach production
- Enable confident, frequent deployments
- Validate agent behavior deterministically despite LLM non-determinism

## 2. Test Pyramid

```
        /‾‾‾‾‾‾‾‾‾\
       /   E2E     \        ~10% — Critical user journeys (Playwright)
      /   Tests     \
     /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\
    / Integration Tests \    ~20% — API + agent workflows + DB (TestContainers)
   /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\
  /     Unit Tests        \  ~70% — Services, models, utils (pytest + mocks)
 /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\
```

### Unit Tests (~70%)
- **Scope**: Individual functions, classes, and methods in isolation
- **Tools**: pytest, pytest-asyncio, unittest.mock, freezegun
- **Mocking**: External APIs (LLM, trend sources, publishing APIs), database, Redis, Weaviate
- **Speed target**: Full unit suite < 60 seconds
- **Examples**:
  - Topic ranking algorithm with various score distributions
  - SEO optimization rules (title length, keyword density)
  - Content formatting for different platforms (Ghost, WordPress, Medium)
  - Agent state transitions and error handling

### Integration Tests (~20%)
- **Scope**: Service boundaries, database operations, agent workflows, API endpoints
- **Tools**: pytest, httpx.AsyncClient, TestContainers (PostgreSQL, Redis, Weaviate)
- **Real dependencies**: PostgreSQL for data persistence, Redis for caching, Weaviate for vector search
- **Mocked**: LLM APIs (use FakeLLM with recorded responses), external trend APIs
- **Speed target**: Full integration suite < 5 minutes
- **Examples**:
  - FastAPI endpoint → service → database round-trip
  - Research agent workflow with mocked LLM but real vector DB
  - Publishing service → platform API integration (mocked external endpoint)
  - Celery task enqueue → execute → result storage

### E2E Tests (~10%)
- **Scope**: Critical user journeys through the full stack
- **Tools**: Playwright (browser automation)
- **Environment**: Docker Compose with all services running
- **Speed target**: Full E2E suite < 10 minutes
- **Critical journeys**:
  - User logs in → views dashboard → sees trending topics
  - User triggers topic scan → views discovered topics → starts research
  - User views generated article → publishes to platform
  - User configures settings → adds API key → connects publishing platform

## 3. Agent-Specific Testing Strategy

### Challenge: LLM Non-Determinism
LLM responses vary between calls, making traditional assertion-based testing insufficient.

### Approach: Layered Agent Testing
1. **Tool call tests (unit)**: Verify individual tools (web search, vector retrieval) return expected shapes
2. **State transition tests (unit)**: Verify agent state machine transitions correctly given mocked tool results
3. **Workflow tests (integration)**: Run full agent graphs with FakeLLM (deterministic responses) and real vector DB
4. **Behavioral tests (integration)**: Assert on structural properties (e.g., "article has ≥3 sections", "all claims have citations") rather than exact content
5. **Snapshot tests (E2E)**: Record golden agent runs; flag deviations > threshold for human review

### FakeLLM Configuration
```python
# tests/conftest.py
@pytest.fixture
def fake_llm():
    return FakeLLM(responses={
        "plan_research": '{"facets": ["security trends", "recent incidents", "expert analysis"]}',
        "generate_outline": '{"sections": ["Introduction", "Key Findings", "Analysis", "Conclusion"]}',
        "draft_section": "This is a test section with proper structure and citations.",
    })
```

## 4. Coverage Requirements

| Component | Minimum Coverage | Rationale |
|-----------|-----------------|-----------|
| API routes | 90% | Entry points — must handle all edge cases |
| Agent orchestration | 85% | Core business logic — failures are costly |
| Services (SEO, formatting) | 80% | Business rules must be verifiable |
| Models/schemas | 80% | Data integrity is critical |
| Publishing integrations | 85% | External API failures need graceful handling |
| Utils/config | 70% | Lower risk, simpler logic |
| Frontend components | 75% | Visual regressions caught by E2E |

## 5. Testing Environments

| Environment | Purpose | Data | LLM |
|-------------|---------|------|-----|
| Local (pytest) | Developer feedback loop | In-memory / TestContainers | FakeLLM |
| CI (GitHub Actions) | PR validation | TestContainers | FakeLLM |
| Staging | Pre-production validation | Seeded test data | Real LLM (rate-limited) |
| Production | Smoke tests only | Production data | Real LLM |

## 6. CI Integration
- Unit tests run on every push (< 60s)
- Integration tests run on PR creation and updates (< 5min)
- E2E tests run before merge to main (< 10min)
- Coverage report posted as PR comment (fail if below thresholds)
- SAST scan (Bandit + Semgrep) runs in parallel with tests
- Secret scan (detect-secrets) runs on every commit

## 7. Test Data Management
- **Factories**: Use factory_boy for creating test fixtures with realistic data
- **Fixtures**: Shared pytest fixtures in `tests/conftest.py` for common setup
- **Recorded responses**: Store API response fixtures in `tests/fixtures/` for deterministic replay
- **Seeding**: Staging environment seeded with representative topics, articles, and publications

## 8. Performance Testing
- **Load testing**: Locust tests for API endpoints (target: 100 concurrent users)
- **Agent throughput**: Benchmark end-to-end pipeline (target: 10 articles/hour)
- **Database queries**: SQLAlchemy query logging + EXPLAIN ANALYZE for slow queries (> 100ms)
- **Frequency**: Monthly load test runs; query analysis on every schema change
