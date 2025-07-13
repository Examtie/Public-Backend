from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.database import redis_client
from bson import json_util
from datetime import datetime


from app.models import UserIn, UserOut, Token
from app.database import users_collection
from app.auth import hash_password, verify_password, create_access_token
from app.dependencies import get_user_by_email, get_user_by_username
from app.settings import CACHE_EXPIRE_SECONDS

router = APIRouter(
    prefix="/auth/api/v1",
    tags=["Authentication"]
)

@router.post("/register", response_model=UserOut)
async def register(user_in: UserIn):
    if await get_user_by_email(user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    if user_in.username and await get_user_by_username(user_in.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    user_data = user_in.dict()
    user_data.update({
        "hashed_password": hash_password(user_data.pop("password")),
        "created_at": datetime.utcnow(),
        "bio": "New to Examtie!",
        "profile_image": "https://jwt.io/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fjwt-flower.f20616b0.png&w=3840&q=75"
    })

    result = await users_collection.insert_one(user_data)
    # Cache the newly created user in Redis for quicker future logins
    user_data["_id"] = result.inserted_id

    await redis_client.set(f"user:{user_data['email']}", json_util.dumps(user_data), ex=CACHE_EXPIRE_SECONDS)
    if user_data.get("username"):
        await redis_client.set(f"user_by_username:{user_data['username']}", json_util.dumps(user_data), ex=CACHE_EXPIRE_SECONDS)

    access_token = create_access_token(
        data={"sub": user_data["email"], "roles": user_data["roles"]}
    )
    return UserOut(
        id=str(result.inserted_id),
        email=user_data["email"],
        username=user_data["username"],
        full_name=user_data["full_name"],
        roles=user_data["roles"],
        bio=user_data["bio"],
        profile_image=user_data["profile_image"],
        token=access_token
    )

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["email"], "roles": user.get("roles", [])}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/token", response_model=Token)
async def login_for_access_token_standard(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["email"], "roles": user.get("roles", [])}
    )
    return {"access_token": access_token, "token_type": "bearer"}