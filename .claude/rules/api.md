---
paths:
  - "src/api/**"
  - "src/routes/**"
  - "src/controllers/**"
---
# API Development Rules

- All endpoints require authentication unless explicitly marked public (health, docs)
- Use consistent error response format: `{ "error": { "code": str, "message": str, "details": list } }`
- Validate request bodies with Pydantic models (FastAPI dependency injection)
- Return typed responses with appropriate HTTP status codes (200, 201, 400, 401, 403, 404, 422, 500)
- Document all endpoints via FastAPI's auto-generated OpenAPI/Swagger (add summary + description)
- Implement cursor-based pagination for list endpoints (topics, articles, research sessions)
- Add rate limiting to all public endpoints via slowapi middleware
- Include X-Request-ID correlation header in all responses (generated via middleware)
- Log request metadata (method, path, status, duration) via structlog — never log request bodies with PII

## Endpoint Conventions
- Use RESTful resource naming: `/api/v1/topics`, `/api/v1/articles`, `/api/v1/research`
- Use plural nouns for collections, singular for actions: `/api/v1/articles/{id}/publish`
- Version all APIs: prefix with `/api/v1/`
- Use HTTP verbs correctly: GET (read), POST (create), PUT (full update), PATCH (partial), DELETE

## FastAPI Patterns
- Use APIRouter for route grouping by domain (topics, articles, research, publishing)
- Use Depends() for authentication, database sessions, and shared dependencies
- Use BackgroundTasks for fire-and-forget operations (triggering agent workflows)
- Use WebSocket endpoints for real-time agent workflow status updates

## Response Models
- Define explicit Pydantic response models for every endpoint
- Use `response_model_exclude_none=True` to keep payloads clean
- Include pagination metadata in list responses: `{ "data": [...], "cursor": str, "has_more": bool }`
