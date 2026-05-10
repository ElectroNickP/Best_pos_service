"""
POS Service — Sales API.
Endpoints for recording sales, getting reports, and cancelling transactions.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from api.auth import get_current_user
from services.cash_service import cash_service
from services.time_utils import get_phuket_today

router = APIRouter(prefix="/api/v1/sales", tags=["Sales"])


class SaleItemInput(BaseModel):
    name: str
    quantity: int
    price: float


class RecordSaleRequest(BaseModel):
    session_id: int | None = None
    pier: str
    manager_id: int | None = None
    items: list[SaleItemInput]
    payment_type: str = "cash"  # "cash" | "online"


@router.post("")
async def record_sale(
    req: RecordSaleRequest,
    user: dict = Depends(get_current_user),
):
    """
    Records a sale with one or more items.
    Requires an active session (session_id) or standalone sale by pier.
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="No items in sale")

    if req.payment_type not in ("cash", "online"):
        raise HTTPException(status_code=400, detail="Invalid payment type. Use 'cash' or 'online'.")

    manager_id = req.manager_id or user.get("user_id", 0)

    try:
        items_data = [
            {"name": item.name, "quantity": item.quantity, "price": item.price}
            for item in req.items
        ]
        sale = await cash_service.record_sale(
            session_id=req.session_id,
            pier=req.pier,
            manager_id=manager_id,
            items_data=items_data,
            payment_type=req.payment_type,
        )
        return {
            "status": "success",
            "data": {
                "sale_id": sale.id,
                "total_amount": sale.total_amount,
                "payment_type": sale.payment_type,
            },
        }
    except Exception as e:
        logger.exception(f"Error recording sale: {e}")
        raise HTTPException(status_code=500, detail=f"Sale recording failed: {str(e)}")


@router.get("/daily-report")
async def daily_report(
    pier: str = Query(..., description="Pier name"),
    report_date: str | None = Query(None, description="Date in YYYY-MM-DD format (default: today)"),
    user: dict = Depends(get_current_user),
):
    """
    Returns aggregated daily sales report for a pier.
    Includes revenue, cost, profit, margin, per-product breakdown, and transaction log.
    """
    if report_date:
        try:
            target_date = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    else:
        target_date = get_phuket_today()

    report = await cash_service.get_daily_report(pier, target_date)
    return {"status": "success", "data": report}


@router.delete("/{sale_id}")
async def cancel_sale(
    sale_id: int,
    user: dict = Depends(get_current_user),
):
    """
    Cancels (soft-deletes) a sale by marking it as 'cancelled'.
    The sale remains in the database for audit purposes but is excluded from reports.
    """
    success = await cash_service.cancel_sale(sale_id)
    if success:
        return {"status": "success", "message": f"Sale #{sale_id} cancelled"}
    raise HTTPException(status_code=404, detail="Sale not found or already cancelled")
