from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from ..core.config import settings
from ..core.security import decrypt_text, encrypt_text, issue_jwt
from ..db.auth import SQLiteAuthStore
from ..services.youtube import build_oauth_authorization_url, exchange_code_for_token_json, get_my_channel
from .auth import get_current_user


router = APIRouter(prefix="/youtube", tags=["youtube"])
store = SQLiteAuthStore(settings.storage_root / "db" / "auth.sqlite3")


@router.post("/oauth/start")
def oauth_start(user=Depends(get_current_user)):
    if not settings.youtube_client_secrets.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Missing YouTube client secrets file at: {settings.youtube_client_secrets}",
        )
    state = str(uuid.uuid4())
    store.create_oauth_state(state, user.user_id, ttl_seconds=600)
    url, _ = build_oauth_authorization_url(
        client_secrets_path=settings.youtube_client_secrets,
        redirect_uri=settings.youtube_oauth_redirect_uri,
        state=state,
    )
    return {"authorization_url": url, "state": state}


@router.get("/oauth/callback")
def oauth_callback(code: str, state: str | None = None):
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")
    user_id = store.consume_oauth_state(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid/expired state")

    try:
        token_json = exchange_code_for_token_json(
            client_secrets_path=settings.youtube_client_secrets,
            redirect_uri=settings.youtube_oauth_redirect_uri,
            code=code,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code for token: {e}")
    token_enc = encrypt_text(token_json)
    store.upsert_youtube_token(user_id, token_enc)

    # Issue (or refresh) a login JWT for this user so the Streamlit app stays logged in,
    # even if the OAuth flow happened in a different browser tab.
    user_row = store.get_user_by_id(user_id)
    if not user_row:
        raise HTTPException(status_code=400, detail="User not found for OAuth state")
    _, email = user_row
    token = issue_jwt(user_id=user_id, email=email)

    # After successful connection, send the user back to the Streamlit app with the token.
    base = settings.streamlit_redirect_base.rstrip("/")
    return RedirectResponse(url=f"{base}/?token={token}")


@router.get("/oauth/status")
def oauth_status(user=Depends(get_current_user)):
    token = store.get_youtube_token(user.user_id)
    return {"authorized": bool(token)}


@router.get("/me")
def youtube_me(user=Depends(get_current_user)):
    token_enc = store.get_youtube_token(user.user_id)
    if not token_enc:
        raise HTTPException(status_code=404, detail="YouTube not connected")
    token_json = decrypt_text(token_enc)

    def _persist(updated_token_json: str) -> None:
        store.upsert_youtube_token(user.user_id, encrypt_text(updated_token_json))

    return get_my_channel(token_json, on_token_json_updated=_persist)


