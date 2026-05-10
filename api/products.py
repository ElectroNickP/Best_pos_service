"""
POS Service — Products API.
Endpoints for listing, filtering, and syncing products.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.auth import get_current_user
from services.cash_service import cash_service
from services.sheets_sync import sync_products_from_sheets

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


@router.get("")
async def list_products(
    category: str | None = Query(None, description="Filter by category"),
    user: dict = Depends(get_current_user),
):
    """Returns list of active products, optionally filtered by category."""
    products = await cash_service.get_active_products(category=category)
    return {
        "status": "success",
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "cost_price": p.cost_price,
                "sale_price": p.sale_price,
            }
            for p in products
        ],
    }


@router.get("/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    """Returns list of unique active product categories."""
    categories = await cash_service.get_active_categories()
    return {"status": "success", "data": categories}


@router.post("/sync")
async def sync_products(user: dict = Depends(get_current_user)):
    """
    Synchronize products from Google Sheets into the POS database.
    Deactivates products not found in the sheet, adds new ones.
    """
    try:
        count = await sync_products_from_sheets()
        if count > 0:
            return {"status": "success", "synced": count}
        return {"status": "warning", "message": "No products found in source", "synced": 0}
    except Exception as e:
        logger.exception(f"Product sync error: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/{product_id}")
async def get_product(product_id: int, user: dict = Depends(get_current_user)):
    """Get a single product by ID."""
    product = await cash_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "status": "success",
        "data": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "cost_price": product.cost_price,
            "sale_price": product.sale_price,
            "is_active": product.is_active,
        },
    }
