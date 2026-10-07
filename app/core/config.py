from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MEMORY_REPO_PATH: str = "/data/memory"
    CHROMA_DB_PATH: str = "/data/chroma"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    CHROMA_HOST: str = "agent-memory-chroma"
    CHROMA_PORT: int = 8000
    GIT_AUTHOR_NAME: str = "Agent Memory"
    GIT_AUTHOR_EMAIL: str = "agent-memory@local"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
