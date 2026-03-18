"""
Audit history routes.

GET /api/v1/history   Return all past audits for the authenticated user
"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth import decode_token
from app.services.user_store import get_user_audits

router = APIRouter(prefix="/api/v1", tags=["history"])
_bearer = HTTPBearer()


@router.get("/history")
def get_history(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    email = decode_token(credentials.credentials)
    return get_user_audits(email)
