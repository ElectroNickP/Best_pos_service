import aiohttp
from loguru import logger
from config import config

async def notify_bot_of_payment(order_data: dict):
    """
    Sends a webhook notification to the main bot about a successful payment.
    """
    if not config.BOT_WEBHOOK_URL:
        logger.warning("⚠️ BOT_WEBHOOK_URL not configured. Skipping notification.")
        return False

    payload = {
        "status": "paid",
        "order": order_data
    }

    headers = {
        "X-API-Key": config.API_KEY.get_secret_value(),
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                config.BOT_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Bot notified of payment for order {order_data.get('id')}")
                    return True
                else:
                    text = await resp.text()
                    logger.error(f"❌ Failed to notify bot: {resp.status} - {text}")
                    return False
    except Exception as e:
        logger.error(f"❌ Error notifying bot: {e}")
        return False
