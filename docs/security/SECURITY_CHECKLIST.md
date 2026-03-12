# Security Checklist: Cognify

## Sprint Security Gates
Every sprint, the following security checks must pass before release.

### 1. Authentication & Authorization
- [ ] All API endpoints require JWT authentication (except `/health`, `/docs`)
- [ ] JWT tokens use RS256 algorithm with short expiry (15 minutes)
- [ ] Refresh tokens are rotated on use and invalidated on logout
- [ ] RBAC enforced at middleware level (admin, editor, viewer roles)
- [ ] Rate limiting on authentication endpoints (5 attempts → 30-min lockout)
- [ ] Password hashing uses bcrypt with cost factor ≥ 12

### 2. Input Validation
- [ ] All API inputs validated via Pydantic models (no raw dict access)
- [ ] File uploads restricted: type whitelist (png, jpg, svg), max 10MB, content-type verification
- [ ] URL inputs validated and restricted to allowed domains for publishing
- [ ] SQL injection prevented via SQLAlchemy ORM (no raw SQL strings)
- [ ] All user-supplied text sanitized before LLM prompt inclusion (prompt injection prevention)

### 3. Data Protection
- [ ] API keys encrypted at rest in PostgreSQL (AES-256 via pgcrypto or application-level)
- [ ] TLS 1.3 enforced for all external communication
- [ ] No PII, passwords, tokens, or API keys in logs (structlog field filtering)
- [ ] Database connections use SSL (sslmode=verify-full)
- [ ] S3 buckets for generated assets use server-side encryption (SSE-S3)

### 4. API Security
- [ ] CORS restricted to allowed origins (dashboard domain only)
- [ ] Request correlation IDs (X-Request-ID) on all responses
- [ ] Rate limiting on all public endpoints via slowapi
- [ ] Response headers: X-Content-Type-Options, X-Frame-Options, CSP
- [ ] Error responses never expose stack traces or internal details
- [ ] API versioning enforced (/api/v1/)

### 5. LLM-Specific Security
- [ ] User inputs sanitized before prompt injection (strip control sequences)
- [ ] LLM outputs filtered through content safety checks before publishing
- [ ] LLM API call costs monitored with per-user/per-session budget limits
- [ ] Generated article content scanned for embedded code/scripts before publishing
- [ ] Prompt templates versioned and reviewed (no user-controlled prompt structure)

### 6. Infrastructure Security
- [ ] Docker images use non-root user
- [ ] Docker images based on slim/distroless base images
- [ ] Container image vulnerability scan (Trivy) — zero Critical
- [ ] Kubernetes pods run with read-only root filesystem
- [ ] Network policies restrict inter-pod communication to required paths
- [ ] Secrets injected via AWS Secrets Manager (not environment variables in manifests)

### 7. Dependency Security
- [ ] `pip-audit` runs in CI — zero known vulnerabilities
- [ ] `npm audit` for frontend — zero Critical/High
- [ ] Dependabot or Renovate configured for automated dependency updates
- [ ] Third-party package licenses reviewed (no copyleft in proprietary components)

### 8. External API Integration Security
- [ ] All external API keys stored encrypted, never in code or git
- [ ] API key rotation procedure documented and tested
- [ ] Rate limiting on outbound API calls (prevent abuse/cost overrun)
- [ ] External API responses validated before processing (no blind trust)
- [ ] Webhook endpoints (if any) verify signatures

### 9. Logging & Monitoring
- [ ] Security events logged: failed auth, permission denied, rate limit hit, unusual agent behavior
- [ ] Log aggregation configured (CloudWatch / ELK)
- [ ] Alerts configured for: brute-force attempts, unusual API key usage, LLM budget exceeded
- [ ] Audit trail for admin actions (settings changes, API key additions)

### 10. Compliance
- [ ] Generated content includes AI disclosure where platform requires
- [ ] Scraped content respects robots.txt and source ToS
- [ ] Data retention policies enforced (90-day trend signals, 1-year research logs)
- [ ] User data deletion capability implemented (GDPR right to erasure)
