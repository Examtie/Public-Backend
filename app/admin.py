from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from bson import ObjectId
from typing import List, Optional
from app.database import users_collection, system_settings_collection, exam_files_collection, exam_categories_collection
from app.dependencies import get_current_user, require_roles
from app.models import UserOut, ExamFileCreate, ExamFileUpdate, ExamFileOut, UpdateProfile, AdminUserOut, UpdateUserRole, ExamCategoryCreate, ExamCategoryUpdate, ExamCategoryOut
from app.storage.r2_client import upload_to_r2, R2_CONFIGURED
from datetime import datetime
from app.settings import ADMIN_ROLE, ALL_ROLES
import json

router = APIRouter(
    prefix="/admin/api/v1",
    tags=["Admin"]
)

# Helper
def to_str_id(doc):
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# === USER MANAGEMENT ===

@router.get("/users", response_model=List[AdminUserOut])
async def list_all_users(
    admin: dict = Depends(require_roles(ADMIN_ROLE)),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by email, username, or full name"),
    role: Optional[str] = Query(None, description="Filter by role")
):
    # Build query
    query = {}
    if search:
        query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"username": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}}
        ]
    if role and role in ALL_ROLES:
        query["roles"] = role
    
    # Calculate skip
    skip = (page - 1) * limit
    
    users = []
    async for user in users_collection.find(query).skip(skip).limit(limit):
        users.append(AdminUserOut(
            id=str(user["_id"]),
            email=user["email"],
            full_name=user.get("full_name", ""),
            username=user.get("username", ""),
            roles=user.get("roles", []),
            bio=user.get("bio", ""),
            profile_image=user.get("profile_image", ""),
            created_at=user.get("created_at")
        ))
    return users

@router.get("/users/@data", response_model=AdminUserOut)
async def get_user_detail(
    admin: dict = Depends(require_roles(ADMIN_ROLE)),
    user_id: Optional[str] = Query(None, description="User ID"),
    username: Optional[str] = Query(None, description="Username")
):
    if not user_id and not username:
        raise HTTPException(status_code=400, detail="Either user_id or username must be provided")
    
    query = {}
    if user_id:
        try:
            query["_id"] = ObjectId(user_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
    elif username:
        query["email"] = username  # Using email as username in login
    
    user = await users_collection.find_one(query)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return AdminUserOut(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user.get("full_name", ""),
        username=user.get("username", ""),
        roles=user.get("roles", []),
        bio=user.get("bio", ""),        profile_image=user.get("profile_image", ""),
        created_at=user.get("created_at")
    )

@router.patch("/users/bulk/role")
async def bulk_update_user_roles(
    bulk_data: dict,
    admin: dict = Depends(require_roles(ADMIN_ROLE))
):
    user_ids = bulk_data.get("user_ids", [])
    role = bulk_data.get("role")
    
    if not user_ids:
        raise HTTPException(status_code=400, detail="user_ids is required")
    if not role or role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {ALL_ROLES}")
    if len(user_ids) > 50:
        raise HTTPException(status_code=400, detail="Cannot update more than 50 users at once")
    
    try:
        object_ids = [ObjectId(uid) for uid in user_ids]
        result = await users_collection.update_many(
            {"_id": {"$in": object_ids}},
            {"$set": {"roles": [role]}}
        )
        return {
            "message": f"Successfully updated {result.modified_count} users",
            "updated_count": result.modified_count
        }
    except Exception as e:
        print(f"Bulk update error: {str(e)}")
        print(f"User IDs: {user_ids}")
        print(f"Role: {role}")
        raise HTTPException(status_code=500, detail=f"Failed to update user roles: {str(e)}")

@router.delete("/users/bulk")
async def bulk_delete_users(
    bulk_data: dict,
    admin: dict = Depends(require_roles(ADMIN_ROLE))
):
    user_ids = bulk_data.get("user_ids", [])
    
    if not user_ids:
        raise HTTPException(status_code=400, detail="user_ids is required")
    if len(user_ids) > 50:
        raise HTTPException(status_code=400, detail="Cannot delete more than 50 users at once")
    
    try:
        object_ids = [ObjectId(uid) for uid in user_ids]
        result = await users_collection.delete_many({"_id": {"$in": object_ids}})
        return {
            "message": f"Successfully deleted {result.deleted_count} users",
            "deleted_count": result.deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete users")

@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str, 
    role_update: UpdateUserRole, 
    admin: dict = Depends(require_roles(ADMIN_ROLE))
):
    try:
        result = await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"roles": [role_update.role]}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "User role updated successfully"}
    except Exception as e:
        if "invalid" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        raise HTTPException(status_code=500, detail="Failed to update user role")

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_roles(ADMIN_ROLE))):
    try:
        result = await users_collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "User deleted successfully"}
    except Exception as e:
        if "invalid" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        raise HTTPException(status_code=500, detail="Failed to delete user")

@router.patch("/users/{user_id}")
async def edit_any_user_profile(user_id: str, update: UpdateProfile, admin: dict = Depends(require_roles(ADMIN_ROLE))):
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    try:
        result = await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        updated_user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found after update")
        return AdminUserOut(
            id=str(updated_user["_id"]),
            email=updated_user["email"],
            username=updated_user["username"],
            full_name=updated_user.get("full_name", ""),
            roles=updated_user.get("roles", []),
            bio=updated_user.get("bio", ""),
            profile_image=updated_user.get("profile_image", ""),
            created_at=updated_user.get("created_at")
        )
    except Exception as e:
        if "invalid" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        raise HTTPException(status_code=500, detail="Failed to update user profile")

# === EXAM CATEGORY MANAGEMENT ===

@router.post("/exam-categories", response_model=ExamCategoryOut)
async def create_exam_category(
    category: ExamCategoryCreate,
    admin: dict = Depends(require_roles(ADMIN_ROLE))
):
    # Check for duplicate category name (case-insensitive)
    existing = await exam_categories_collection.find_one({"name": {"$regex": f"^{category.name}$", "$options": "i"}})
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists.")
    doc = category.dict()
    result = await exam_categories_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return ExamCategoryOut(**doc)

@router.put("/exam-categories/{category_id}", response_model=ExamCategoryOut)
async def update_exam_category(
    category_id: str,
    update: ExamCategoryUpdate,
    admin: dict = Depends(require_roles(ADMIN_ROLE))
):
    update_dict = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="No data provided")
    result = await exam_categories_collection.update_one(
        {"_id": ObjectId(category_id)},
        {"$set": update_dict}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    updated = await exam_categories_collection.find_one({"_id": ObjectId(category_id)})
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found after update")
    return ExamCategoryOut(
        id=str(updated["_id"]),
        name=updated["name"],
        description=updated.get("description", ""),
        english_name=updated.get("english_name", "")
    )

@router.delete("/exam-categories/{category_id}")
async def delete_exam_category(
    category_id: str,
    admin: dict = Depends(require_roles(ADMIN_ROLE))
):
    result = await exam_categories_collection.delete_one({"_id": ObjectId(category_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted successfully"}

# === EXAM MANAGEMENT ===

@router.get("/test-r2")
async def test_r2_configuration(
    admin=Depends(require_roles(ADMIN_ROLE))
):
    """Test endpoint to check R2 configuration"""
    from app.storage.r2_client import R2_CONFIGURED, r2, BUCKET
    from app.storage.s3_client import S3_CONFIGURED
    import os
    
    config_status = {
        "r2_configured": R2_CONFIGURED,
        "r2_client_initialized": r2 is not None,
        "bucket_name": BUCKET,
        "has_endpoint_url": bool(os.getenv("R2_ENDPOINT_URL")),
        "has_access_key": bool(os.getenv("R2_ACCESS_KEY")),
        "has_secret_key": bool(os.getenv("R2_SECRET_KEY")),
        "has_bucket_name": bool(os.getenv("R2_BUCKET_NAME")),
    }
    
    # Test bucket access if configured
    if R2_CONFIGURED and r2 and BUCKET:
        try:
            # Try to list objects (this will test connectivity and permissions)
            response = r2.list_objects_v2(Bucket=BUCKET, MaxKeys=1)
            config_status["bucket_accessible"] = True
            config_status["bucket_test_error"] = None
        except Exception as e:
            config_status["bucket_accessible"] = False
            config_status["bucket_test_error"] = str(e)
    else:
        config_status["bucket_accessible"] = False
        config_status["bucket_test_error"] = "R2 not properly configured"
    
    return config_status

@router.post("/upload", response_model=ExamFileOut)
async def upload_exam_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    tags: str = Form(...),  # This will be the list of category IDs
    essay_count: int = Form(...),
    choice_count: int = Form(...),
    answer_key: str = Form(None),  # JSON string mapping question -> answer
    admin=Depends(require_roles(ADMIN_ROLE)),
    current_user=Depends(get_current_user)
):
    # Parse tags (accept comma-separated or JSON array)
    try:
        if tags.strip().startswith("["):
            tags_list = json.loads(tags)
        else:
            tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    except Exception:
        tags_list = []

    # Validate at least one question type
    if (int(essay_count) < 1 and int(choice_count) < 1):
        raise HTTPException(status_code=400, detail="ต้องมีอย่างน้อย 1 ใน 2 (essay_count หรือ choice_count) ที่เป็น 1 ขึ้นไป")

    # Decide which storage backend to use
    from app.storage.s3_client import upload_to_s3, S3_CONFIGURED
    if S3_CONFIGURED:
        file_url = await upload_to_s3(file)
    elif R2_CONFIGURED:
        file_url = await upload_to_r2(file)
    else:
        raise HTTPException(status_code=500, detail="No storage backend configured")
    # Parse answer_key JSON if provided
    answer_key_data = None
    if answer_key:
        try:
            answer_key_data = json.loads(answer_key)
        except Exception:
            raise HTTPException(status_code=400, detail="answer_key must be valid JSON")

    record = {
        "title": title,
        "description": description,
        "tags": tags_list,  # Store category IDs here
        "essay_count": int(essay_count),
        "choice_count": int(choice_count),
        "url": file_url,
        "uploaded_by": current_user["email"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "answer_key": answer_key_data
    }
    result = await exam_files_collection.insert_one(record)
    record["id"] = str(result.inserted_id)
    record["url"] = file_url
    return ExamFileOut(**{**record, "id": str(result.inserted_id)})

@router.put("/exam-files/{file_id}", response_model=ExamFileOut)
async def update_exam_file(
    file_id: str,
    update_data: ExamFileUpdate,
    admin=Depends(require_roles(ADMIN_ROLE))
):
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="No data provided")
    update_dict["updated_at"] = datetime.utcnow()
    try:
        result = await exam_files_collection.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": update_dict}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="File not found")
        updated = await exam_files_collection.find_one({"_id": ObjectId(file_id)})
        if not updated:
            raise HTTPException(status_code=404, detail="File not found after update")
        return ExamFileOut(
            id=str(updated["_id"]),
            title=updated["title"],
            description=updated["description"],
            tags=updated["tags"],
            url=updated["url"],
            uploaded_by=updated["uploaded_by"],
            essay_count=updated.get("essay_count", 0),
            choice_count=updated.get("choice_count", 0)
        )
    except ValueError as ve:
        # Validation errors from the model
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        if "invalid" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid file ID format")
        # Log the actual error for debugging
        print(f"Update error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update exam file: {str(e)}")

@router.get("/exam-files", response_model=List[ExamFileOut])
async def list_exam_files(
    admin: dict = Depends(require_roles(ADMIN_ROLE)),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    skip = (page - 1) * limit
    files = []
    async for file_doc in exam_files_collection.find().skip(skip).limit(limit):
        files.append(ExamFileOut(
            id=str(file_doc["_id"]),
            title=file_doc["title"],
            description=file_doc["description"],
            tags=file_doc.get("tags", []),
            url=file_doc["url"],
            uploaded_by=file_doc["uploaded_by"],
            essay_count=file_doc.get("essay_count", 0),
            choice_count=file_doc.get("choice_count", 0)
        ))
    return files

@router.delete("/exam-files/{file_id}")
async def delete_exam_file(
    file_id: str,
    admin: dict = Depends(require_roles(ADMIN_ROLE))
):
    try:
        result = await exam_files_collection.delete_one({"_id": ObjectId(file_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="File not found")
        return {"message": "Exam file deleted successfully"}
    except Exception as e:
        if "invalid" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid file ID format")
        raise HTTPException(status_code=500, detail="Failed to delete exam file")

@router.get("/exam-files/by-category/{category_id}", response_model=List[ExamFileOut])
async def get_exam_files_by_category(
    category_id: str,
    admin: dict = Depends(require_roles(ADMIN_ROLE)),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    skip = (page - 1) * limit
    files = []
    # Find files where category_id is in tags
    async for file_doc in exam_files_collection.find({"tags": category_id}).skip(skip).limit(limit):
        files.append(ExamFileOut(
            id=str(file_doc["_id"]),
            title=file_doc["title"],
            description=file_doc["description"],
            tags=file_doc.get("tags", []),
            url=file_doc["url"],
            uploaded_by=file_doc["uploaded_by"],
            essay_count=file_doc.get("essay_count", 0),
            choice_count=file_doc.get("choice_count", 0)
        ))
    return files

@router.get("/exam-files/all", response_model=List[ExamFileOut])
async def get_all_exam_files(admin: dict = Depends(require_roles(ADMIN_ROLE))):
    files = []
    async for file_doc in exam_files_collection.find():
        files.append(ExamFileOut(
            id=str(file_doc["_id"]),
            title=file_doc["title"],
            description=file_doc["description"],
            tags=file_doc.get("tags", []),
            url=file_doc["url"],
            uploaded_by=file_doc["uploaded_by"],
            essay_count=file_doc.get("essay_count", 0),
            choice_count=file_doc.get("choice_count", 0)
        ))
    return files

# === SYSTEM STATS ===

@router.get("/stats")
async def get_system_stats(admin: dict = Depends(require_roles(ADMIN_ROLE))):
    user_count = await users_collection.count_documents({})
    exam_count = await exam_files_collection.count_documents({})
    
    # Get user counts by role
    user_roles_stats = {}
    for role in ALL_ROLES:
        count = await users_collection.count_documents({"roles": role})
        user_roles_stats[role] = count
    
    return {
        "users": {
            "total": user_count,
            "by_role": user_roles_stats
        },
        "exams": exam_count,
        "timestamp": datetime.utcnow()
    }
