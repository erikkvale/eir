from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.auth.jwt_handler import verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Verify and return the current user from the token.
    """
    try:
        payload = verify_token(token)
        return payload
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
