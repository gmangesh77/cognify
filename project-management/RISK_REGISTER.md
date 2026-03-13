# Risk Register: Cognify

## Risk Assessment Matrix

| Likelihood → | Low (1) | Medium (2) | High (3) |
|--------------|---------|------------|----------|
| **Impact ↓** | | | |
| **High (3)** | 3 - Medium | 6 - High | 9 - Critical |
| **Medium (2)** | 2 - Low | 4 - Medium | 6 - High |
| **Low (1)** | 1 - Low | 2 - Low | 3 - Medium |

---

## Active Risks

### RISK-001: LLM Hallucination in Published Content
- **Category**: Quality / Reputation
- **Description**: Claude or other LLMs may generate factually incorrect information that gets published to live platforms, damaging credibility.
- **Likelihood**: High (3) — LLMs hallucinate regularly, especially on niche or recent topics
- **Impact**: High (3) — Published misinformation damages brand trust and SEO
- **Risk Score**: 9 (Critical)
- **Mitigation**:
  - Enforce citation requirement: every factual claim must have a verifiable source
  - RAG pipeline grounds generation in retrieved documents
  - Automated fact-checking pass: compare generated claims against source material
  - Default "human review before publish" toggle (enabled by default)
  - Content safety filter on all LLM outputs
- **Owner**: Engineering Lead
- **Status**: Active — mitigation in progress (Sprint 1-2)

### RISK-002: External API Rate Limits and Outages
- **Category**: Technical / Reliability
- **Description**: Google Trends API (alpha), Reddit API, SerpAPI, and other external services may impose rate limits, change APIs, or experience outages, breaking the trend discovery and research pipelines.
- **Likelihood**: High (3) — Multiple external dependencies, some in alpha/preview
- **Impact**: Medium (2) — Degrades functionality but doesn't break core system
- **Risk Score**: 6 (High)
- **Mitigation**:
  - Abstract all external APIs behind adapter interfaces (easy to swap)
  - Cache trend signals in Redis (serve stale data if API unavailable)
  - Implement circuit breaker pattern (fail-fast after 5 consecutive failures)
  - Configure fallback sources (if Google Trends unavailable, rely on Reddit + HN)
  - Monitor API status and alert on degradation
- **Owner**: Backend Engineer
- **Status**: Active — adapter pattern in architecture

### RISK-003: LLM API Cost Overruns
- **Category**: Financial
- **Description**: Multi-agent research with parallel LLM calls (Claude Opus for synthesis, Sonnet for drafting) could generate unexpected costs, especially with iterative refinement loops.
- **Likelihood**: Medium (2) — Predictable per-article cost, but scaling increases
- **Impact**: High (3) — Uncontrolled costs could make the project unsustainable
- **Risk Score**: 6 (High)
- **Mitigation**:
  - Per-session token budget limits (configurable, default: 100K tokens/article)
  - Use Claude Sonnet (cheaper) for drafting, Opus only for final synthesis pass
  - Cache LLM responses for identical prompts (Redis-based)
  - Daily/weekly cost monitoring dashboard with alerts
  - Circuit breaker: halt generation if daily budget exceeded
- **Owner**: Engineering Lead
- **Status**: Active — budget limits planned for Sprint 2

### RISK-004: Copyright and Plagiarism in Generated Content
- **Category**: Legal / Compliance
- **Description**: Articles may inadvertently reproduce copyrighted text from scraped sources, exposing the project to legal liability.
- **Likelihood**: Medium (2) — LLMs can reproduce training data; scraping adds risk
- **Impact**: High (3) — Legal action, platform bans, content takedowns
- **Risk Score**: 6 (High)
- **Mitigation**:
  - Plagiarism detection scan on all generated content before publishing
  - Restrict scraping to sources with permissive ToS (no paywalled content)
  - Enforce paraphrasing: no verbatim quotes > 50 words without attribution
  - Respect robots.txt on all scraped sources
  - Legal review of content policy before production launch
- **Owner**: Product Owner
- **Status**: Active — plagiarism detection planned for Sprint 3

### RISK-005: Prompt Injection via Scraped Content
- **Category**: Security
- **Description**: Malicious content scraped from web sources could contain prompt injection payloads that manipulate LLM behavior, causing unintended outputs or data leaks.
- **Likelihood**: Medium (2) — Increasingly common attack vector
- **Impact**: Medium (2) — Could produce harmful content or expose system prompts
- **Risk Score**: 4 (Medium)
- **Mitigation**:
  - Sanitize all scraped content before inclusion in LLM prompts
  - Use structured prompt templates (not user-controlled)
  - Content safety filter on all LLM outputs
  - Log and monitor for unusual LLM output patterns
  - Input/output guardrails using Anthropic's content filtering
- **Owner**: Security Engineer
- **Status**: Active — sanitization in security rules

### RISK-006: Agent Workflow Reliability
- **Category**: Technical / Quality
- **Description**: Multi-agent workflows with 5+ steps have compounding failure probability. Any agent failure (timeout, LLM error, tool failure) could stall the entire pipeline.
- **Likelihood**: Medium (2) — Multiple failure points in long-running workflows
- **Impact**: Medium (2) — Stalled workflows require manual intervention
- **Risk Score**: 4 (Medium)
- **Mitigation**:
  - LangGraph checkpointing: resume from last successful step
  - Per-agent timeout with graceful degradation (skip non-critical steps)
  - Retry with exponential backoff for transient failures
  - Dead letter queue for permanently failed workflows
  - Alerting on stuck workflows (> 30 minutes)
- **Owner**: Backend Engineer
- **Status**: Active — architecture supports checkpointing

### RISK-007: Data Source Bias and Content Monotony
- **Category**: Product / Quality
- **Description**: System may produce formulaic, repetitive content by always drawing from the same sources and following the same generation patterns.
- **Likelihood**: Medium (2) — Common with automated content systems
- **Impact**: Low (1) — Reduced engagement but no system failure
- **Risk Score**: 2 (Low)
- **Mitigation**:
  - Diversify trend sources (minimum 3 sources per topic)
  - Track published topics to avoid repetition
  - Prompt engineering for unique angle identification
  - Configurable content tone and style parameters
  - Future: A/B testing on content engagement
- **Owner**: Product Owner
- **Status**: Monitoring — addressed by multi-source architecture

### RISK-008: Milvus Scalability at Knowledge Base Growth
- **Category**: Technical / Performance
- **Description**: As the RAG knowledge base grows (1000+ articles, 50K+ embeddings), Milvus query performance may degrade, slowing research and generation.
- **Likelihood**: Low (1) — Milvus scales well, but needs monitoring
- **Impact**: Medium (2) — Slower article generation, degraded user experience
- **Risk Score**: 2 (Low)
- **Mitigation**:
  - Index partitioning by domain
  - TTL on old embeddings (archive after 90 days)
  - Monitor query latency (alert if P95 > 200ms)
  - Milvus sharding configuration for horizontal scaling
- **Owner**: Backend Engineer
- **Status**: Monitoring — planned for post-MVP optimization

---

## Risk Summary

| Risk ID | Title | Score | Status |
|---------|-------|-------|--------|
| RISK-001 | LLM Hallucination | 9 (Critical) | Active |
| RISK-002 | External API Instability | 6 (High) | Active |
| RISK-003 | LLM Cost Overruns | 6 (High) | Active |
| RISK-004 | Copyright / Plagiarism | 6 (High) | Active |
| RISK-005 | Prompt Injection | 4 (Medium) | Active |
| RISK-006 | Agent Workflow Reliability | 4 (Medium) | Active |
| RISK-007 | Content Monotony | 2 (Low) | Monitoring |
| RISK-008 | Milvus Scalability | 2 (Low) | Monitoring |

**Review cadence**: Risks reviewed every sprint retrospective. New risks added as discovered.
