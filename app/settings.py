import os
from dotenv import load_dotenv

# Load environment variables from the Backend directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "myapp")

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = os.getenv("REDIS_DB", "0")
# Redis connection URL. If REDIS_URL is not provided, default to a local instance.
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_EXPIRE_SECONDS = int(os.getenv("CACHE_EXPIRE_SECONDS", 3600))

SECRET_KEY = os.getenv("SECRET_KEY", "niga56")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES_SECONDS", 43200)) # 30 days (30 * 24 * 60 minutes)

STREAK_TTL_SECONDS = int(os.getenv("STREAK_TTL_SECONDS", 60 * 60 * 24 * 60))  # 60 days default

ADMIN_ROLE = "admin"
USER_ROLE = "user"
STAFF_ROLE = "staff"
SELLER_ROLE = "seller"


ALL_ROLES = [ADMIN_ROLE, USER_ROLE, STAFF_ROLE, SELLER_ROLE]