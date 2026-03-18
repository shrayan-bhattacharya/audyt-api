"""
Auth routes.

POST /api/v1/auth/signup   Create account, return JWT
POST /api/v1/auth/login    Verify credentials, return JWT
GET  /api/v1/auth/me       Return email for the current token
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.services.auth import create_access_token, decode_token, hash_password, verify_password
from app.services.user_store import create_user, get_user_by_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_bearer = HTTPBearer()


class AuthBody(BaseModel):
    email: str
    password: str


@router.post("/signup", status_code=201)
def signup(body: AuthBody):
    if get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered.")
    hashed = hash_password(body.password)
    create_user(body.email, hashed)
    token = create_access_token({"sub": body.email})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(body: AuthBody):
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token({"sub": body.email})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    email = decode_token(credentials.credentials)
    return {"email": email}
