from __future__ import annotations

from pydantic import BaseModel, EmailStr


class RequestCodeBody(BaseModel):
    email: EmailStr


class VerifyCodeBody(BaseModel):
    email: EmailStr
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    email: str


