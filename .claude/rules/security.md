---
paths:
  - "src/api/**"
  - "src/auth/**"
  - "**/middleware/**"
  - "src/services/publishing/**"
  - "src/config/**"
---
# Security Development Rules

## Input Handling
- Validate ALL user inputs server-side via Pydantic models (never trust client)
- Use parameterized queries via SQLAlchemy ORM — never string concatenation for SQL
- Encode output to prevent XSS in any HTML rendering
- Validate file uploads: type, size, content scanning
- Sanitize all trend source data before indexing (prevent injection via scraped content)

## Authentication & Authorization
- Implement RBAC with least-privilege principle
- JWT: explicit algorithm (RS256), reject "none", short expiry (15min) + refresh tokens (7d)
- Session tokens: CSPRNG with ≥64 bits entropy
- Rate limit auth endpoints (5 failed attempts → 30-min lockout)
- API keys for external integrations stored encrypted in DB, never in code

## Data Protection
- Encrypt PII at rest (AES-256) and in transit (TLS 1.2+)
- Never log passwords, API keys, tokens, PII, or secrets
- Follow data classification policy for all data stores
- Implement data retention and deletion capabilities
- Trend data and scraped content must respect robots.txt and ToS

## API Key Management
- All external API keys (Google Trends, Reddit PRAW, SerpAPI, NewsAPI, Ghost, OpenAI) stored via environment variables
- Use pydantic-settings SecretStr for sensitive config values
- Rotate API keys quarterly; alert on key expiration
- Audit log all API key access and usage

## OWASP Top 10 Awareness
Every PR touching auth, APIs, or data MUST address:
- A01: Broken Access Control — verify ownership on all data access
- A02: Crypto Failures — no weak algorithms (MD5, SHA-1 for security)
- A03: Injection — parameterized everything (SQL, LLM prompts, shell commands)
- A07: Auth Failures — brute-force protection, secure password storage (bcrypt)
- A09: Logging Failures — log security events, never log secrets

## LLM-Specific Security
- Sanitize all content before passing to LLM prompts (prevent prompt injection)
- Validate LLM outputs before publishing (content safety filters)
- Rate limit LLM API calls to prevent cost overruns
- Never expose raw LLM errors to end users
