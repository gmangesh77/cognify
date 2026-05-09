from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COGNIFY_", env_file=".env", env_file_encoding="utf-8"
    )

    app_name: str = "Cognify"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    rate_limit_default: str = "100/minute"
    api_v1_prefix: str = "/api/v1"
    # Public-facing base URL of this API. Used to absolutify relative
    # `generated_assets/...` URLs when serving the dashboard, and as a
    # default for publishing transformers when no per-call override is
    # given. Override via COGNIFY_API_BASE_URL.
    api_base_url: str = "http://localhost:8000"
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 1440
    jwt_refresh_token_expire_days: int = 7
    # Topic ranking weights (must sum to 1.0)
    relevance_weight: float = 0.4
    recency_weight: float = 0.3
    velocity_weight: float = 0.2
    diversity_weight: float = 0.1
    # Embedding / dedup
    embedding_model: str = "all-MiniLM-L6-v2"
    dedup_similarity_threshold: float = 0.85
    # Hacker News integration
    hn_api_base_url: str = "https://hn.algolia.com/api/v1"
    hn_default_max_results: int = 30
    hn_default_min_points: int = 10
    hn_points_cap: float = 300.0
    hn_request_timeout: float = 10.0
    # Google Trends integration
    gt_language: str = "en-US"
    gt_timezone_offset: int = 360
    gt_default_country: str = "united_states"
    gt_default_max_results: int = 30
    gt_request_timeout: float = 15.0
    # Reddit integration
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "cognify:v1.0 (by /u/cognify-bot)"
    reddit_default_subreddits: list[str] = [
        "cybersecurity",
        "programming",
        "netsec",
        "technology",
    ]
    reddit_score_cap: float = 1000.0
    reddit_request_timeout: float = 15.0
    # NewsAPI integration
    newsapi_api_key: str = ""
    newsapi_base_url: str = "https://newsapi.org/v2"
    newsapi_request_timeout: float = 10.0
    newsapi_default_category: str = "technology"
    newsapi_default_country: str = "us"
    # arXiv integration
    arxiv_api_base_url: str = "https://export.arxiv.org/api/query"
    arxiv_request_timeout: float = 15.0
    arxiv_default_categories: list[str] = [
        "cs.CR",
        "cs.AI",
        "cs.LG",
    ]
    # SerpAPI integration
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search"
    serpapi_timeout: float = 10.0
    serpapi_results_per_query: int = 10
    # Semantic Scholar integration
    semantic_scholar_base_url: str = "https://api.semanticscholar.org"
    semantic_scholar_api_key: str = ""
    semantic_scholar_timeout: float = 10.0
    semantic_scholar_results_per_query: int = 5
    # Milvus
    milvus_uri: str = "./milvus_data.db"
    milvus_collection_name: str = "research_chunks"
    # Chunking
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 50
    # Retrieval
    top_k_retrieval: int = 5
    # LLM — Anthropic (empty = NoOp fallback, no real generation)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    # Content pipeline model names (for Provenance tracking)
    primary_model_name: str = "claude-sonnet-4"
    drafting_model_name: str = "claude-sonnet-4"
    embedding_version: str = "v1"
    # Encryption (Fernet key for API key encryption at rest)
    encryption_key: str = ""
    # Database (empty = in-memory repos; set via COGNIFY_DATABASE_URL)
    database_url: str = ""
    # Visual asset generation
    chart_output_dir: str = "generated_assets/charts"
    # AI illustration generation (OpenAI DALL-E)
    openai_api_key: str = ""
    illustration_output_dir: str = "generated_assets/illustrations"
    dalle_model: str = "dall-e-3"
    illustration_timeout: float = 30.0
    # Diagram generation (Mermaid CLI)
    diagram_output_dir: str = "generated_assets/diagrams"
    # Visuals — generation (Epic 10 / VISUAL-004)
    enable_image_planner: bool = True  # flipped at end of Phase 5 / VISUAL-008
    # dalle_3 | gemini_flash | gemini_3_pro | imagen_4
    # Default to dalle_3 because OpenAI keys are commonly available;
    # Google providers require COGNIFY_GOOGLE_AI_API_KEY.
    default_image_provider: str = "dalle_3"
    image_model_gemini_flash: str = "gemini-2.5-flash-image"
    image_model_gemini_3_pro: str = "gemini-3-pro-image-preview"
    image_model_imagen_4: str = "imagen-4.0-generate-001"
    image_render_concurrency: int = 3
    image_planner_max_images_per_section: int = 4
    google_ai_api_key: str = ""
    imagen_4_enabled: bool = False  # gates Premium tier in UI
    gemini_3_pro_enabled: bool = True  # gates Mid tier (preview model)
    visuals_output_dir: str = "generated_assets/visuals"
    image_provider_timeout: float = 30.0
    # Visuals — object storage (MinIO / S3)
    minio_enabled: bool = False
    minio_endpoint: str = ""  # host:port, no scheme
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "cognify-visuals"
    minio_public_url: str = ""  # base URL prepended to object keys (CDN or proxy)
    minio_use_ssl: bool = False
    minio_region: str = "us-east-1"
    # Visuals — image-import safety (SSRF guard + upload validation)
    fetch_image_max_size_mb: int = 10
    fetch_image_allowed_mime: list[str] = [
        "image/png",
        "image/jpeg",
        "image/webp",
    ]
    fetch_image_timeout_s: float = 10.0
    fetch_image_max_redirects: int = 3
    # Publishing — Ghost CMS
    ghost_api_url: str = ""
    ghost_admin_api_key: str = ""  # format: "id:secret"
    # Publishing — Medium (deprecated API, mock-only)
    medium_api_token: str = ""
    medium_user_id: str = ""
    # Publishing — LinkedIn (OAuth 2.0, link sharing via Posts API)
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_author_urn: str = ""  # "urn:li:organization:XXX" or "urn:li:person:XXX"
    linkedin_access_token: str = ""  # stored via OAuth callback
    linkedin_refresh_token: str = ""  # stored via OAuth callback
