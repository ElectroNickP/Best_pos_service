"""
POS Service — Tourist Checkout API.
Handles online orders from tourists: creates orders and generates NSPK payment links.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

from api.auth import get_current_user
from models import AsyncSessionLocal, TouristOrder, TouristOrderItem
from services.payment_service import nspk_service
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/checkout", tags=["Checkout"])


class CheckoutItem(BaseModel):
    name: str
    quantity: int = 1
    price: float


class CheckoutRequest(BaseModel):
    items: list[CheckoutItem]
    telegram_id: int | None = None
    pier: str = "Online"


@router.post("")
async def create_checkout(req: CheckoutRequest):
    """
    Create an online order and generate an NSPK payment link.
    This endpoint is intentionally public (no auth required) for tourist access,
    but can be called with API key for bot integration.
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total_thb = sum(item.price * item.quantity for item in req.items)
    if total_thb <= 0:
        raise HTTPException(status_code=400, detail="Invalid total amount")

    # Generate payment link via NSPK
    try:
        pay_info = await nspk_service.create_order(total_thb)
    except Exception as e:
        logger.error(f"NSPK payment error: {e}")
        raise HTTPException(status_code=502, detail="Payment gateway error")

    if not pay_info:
        raise HTTPException(status_code=502, detail="Payment gateway returned no data")

    # Save order to database
    async with AsyncSessionLocal() as session:
        order = TouristOrder(
            telegram_id=req.telegram_id,
            pier=req.pier,
            total_amount=total_thb,
            total_rub=pay_info.get("amount_rub"),
            rate=pay_info.get("rate"),
            status="pending",
            payment_reference=pay_info["reference"],
            payment_link=pay_info["link"],
        )
        session.add(order)
        await session.flush()

        for item in req.items:
            oi = TouristOrderItem(
                order_id=order.id,
                product_name=item.name,
                quantity=item.quantity,
                price_per_unit=item.price,
                total_price=item.price * item.quantity,
            )
            session.add(oi)

        await session.commit()
        logger.info(f"Tourist Order #{order.id} created: {total_thb}฿ → {pay_info['amount_rub']}₽")

        return {
            "status": "success",
            "data": {
                "order_id": order.id,
                "pay_url": pay_info["link"],
                "total_thb": total_thb,
                "total_rub": pay_info["amount_rub"],
                "rate": pay_info["rate"],
                "reference": pay_info["reference"],
            },
        }


@router.get("/{order_id}/status")
async def get_order_status(order_id: int):
    """
    Check the status of an existing tourist order.
    Public endpoint (no auth) so payment confirmation pages can poll it.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TouristOrder).where(TouristOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        return {
            "status": "success",
            "data": {
                "order_id": order.id,
                "order_status": order.status,
                "total_amount": order.total_amount,
                "payment_link": order.payment_link,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            },
        }
