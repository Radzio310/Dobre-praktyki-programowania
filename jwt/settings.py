from datetime import timedelta
import os

SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_ME_IN_ENV")
ALGORITHM = os.getenv("JWT_ALG", "HS256")  # później łatwo przełączysz na RS256
ACCESS_TOKEN_EXPIRE = int(os.getenv("JWT_EXP_MIN", "60"))  # minuty

def access_token_timedelta() -> timedelta:
    return timedelta(minutes=ACCESS_TOKEN_EXPIRE)
