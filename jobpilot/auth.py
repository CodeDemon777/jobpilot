"""Authentication module for JobPilot."""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Configuration
SECRET_KEY = os.getenv("JOBTPILOT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


class UserCreate(BaseModel):
    """User registration model."""

    email: str
    password: str
    name: str = ""


class UserLogin(BaseModel):
    """User login model."""

    email: str
    password: str


class UserResponse(BaseModel):
    """User response model (no password)."""

    id: int
    email: str
    name: str
    is_active: bool = True
    created_at: str


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data."""

    user_id: Optional[int] = None
    email: Optional[str] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash (truncates to 72 bytes for bcrypt compatibility)."""
    return pwd_context.verify(plain_password[:72], hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password (truncates to 72 bytes for bcrypt compatibility)."""
    return pwd_context.hash(password[:72])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create an access JWT token."""
    to_encode = data.copy()
    # JWT sub claim must be a string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a refresh JWT token."""
    to_encode = data.copy()
    # JWT sub claim must be a string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        # Convert sub to int if it's a string
        if isinstance(user_id, str):
            user_id = int(user_id)
        return TokenData(user_id=user_id, email=email)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Get current user from token dependency."""
    return decode_token(token)


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    """Get current active user (can add is_active check here)."""
    return current_user


def authenticate_user(email: str, password: str, db_path=None) -> Optional[dict]:
    """Authenticate user with email and password."""
    from jobpilot import database as db
    from jobpilot.config import DB_PATH

    if db_path is None:
        db_path = DB_PATH
    user = db.get_user_by_email(email, db_path)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def register_user(email: str, password: str, name: str = "", db_path=None) -> dict:
    """Register a new user."""
    from jobpilot import database as db
    from jobpilot.config import DB_PATH

    if db_path is None:
        db_path = DB_PATH

    # Check if user exists
    existing = db.get_user_by_email(email, db_path)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password and create user
    hashed_password = get_password_hash(password)
    user_id = db.create_user(
        email=email, password_hash=hashed_password, name=name, db_path=db_path
    )

    return {"id": user_id, "email": email, "name": name}


def refresh_access_token(refresh_token: str) -> str:
    """Create a new access token from a refresh token."""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
        email = payload.get("email")
        return create_access_token(data={"sub": user_id, "email": email})
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
