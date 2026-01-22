from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "mixtape-automation"
    storage_root: Path = Path(os.getenv("MIXTAPE_STORAGE_ROOT", "/Users/shreyanair/Mixtape_Creation/storage"))

    # Auth
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "mixtape-automation")
    jwt_ttl_seconds: int = int(os.getenv("JWT_TTL_SECONDS", "86400"))  # 24h
    login_code_ttl_seconds: int = int(os.getenv("LOGIN_CODE_TTL_SECONDS", "600"))  # 10m

    # Email (passwordless codes)
    email_mode: str = os.getenv("EMAIL_MODE", "console")  # console|smtp
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_pass: str = os.getenv("SMTP_PASS", "")
    smtp_from: str = os.getenv("SMTP_FROM", "no-reply@mixtape.local")

    # Token encryption (Fernet key, base64 urlsafe 32 bytes)
    tokens_encryption_key: str = os.getenv("TOKENS_ENCRYPTION_KEY", "")

    # YouTube OAuth
    youtube_client_secrets: Path = Path(os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secrets.json"))
    youtube_oauth_redirect_uri: str = os.getenv("YOUTUBE_OAUTH_REDIRECT_URI", "http://localhost:8000/youtube/oauth/callback")

    # Google Sign-In (login)
    google_oauth_redirect_uri: str = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    streamlit_redirect_base: str = os.getenv("STREAMLIT_REDIRECT_BASE", "http://localhost:8501")


settings = Settings()


