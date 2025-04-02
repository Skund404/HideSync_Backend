# File: app/core/config.py
"""
Configuration settings for HideSync.

This module defines application settings using Pydantic's BaseSettings,
which supports environment variable loading and validation.
"""

import os
import secrets
from typing import Any, Dict, List, Optional, Union

# Ensure you have pydantic > 1.8 for AnyHttpUrl and pydantic-settings installed
from pydantic import AnyHttpUrl, EmailStr, validator, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    This class uses Pydantic's BaseSettings to load configuration from
    environment variables, with validation and type conversion.
    """

    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "HideSync"

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PRODUCTION: bool = False

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days for refresh tokens
    FRONTEND_URL: str = "http://localhost:3000"  # For password reset links

    # JWT Settings
    JWT_ALGORITHM: str = "HS256"
    TOKEN_URL: str = "/api/v1/auth/login"

    # CORS - Fixed type annotation to handle both URLs and strings
    BACKEND_CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = []

    MIN_PASSWORD_LENGTH: int = 4

    # Restored validator with improved JSON parsing
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from environment variables."""
        if isinstance(v, str):
            # Try to parse as JSON string
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # Fallback to comma-separated format
                return [i.strip() for i in v.split(",")]
        return v or []

    # Database
    DATABASE_URL: Optional[str] = None
    DATABASE_HOST: Optional[str] = None
    DATABASE_PORT: Optional[str] = None
    DATABASE_USER: Optional[str] = None
    DATABASE_PASSWORD: Optional[str] = None
    DATABASE_NAME: Optional[str] = None

    # Database performance tuning
    DB_POOL_SIZE: int = 2  # Small pool size
    DB_MAX_OVERFLOW: int = 3  # Limited overflow
    DB_POOL_TIMEOUT: int = 20  # Faster timeout
    DB_POOL_RECYCLE: int = 600  # 10 minutes
    DB_DEFAULT_QUERY_LIMIT: int = 500  # Safety limit
    TRACK_MEMORY_USAGE: bool = True  # Enable memory tracking
    MEMORY_WARNING_THRESHOLD_MB: int = 200  # Early warning
    MEMORY_CRITICAL_THRESHOLD_MB: int = 400  # Critical threshold

    # SQLCipher
    USE_SQLCIPHER: bool = True
    DATABASE_PATH: str = "hidesync.db"
    DATABASE_ENCRYPTION_KEY: str = "8f353342c59546db88dd352f883e440e0a413d34149bbdced9b4fc0c84028d9e"

    # Key Management
    KEY_MANAGEMENT_METHOD: str = "file"
    KEY_FILE_PATH: str = "/etc/hidesync/dev_db.key"
    KEY_ENVIRONMENT_VARIABLE: str = "HIDESYNC_DB_KEY"
    ENFORCE_KEY_FILE_PERMISSIONS: bool = True

    # Cloud Provider Secret Management
    AWS_SECRET_NAME: str = "hidesync/database-key"
    AWS_REGION: str = "us-east-1"
    AWS_SECRET_KEY_FIELD: str = "database_key"

    AZURE_VAULT_URL: str = "https://hidesync-vault.vault.azure.net/"
    AZURE_SECRET_NAME: str = "database-key"

    GCP_PROJECT_ID: str = "hidesync-project"
    GCP_SECRET_ID: str = "database-key"
    GCP_SECRET_VERSION: str = "latest"

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        """Assemble database connection string."""
        if isinstance(v, str):
            return v
        if (
            values.get("DATABASE_HOST")
            and values.get("DATABASE_PORT")
            and values.get("DATABASE_USER")
            and values.get("DATABASE_NAME")
        ):
            password = values.get("DATABASE_PASSWORD", "")
            return f"postgresql://{values['DATABASE_USER']}:{password}@{values['DATABASE_HOST']}:{values['DATABASE_PORT']}/{values['DATABASE_NAME']}"
        return f"sqlite:///{values.get('DATABASE_PATH', 'hidesync.db')}"

    @validator("DATABASE_URL")
    def validate_database_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate database URL, allowing both PostgreSQL and SQLite."""
        if not v:
            return v
        if v.startswith("sqlite:"):
            return v
        # Add PostgreSQL validation if needed
        return v

    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None

    # Superuser
    FIRST_SUPERUSER: EmailStr = "admin@hidesync.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin"
    FIRST_SUPERUSER_USERNAME: str = "admin"
    FIRST_SUPERUSER_FULLNAME: str = "HideSync Administrator"

    # Metrics
    ENABLE_METRICS: bool = True

    class Config:
        """Pydantic settings configuration."""

        from_attributes = True
        case_sensitive = True
        env_file = ".env"  # Ensure this points to your actual .env file


# Create settings instance
settings = Settings()

# Debug logging - uncomment if needed for troubleshooting
# import logging
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)
# logger.debug(f"Loaded CORS Origins: {settings.BACKEND_CORS_ORIGINS}")