from fastapi import APIRouter, Request, HTTPException, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database import get_db
from models.schemas import TouristOrder
from services.bot_client import notify_bot_of_payment

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

@router.post("/nspk/callback")
async def nspk_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Callback endpoint for NSPK payment gateway.
    Expected payload (simplified): {"payment_reference": "...", "status": "success"}
    """
    try:
        data = await request.json()
        logger.info(f"📩 Received NSPK callback: {data}")
        
        ref = data.get("payment_reference")
        status = data.get("status")
        
        if not ref or status != "success":
            return {"status": "ignored", "reason": "invalid_data_or_status"}

        # Find order by reference
        stmt = select(TouristOrder).where(TouristOrder.payment_reference == ref)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()
        
        if not order:
            logger.warning(f"⚠️ Order not found for reference: {ref}")
            return {"status": "error", "message": "order_not_found"}

        if order.status == "paid":
            return {"status": "ok", "message": "already_paid"}

        # Update order status
        order.status = "paid"
        await db.commit()
        logger.info(f"💰 Order {order.id} marked as PAID.")

        # Notify the Bot
        order_dict = {
            "id": order.id,
            "total_thb": float(order.total_amount),
            "total_rub": order.total_rub or 0,
            "pier": order.pier,
            "telegram_id": order.telegram_id,
            "items": [
                {"name": i.product_name, "quantity": i.quantity}
                for i in order.items
            ]
        }
        await notify_bot_of_payment(order_dict)

        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
