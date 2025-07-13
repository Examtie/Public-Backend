from fastapi import APIRouter, Query, HTTPException, status, Depends
from typing import List, Optional
from bson import ObjectId

from app.database import market_items_collection
from app.models import MarketItemOut, MarketItemCreate
from app.dependencies import require_roles, get_current_user
from app.settings import SELLER_ROLE, ADMIN_ROLE

router = APIRouter(
    prefix="/market/api/v1",
    tags=["Market"]
)

# Helper to convert MongoDB document to Pydantic output model

def to_market_item_out(doc) -> MarketItemOut:
    return MarketItemOut(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description"),
        price=doc["price"],
        image_url=doc.get("image_url"),
    )

# ----------------------- PUBLIC ROUTES -----------------------

@router.get("/items", response_model=List[MarketItemOut])
async def list_market_items(q: int = Query(10, ge=1, le=100, description="Number of items to retrieve"),current_user: dict = Depends(get_current_user)):
    """Get *q* items from the market (default 10, max 100)."""
    items: List[MarketItemOut] = []
    async for doc in market_items_collection.find().limit(q):
        items.append(to_market_item_out(doc))
    return items

@router.get("/items/search", response_model=List[MarketItemOut])
async def search_market_items(
    keyword: str = Query(..., min_length=1, description="Keyword to search for"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    current_user: dict = Depends(get_current_user),
):
    """Search items by **name** or **description**."""
    query = {
        "$or": [
            {"name": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
        ]
    }
    items: List[MarketItemOut] = []
    async for doc in market_items_collection.find(query).limit(limit):
        items.append(to_market_item_out(doc))
    return items

@router.get("/items/{item_id}", response_model=MarketItemOut)
async def get_market_item(item_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve a single market item by its *id*."""
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item ID format")

    doc = await market_items_collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return to_market_item_out(doc)

# ----------------------- ADMIN/SELLER ROUTES -----------------------

@router.post("/items", response_model=MarketItemOut, status_code=status.HTTP_201_CREATED)
async def create_market_item(
    item: MarketItemCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLE, SELLER_ROLE)),
):
    """Create a new market item (admin/seller only)."""
    doc = item.model_dump()
    result = await market_items_collection.insert_one(doc)
    created = await market_items_collection.find_one({"_id": result.inserted_id})
    return to_market_item_out(created)

@router.delete("/items/{item_id}")
async def delete_market_item(
    item_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLE, SELLER_ROLE)),
):
    """Delete a market item (admin/seller only)."""
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item ID format")
    result = await market_items_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return {"message": "Item deleted successfully"}
