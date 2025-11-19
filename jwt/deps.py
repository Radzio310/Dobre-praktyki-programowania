from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .tokens import decode_token, TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/jwt/login_form")

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        return decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

def require_roles(*required: str):
    def _dep(user: TokenData = Depends(get_current_user)) -> TokenData:
        if not required:
            return user
        have = set(r.lower() for r in user.roles)
        need = set(r.lower() for r in required)
        if not need.issubset(have):
            raise HTTPException(status_code=403, detail="Forbidden: missing role")
        return user
    return _dep
