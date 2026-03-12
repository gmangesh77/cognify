---
paths:
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/__tests__/**"
  - "**/tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
---
# Testing Rules

## TDD Workflow (mandatory)
1. RED: Write a failing test first — cover happy path + edge cases
2. GREEN: Write minimal code to pass the test
3. REFACTOR: Clean up while keeping tests green

## Test Pyramid Ratios
- Unit tests: ~70% of suite (fast, isolated, mock externals with unittest.mock)
- Integration tests: ~20% (real PostgreSQL/Redis via TestContainers)
- E2E tests: ~10% (critical user journeys only — Playwright)

## Test Naming
- Pattern: `test_[unit]_[scenario]_[expected_result]`
- Example: `test_trend_detector_empty_response_returns_empty_list`
- Group with classes: `class TestTrendDetector:` > `def test_should_rank_by_score_when_multiple_trends:`

## Coverage Targets
- New code: ≥80% line coverage
- Critical paths (agent orchestration, publishing, API auth): ≥90%
- Overall project floor: ≥70%

## Test Independence
- No shared mutable state between tests
- Each test sets up and tears down its own fixtures
- Tests must pass in any order and in isolation
- Use pytest fixtures with appropriate scope (function default, session for DB)

## Agent Testing
- Mock LLM calls in unit tests (use LangChain's FakeLLM or recorded responses)
- Integration tests for agent workflows use a test LLM with deterministic outputs
- Test agent tool calls independently from agent logic
- Verify agent state transitions and memory updates

## Async Testing
- Use pytest-asyncio for all async test functions
- Mark async tests with `@pytest.mark.asyncio`
- Use `AsyncClient` from httpx for FastAPI endpoint testing
