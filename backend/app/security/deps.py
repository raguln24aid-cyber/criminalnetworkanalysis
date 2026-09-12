from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import User
from app.security.auth import decode_access_token

# tokenUrl is documentation-only for the OpenAPI schema (Swagger's "Authorize"
# button) - the actual login route is /api/auth/login, this doesn't redirect
# or proxy anything.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """The one real gate every protected endpoint depends on. Previously no
    endpoint checked the JWT at all - a token was issued at login but nothing
    ever verified it again, so every API route was reachable by anyone with
    network access to the backend regardless of the frontend's login screen."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error

    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise credentials_error

    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user or not user.is_active:
        raise credentials_error

    return user


def require_role(*roles: str):
    """Dependency factory for RBAC: Depends(require_role("ADMIN"))."""

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the following roles: {', '.join(roles)}",
            )
        return user

    return _check
