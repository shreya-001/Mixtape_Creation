from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from cryptography.fernet import Fernet

from .config import settings


def generate_login_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(email: str, code: str, salt: str) -> str:
    msg = f"{email.lower()}:{code}".encode("utf-8")
    key = salt.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def issue_jwt(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_jwt(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)


def _fernet() -> Fernet:
    if not settings.tokens_encryption_key:
        raise RuntimeError("TOKENS_ENCRYPTION_KEY is not set")
    return Fernet(settings.tokens_encryption_key.encode("utf-8"))


def encrypt_text(plain: str) -> str:
    f = _fernet()
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher: str) -> str:
    f = _fernet()
    return f.decrypt(cipher.encode("utf-8")).decode("utf-8")


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode("utf-8")


