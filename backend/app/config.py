from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

class Settings(BaseSettings):
    PROJECT_NAME: str = "NEXUS-X"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "supersecretkey"  # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    DATABASE_URL: str = "sqlite:///./nexus.db"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-8b-8192"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    # Left unset by default so the driver uses the connection's actual default
    # database. Hardcoding "neo4j" breaks on Neo4j Aura, which auto-generates
    # a unique default database name per instance (not literally "neo4j") -
    # only set this if you're connecting to a self-hosted Neo4j with multiple
    # named databases and need a specific one.
    NEO4J_DATABASE: Optional[str] = None
    UPLOAD_DIR: str = "uploads"
    PROCESSED_DIR: str = "processed"
    MAX_UPLOAD_SIZE_MB: int = 50

    # Comma-separated list of allowed browser origins for CORS. Defaults cover
    # local dev only - set this explicitly in production.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Optional: if set AND no users exist yet in the database, main.py creates
    # this one admin account on startup. This is the only way an admin gets
    # created without running backend/scripts/create_admin.py - there is no
    # hardcoded username/password anywhere in source.
    INITIAL_ADMIN_USERNAME: Optional[str] = None
    INITIAL_ADMIN_PASSWORD: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origins_list(self):
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

@lru_cache()
def get_settings():
    settings = Settings()
    if settings.SECRET_KEY == "supersecretkey":
        import logging
        logging.getLogger(__name__).warning(
            "[SECURITY] SECRET_KEY is set to the insecure default. All JWTs "
            "signed with it can be forged by anyone who reads this source. "
            "Set a unique SECRET_KEY in backend/.env before any real use."
        )
    return settings
