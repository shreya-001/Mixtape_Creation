from __future__ import annotations

import json
import os
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import RedirectResponse

from ..core.emailer import send_login_code
from ..core.security import generate_login_code, issue_jwt, verify_jwt
from ..db.auth import SQLiteAuthStore
from ..core.config import settings
from ..schemas.auth import MeResponse, RequestCodeBody, TokenResponse, VerifyCodeBody

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow


router = APIRouter(prefix="/auth", tags=["auth"])
store = SQLiteAuthStore(settings.storage_root / "db" / "auth.sqlite3")

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> MeResponse:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = verify_jwt(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return MeResponse(user_id=str(payload["sub"]), email=str(payload["email"]))


@router.post("/request_code")
def request_code(body: RequestCodeBody):
    email = body.email.lower()
    code = generate_login_code()
    salt = secrets.token_hex(16)
    store.upsert_login_code(email, code, salt)
    send_login_code(email, code)
    return {"ok": True}


@router.post("/verify_code", response_model=TokenResponse)
def verify_code(body: VerifyCodeBody) -> TokenResponse:
    email = body.email.lower()
    code = body.code.strip()
    if not store.verify_login_code(email, code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    # Create user if needed
    existing = store.get_user_by_email(email)
    if existing is None:
        user_id = store.get_or_create_user(user_id=str(uuid.uuid4()), email=email)
    else:
        user_id = existing[0]

    token = issue_jwt(user_id=user_id, email=email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(user: MeResponse = Depends(get_current_user)) -> MeResponse:
    return user


GOOGLE_LOGIN_SCOPES = [
    # Use full userinfo scopes to avoid oauthlib "Scope has changed" error.
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _google_client_id() -> str:
    data = json.loads(settings.youtube_client_secrets.read_text(encoding="utf-8"))
    if "web" in data and "client_id" in data["web"]:
        return data["web"]["client_id"]
    if "installed" in data and "client_id" in data["installed"]:
        return data["installed"]["client_id"]
    raise RuntimeError("client_id not found in client_secrets.json")


@router.get("/google/start")
def google_start():
    if not settings.youtube_client_secrets.exists():
        raise HTTPException(status_code=400, detail="Missing client_secrets.json")

    state = str(uuid.uuid4())
    store.create_login_oauth_state(state, ttl_seconds=600)

    try:
        flow = Flow.from_client_secrets_file(
            str(settings.youtube_client_secrets),
            scopes=GOOGLE_LOGIN_SCOPES,
            redirect_uri=settings.google_oauth_redirect_uri,
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid client_secrets.json (download it from Google Cloud Console). Error: {e}",
        )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return {"authorization_url": auth_url, "state": state}


@router.get("/google/callback")
def google_callback(code: str, state: str):
    if not store.consume_login_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid/expired state")

    try:
        flow = Flow.from_client_secrets_file(
            str(settings.youtube_client_secrets),
            scopes=GOOGLE_LOGIN_SCOPES,
            redirect_uri=settings.google_oauth_redirect_uri,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid client_secrets.json. Error: {e}")
    try:
        # Allow the token response scope to be a superset of requested scopes.
        # This commonly happens if the user previously granted additional scopes
        # (e.g. youtube.upload) during another consent flow.
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
        flow.fetch_token(code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code for token: {e}")
    creds = flow.credentials
    if not getattr(creds, "id_token", None):
        raise HTTPException(status_code=400, detail="Missing id_token")

    info = google_id_token.verify_oauth2_token(
        creds.id_token,
        GoogleRequest(),
        _google_client_id(),
    )
    email = str(info.get("email", "")).lower()
    if not email:
        raise HTTPException(status_code=400, detail="Google account email not available")

    existing = store.get_user_by_email(email)
    if existing is None:
        user_id = store.get_or_create_user(user_id=str(uuid.uuid4()), email=email)
    else:
        user_id = existing[0]

    token = issue_jwt(user_id=user_id, email=email)

    # Redirect back to Streamlit with token in query string
    base = settings.streamlit_redirect_base.rstrip("/")
    return RedirectResponse(url=f"{base}/?token={token}")


