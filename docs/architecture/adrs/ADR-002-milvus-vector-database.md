---

## status: "accepted"
date: 2026-03-13
decision-makers: ["Engineering Team"]
supersedes: "Initial architecture spec (Weaviate selection)"

# ADR-002: Milvus for Vector Database (replacing Weaviate)

## Context and Problem Statement

Cognify's RAG pipeline (RESEARCH-003) requires a vector database to store document embeddings and perform similarity search for context retrieval during article generation. The initial architecture spec selected Weaviate, but before implementation begins, we are re-evaluating this choice against alternatives.

The vector DB must support:

- Storage and retrieval of document chunk embeddings (all-MiniLM-L6-v2, 384 dimensions)
- Top-k cosine similarity search (k=5) with metadata filtering (source, date, topic)
- Ingestion of 50K+ embeddings with sub-200ms P95 query latency
- Easy local development setup (Docker or embedded mode)
- Python SDK with LangChain integration
- Open-source with no mandatory paid cloud dependency

## Decision Drivers

- **Cost**: No paid cloud dependency for core functionality — self-hosted must be fully functional
- **Use case fit**: Cognify performs straightforward RAG retrieval (embed → store → query top-k), not complex multi-modal or graph-based searches
- **Embedding ownership**: We embed externally via sentence-transformers — built-in vectorization modules add no value
- **Operational simplicity**: Lightweight local development; manageable production deployment on Kubernetes
- **Ecosystem maturity**: Stable Python SDK, proven LangChain integration, active maintenance
- **Scale horizon**: 50K embeddings at launch, potential growth to 500K+ within a year

## Considered Options

- **Weaviate** — Hybrid search engine with built-in vectorization modules
- **Milvus** — Purpose-built vector similarity search engine
- **Qdrant** — Rust-based vector search engine with rich filtering
- **pgvector** — PostgreSQL extension for vector similarity search

## Decision Outcome

Chosen option: **Milvus**, because it is purpose-built for vector similarity search, fully open-source (Apache 2.0), offers the best performance-to-resource ratio for Cognify's straightforward RAG workload, and provides Milvus Lite for frictionless local development.

### Consequences

- Good, because Milvus is fully open-source (Apache 2.0) with no paid cloud requirement for any feature
- Good, because Milvus Lite enables embedded in-process vector search for development and testing — no Docker container needed for local dev
- Good, because purpose-built architecture delivers superior query performance for pure vector similarity workloads
- Good, because proven at billion-scale datasets — Cognify's 50K-500K scale is well within comfort zone
- Good, because mature Python SDK (pymilvus) and LangChain integration (`langchain-milvus`)
- Good, because lightweight resource footprint compared to Weaviate for equivalent workloads
- Bad, because hybrid search (BM25 + vector) is less mature than Weaviate's — if needed later, requires additional tuning
- Bad, because Milvus standalone requires etcd + MinIO for production deployment (more moving parts than pgvector)
- Bad, because slightly smaller community mindshare than Weaviate in the LangChain ecosystem

### Confirmation

Validate through: benchmark during RESEARCH-003 implementation — measure ingestion throughput (target: 1000 embeddings/sec), query latency (target: P95 < 50ms for k=5 at 50K scale), and memory footprint. If benchmarks fail, Qdrant is the fallback option.

## Pros and Cons of the Options

### Milvus

- Good, because purpose-built for vector similarity search — optimized query engine, not a bolted-on feature
- Good, because Apache 2.0 license — fully open-source, no feature gating behind paid tiers
- Good, because Milvus Lite allows embedded mode for development and testing (no external dependencies)
- Good, because proven at massive scale (billion+ vectors) with companies like Salesforce, PayPal, Shopee
- Good, because GPU-accelerated indexing available for future scaling needs
- Good, because supports IVF_FLAT, HNSW, and DiskANN index types — can tune for latency vs. memory trade-off
- Good, because metadata filtering on scalar fields (source, date, topic_id) is first-class
- Good, because mature Python SDK and LangChain integration (`langchain-milvus`)
- Neutral, because hybrid search (sparse + dense) was added in Milvus 2.4 but is less battle-tested than Weaviate's
- Bad, because production deployment requires etcd (metadata) + MinIO (object storage) alongside Milvus server
- Bad, because operational complexity is higher than pgvector for small-scale deployments

### Weaviate (original selection)

- Good, because best-in-class hybrid search combining BM25 keyword matching with vector similarity in a single query
- Good, because built-in vectorization modules can embed at ingest time (text2vec-transformers, etc.)
- Good, because GraphQL and REST APIs with rich querying capabilities
- Good, because built-in multi-tenancy support for future SaaS scenarios
- Good, because strong LangChain ecosystem presence with extensive documentation
- Bad, because Weaviate Cloud (managed hosting) is paid — self-hosted is BSD-3 but operationally heavier
- Bad, because built-in vectorization modules are unused — Cognify embeds externally via sentence-transformers
- Bad, because heavier resource footprint than Milvus for pure vector search workloads
- Bad, because hybrid search capability, while excellent, is not required for Cognify's current RAG pattern (embed externally, retrieve by vector similarity)
- Bad, because over-provisioned for the use case — paying operational cost for features we don't use

### Qdrant

- Good, because Rust-based engine with excellent single-node performance
- Good, because rich filtering with payload indexes — strong metadata querying
- Good, because simple deployment (single binary, no external dependencies for standalone)
- Good, because Apache 2.0 license, fully open-source
- Good, because built-in quantization for memory-efficient deployments
- Neutral, because smaller community than Milvus/Weaviate but growing rapidly
- Bad, because no embedded/lite mode for local development (requires running a server)
- Bad, because less proven at very large scale compared to Milvus
- Bad, because LangChain integration exists but is less mature than Milvus/Weaviate

### pgvector (PostgreSQL extension)

- Good, because zero additional infrastructure — reuses existing PostgreSQL 16 instance
- Good, because simplest operational model (no new database to manage)
- Good, because ACID transactions on vector data alongside relational data
- Good, because sufficient for small-scale RAG (< 100K vectors)
- Bad, because query performance degrades significantly above 100K vectors without careful tuning
- Bad, because limited index types (IVF-Flat, HNSW) with less optimization than purpose-built engines
- Bad, because no built-in sharding or distributed deployment for horizontal scaling
- Bad, because embedding dimension and index tuning competes with OLTP workload on the same PostgreSQL instance
- Bad, because would need migration to a dedicated vector DB when scale exceeds PostgreSQL's practical limits

## Migration Impact

Switching from Weaviate to Milvus affects:

| Artifact | Change Required |
|----------|----------------|
| `docs/architecture/HIGH_LEVEL_ARCHITECTURE.md` | Replace Weaviate references with Milvus |
| `RESEARCH-003` backlog item | Update acceptance criteria to reference Milvus/pymilvus |
| `docker-compose.yml` (future) | Milvus standalone + etcd + MinIO instead of Weaviate container |
| `requirements.txt` / `pyproject.toml` | `pymilvus` + `langchain-milvus` instead of `weaviate-client` + `langchain-weaviate` |
| Observability plan | Update `cognify_vector_operations_total` metric labels |

**Update (2026-03-17):** RESEARCH-003 is now Done (PR #17). Milvus integration implemented: `MilvusService`, `MilvusRetriever`, `TokenChunker`, and `index_findings` orchestrator node. Uses `pymilvus` directly (not `langchain-milvus`). Milvus Lite for dev, configurable URI for production.
