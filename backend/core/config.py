from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Pitchcraft"
    debug: bool = False

    # MongoDB
    mongodb_url: str = "mongodb://mongodb:27017"
    mongodb_db_name: str = "pitchcraft"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "pitchcraft"

    # Anthropic
    anthropic_api_key: str = ""

    # Tavily
    tavily_api_key: str = ""

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"

    # BGE-M3 embedding service
    embedding_service_url: str = "http://embedding:8001"

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    class Config:
        env_file = ".env"


settings = Settings()
