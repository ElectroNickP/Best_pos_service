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
from services.payment_service import nspk_service
from services.time_utils import get_phuket_today
from services.bot_client import send_telegram_log

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
        total_amount = sum(item.price * item.quantity for item in req.items)
        
        pay_url = None
        pay_ref = None
        total_rub = None
        rate = None

        if req.payment_type == "online":
            if total_amount <= 0:
                raise HTTPException(status_code=400, detail="Сумма заказа 0฿. Пожалуйста, используйте оплату наличными (Cash).")
            try:
                pay_info = await nspk_service.create_order(total_amount)
                if pay_info:
                    pay_url = pay_info["link"]
                    pay_ref = pay_info["reference"]
                    total_rub = pay_info["amount_rub"]
                    rate = pay_info["rate"]
                else:
                    logger.error("NSPK gateway returned no data")
                    # We can either fail here or proceed without link. 
                    # Usually it's better to fail if online payment is requested.
                    raise HTTPException(status_code=502, detail="Payment gateway error")
            except Exception as e:
                logger.error(f"NSPK payment error: {e}")
                raise HTTPException(status_code=502, detail="Payment gateway error")

        sale = await cash_service.record_sale(
            session_id=req.session_id,
            pier=req.pier,
            manager_id=manager_id,
            items_data=items_data,
            payment_type=req.payment_type,
            payment_reference=pay_ref,
            payment_link=pay_url,
            status="pending" if req.payment_type == "online" else "completed",
        )
        # Send Telegram Log immediately ONLY for cash
        if req.payment_type == "cash":
            try:
                items_text = "\n".join([f"• {item.name} x{item.quantity} ({item.price} ฿)" for item in req.items])
                pay_method = "💳 Online (NSPK)" if req.payment_type == "online" else "💵 Cash"
                
                msg = f"<b>🧾 New POS Sale</b>\n"
                msg += f"📍 Pier: {req.pier}\n"
                msg += f"💰 Amount: {total_amount} ฿\n"
                msg += f"💳 Payment: {pay_method}\n\n"
                msg += "<b>Items:</b>\n"
                msg += items_text
                
                await send_telegram_log(msg)
            except Exception as e:
                logger.error(f"Error formatting/sending telegram log: {e}")

        return {
            "status": "success",
            "data": {
                "sale_id": sale.id,
                "total_amount": sale.total_amount,
                "payment_type": sale.payment_type,
                "pay_url": pay_url,
                "total_rub": total_rub,
                "rate": rate,
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


@router.post("/{sale_id}/complete")
async def complete_sale(
    sale_id: int,
    user: dict = Depends(get_current_user),
):
    """
    Manually marks a pending online sale as completed.
    Also sends the Telegram log.
    """
    sale = await cash_service.complete_sale(sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Pending sale not found")
        
    # Send Telegram Log for POS Sale
    try:
        items_text = "\n".join([f"• {i.product_name} x{i.quantity} ({i.price_per_unit} ฿)" for i in sale.items])
        msg = f"<b>🧾 New POS Sale (Manual Confirmation)</b>\n"
        msg += f"📍 Pier: {sale.pier}\n"
        msg += f"💰 Amount: {sale.total_amount} ฿\n"
        msg += f"💳 Payment: 💳 Online (NSPK)\n\n"
        msg += "<b>Items:</b>\n"
        msg += items_text
        
        await send_telegram_log(msg)
    except Exception as e:
        logger.error(f"Error sending telegram log for manual POS sale completion: {e}")

    return {"status": "success", "message": f"Sale #{sale_id} marked as completed"}
