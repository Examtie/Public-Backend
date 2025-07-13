from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.settings import SECRET_KEY, ALGORITHM, CACHE_EXPIRE_SECONDS
from app.database import redis_client
from bson import json_util
from app.models import TokenData
from app.database import users_collection

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/token",
    scheme_name="Bearer Token",
    description="Enter your JWT token here"
)

async def _cache_user(user: dict):
    """Helper – store user doc in Redis under both email and username keys."""
    if not user:
        return
    # BSON -> JSON string that preserves ObjectId
    encoded = json_util.dumps(user)
    await redis_client.set(f"user:{user['email']}", encoded, ex=CACHE_EXPIRE_SECONDS)
    username = user.get("username")
    if username:
        await redis_client.set(f"user_by_username:{username}", encoded, ex=CACHE_EXPIRE_SECONDS)

async def get_user_by_email(email: str):
    key = f"user:{email}"
    cached = await redis_client.get(key)
    if cached:
        return json_util.loads(cached)
    user = await users_collection.find_one({"email": email})
    if user:
        await _cache_user(user)
    return user

async def get_user_by_username(username: str):
    key = f"user_by_username:{username}"
    cached = await redis_client.get(key)
    if cached:
        return json_util.loads(cached)
    user = await users_collection.find_one({"username": username})
    if user:
        await _cache_user(user)
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        roles = payload.get("roles", [])
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email, roles=roles)
    except JWTError:
        raise credentials_exception

    if token_data.email is None:
        raise credentials_exception
    user = await get_user_by_email(token_data.email)
    if not user:
        raise credentials_exception
    return user

def require_roles(*roles: str):
    async def checker(current_user: dict = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return current_user
    return checker
