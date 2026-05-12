from fastapi import APIRouter, Request, HTTPException, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database import get_db
from models.schemas import TouristOrder, Sale
from services.bot_client import notify_bot_of_payment, send_telegram_log

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
            # Fallback to check if it's a POS Sale
            stmt_sale = select(Sale).where(Sale.payment_reference == ref)
            result_sale = await db.execute(stmt_sale)
            sale = result_sale.scalar_one_or_none()
            
            if not sale:
                logger.warning(f"⚠️ Order/Sale not found for reference: {ref}")
                return {"status": "error", "message": "not_found"}
                
            if sale.status == "completed":
                return {"status": "ok", "message": "already_paid"}
                
            sale.status = "completed"
            await db.commit()
            logger.info(f"💰 POS Sale {sale.id} marked as PAID via webhook.")
            
            # Send Telegram Log for POS Sale
            try:
                items_text = "\n".join([f"• {i.product_name} x{i.quantity} ({i.price_per_unit} ฿)" for i in sale.items])
                msg = f"<b>🧾 New POS Sale</b>\n"
                msg += f"📍 Pier: {sale.pier}\n"
                msg += f"💰 Amount: {sale.total_amount} ฿\n"
                msg += f"💳 Payment: 💳 Online (NSPK)\n\n"
                msg += "<b>Items:</b>\n"
                msg += items_text
                
                await send_telegram_log(msg)
            except Exception as e:
                logger.error(f"Error sending telegram log for POS sale: {e}")
                
            return {"status": "ok"}

        if order.status == "paid":
            return {"status": "ok", "message": "already_paid"}

        # Update order status
        order.status = "paid"
        await db.commit()
        logger.info(f"💰 Order {order.id} marked as PAID.")

        # Notify the Bot via Webhook
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

        # Send direct Telegram Log for Tourist Order
        try:
            items_text = "\n".join([f"• {i.product_name} x{i.quantity}" for i in order.items])
            msg = f"<b>✅ Online Payment (Tourist Shop)</b>\n"
            msg += f"🛒 Order #{order.id}\n"
            msg += f"📍 Pier: {order.pier}\n"
            msg += f"💰 Amount: {order.total_amount} ฿"
            if order.total_rub:
                msg += f" ({order.total_rub} ₽)"
            msg += "\n\n<b>Items:</b>\n"
            msg += items_text
            
            await send_telegram_log(msg)
        except Exception as e:
            logger.error(f"Error sending telegram log for tourist order: {e}")

        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
