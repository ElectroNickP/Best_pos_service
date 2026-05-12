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

async def send_telegram_log(message: str, chat_id: str | None = None, topic_id: int | None = None):
    """
    Sends a formatted HTML message directly to the management Telegram group topic.
    Uses dynamic settings from DB with config fallbacks.
    """
    from services.settings_service import settings_service

    if not config.bot_token_list:
        logger.warning("⚠️ No bot tokens configured for Telegram logs.")
        return False
    
    # Resolve chat_id and topic_id (passed params > DB settings > hardcoded defaults)
    final_chat_id = chat_id or await settings_service.get("TELEGRAM_LOG_CHAT_ID", "-1003556020066")
    db_topic_id = await settings_service.get("TELEGRAM_LOG_TOPIC_ID", "569")
    final_topic_id = topic_id or int(db_topic_id)

    token = config.bot_token_list[0]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": final_chat_id,
        "message_thread_id": final_topic_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    logger.info("✅ Telegram log sent successfully.")
                    return True
                else:
                    err = await resp.text()
                    logger.error(f"❌ Failed to send Telegram log: {resp.status} - {err}")
                    return False
    except Exception as e:
        logger.error(f"❌ Error sending Telegram log: {e}")
        return False
