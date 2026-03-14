from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COGNIFY_")

    app_name: str = "Cognify"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
    rate_limit_default: str = "100/minute"
    api_v1_prefix: str = "/api/v1"
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 15
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
