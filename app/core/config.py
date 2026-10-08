from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    MEMORY_REPO_PATH: str = "/data/memory"
    CHROMA_DB_PATH: str = "/data/chroma"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    CHROMA_HOST: str = "dejavault-chroma"
    CHROMA_PORT: int = 8000
    GIT_AUTHOR_NAME: str = "DejaVault"
    GIT_AUTHOR_EMAIL: str = "dejavault@local"
    # Used by docker-compose for SSH key mounts; not read by the app itself.
    SSH_PRIVATE_KEY_PATH: str = ""
    SSH_PUBLIC_KEY_PATH: str = ""


settings = Settings()
