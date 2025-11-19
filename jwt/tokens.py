from datetime import datetime, timezone
from jose import jwt, JWTError
from pydantic import BaseModel
from typing import List
from .settings import SECRET_KEY, ALGORITHM, access_token_timedelta

class TokenData(BaseModel):
    sub: str
    roles: List[str] = []

def create_access_token(sub: str, roles: List[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + access_token_timedelta()).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> TokenData:
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(sub=data["sub"], roles=data.get("roles", []))
    except JWTError as e:
        raise ValueError("invalid-token") from e
