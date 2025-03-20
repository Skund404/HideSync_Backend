# File: app/core/config.py
"""
Configuration settings for HideSync.

This module defines application settings using Pydantic's BaseSettings,
which supports environment variable loading and validation.
"""

import os
import secrets
from typing import Any, Dict, List, Optional, Union

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

    # JWT Settings
    JWT_ALGORITHM: str = "HS256"
    TOKEN_URL: str = "/api/v1/auth/login"

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """
        Parse CORS origins from environment variable.

        Args:
            v: String or list with CORS origins

        Returns:
            List of validated CORS origins
        """
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    # Changed from PostgresDsn to str to support both SQLite and PostgreSQL
    DATABASE_URL: Optional[str] = None
    DATABASE_HOST: Optional[str] = None
    DATABASE_PORT: Optional[str] = None
    DATABASE_USER: Optional[str] = None
    DATABASE_PASSWORD: Optional[str] = None
    DATABASE_NAME: Optional[str] = None

    # SQLCipher
    USE_SQLCIPHER: bool = True
    DATABASE_PATH: str = "hidesync.db"
    DATABASE_ENCRYPTION_KEY: str = "change-me-in-production"

    # Key Management
    KEY_MANAGEMENT_METHOD: str = "file"  # Options: file, environment, aws, azure, gcp
    KEY_FILE_PATH: str = "/etc/hidesync/keys/db.key"
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
        """
        Assemble database connection string.

        Args:
            v: Existing connection string or None
            values: Current settings values

        Returns:
            Complete database connection string
        """
        if isinstance(v, str):
            return v

        # Build connection string from components if provided
        if (
            values.get("DATABASE_HOST")
            and values.get("DATABASE_PORT")
            and values.get("DATABASE_USER")
            and values.get("DATABASE_NAME")
        ):
            password = values.get("DATABASE_PASSWORD", "")
            return f"postgresql://{values['DATABASE_USER']}:{password}@{values['DATABASE_HOST']}:{values['DATABASE_PORT']}/{values['DATABASE_NAME']}"

        # Fall back to SQLite
        return f"sqlite:///{values.get('DATABASE_PATH', 'hidesync.db')}"

    # Skip PostgreSQL validation for SQLite URLs
    @validator("DATABASE_URL")
    def validate_database_url(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate database URL, allowing both PostgreSQL and SQLite.

        Args:
            v: Database URL string

        Returns:
            Validated database URL
        """
        if not v:
            return v

        # Skip validation for SQLite URLs
        if v.startswith("sqlite:"):
            return v

        # For PostgreSQL URLs, you could add additional validation here if needed
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

        case_sensitive = True
        env_file = ".env"


# Create settings instance
settings = Settings()
