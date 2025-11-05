from typing import Optional, Dict, Any

import requests
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from jose.exceptions import JWTError

from .config import AWS_REGION, USER_POOL_ID, CLIENT_ID


security = HTTPBearer()

_jwks_cache: Optional[Dict] = None


def get_jwks() -> Dict[str, Any]:
    """Get JWKS from AWS Cognito with caching."""
    global _jwks_cache
    if _jwks_cache is None:
        jwks_url = (
            f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        )
        try:
            response = requests.get(jwks_url)
            response.raise_for_status()
            _jwks_cache = response.json()
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch JWKS: {str(e)}")
    return _jwks_cache


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify JWT token from Cognito."""
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Invalid token: missing kid")

        jwks = get_jwks()
        key = None
        for k in jwks["keys"]:
            if k["kid"] == kid:
                key = k
                break

        if not key:
            raise HTTPException(status_code=401, detail="Invalid token: key not found")

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}",
        )
        return payload

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency to get current user from JWT token."""
    if credentials.scheme != "Bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    return verify_jwt_token(credentials.credentials)


