from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis_async
from app.settings import MONGO_URI, DATABASE_NAME, REDIS_URL

client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

redis_client = redis_async.from_url(REDIS_URL, decode_responses=True)

users_collection = db.get_collection("users")
system_settings_collection = db.get_collection("system_settings")
exam_files_collection = db.get_collection("exam_files")
exam_categories_collection = db.get_collection("exam_categories")
bookmarks_collection = db.get_collection("bookmarks")
exam_questions_collection = db.get_collection("exam_questions")
exam_submissions_collection = db.get_collection("exam_submissions")
market_items_collection = db.get_collection("market_items")