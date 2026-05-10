"""
POS Service — NSPK Payment Gateway (Async).
Handles THB → RUB conversion and payment link generation via asia-nspk.cc.
Rewritten from the bot project's synchronous version to use aiohttp.
"""
import aiohttp
import urllib.parse
from loguru import logger
from config import config


class NSPKService:
    def __init__(
        self,
        slug: str | None = None,
        point_id: int | None = None,
    ):
        self.slug = slug or config.NSPK_SLUG
        self.point_id = point_id or config.NSPK_POINT_ID
        self.base_url = "https://asia-nspk.cc"

    async def _create_session(self) -> aiohttp.ClientSession:
        """Create a fresh aiohttp session with browser-like headers."""
        return aiohttp.ClientSession(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
        )

    async def _refresh_session(self, session: aiohttp.ClientSession) -> str | None:
        """Hit the landing page to get XSRF token from cookies."""
        try:
            landing_url = f"{self.base_url}/point/{self.slug}/pay"
            async with session.get(landing_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                # Extract XSRF token from cookies
                xsrf_token = None
                for cookie in session.cookie_jar:
                    if cookie.key == "XSRF-TOKEN":
                        xsrf_token = urllib.parse.unquote(cookie.value)
                        break
                if xsrf_token:
                    session.headers.update({"X-XSRF-TOKEN": xsrf_token})
                return xsrf_token
        except Exception as e:
            logger.error(f"NSPK session refresh failed: {e}")
            return None

    async def get_rate(self, session: aiohttp.ClientSession) -> dict | None:
        """Fetch current THB/RUB rate and rate_token."""
        try:
            rate_url = f"{self.base_url}/api/public/points/{self.slug}/rate"
            async with session.get(rate_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error(f"NSPK rate fetch failed: {resp.status}")
                    return None
                data = await resp.json()
                return data.get("rate")
        except Exception as e:
            logger.error(f"NSPK rate error: {e}")
            return None

    async def create_order(self, amount_thb: float) -> dict | None:
        """
        Generate a payment reference for the given THB amount.
        Returns dict with: reference, link, amount_rub, amount_thb, rate
        """
        async with await self._create_session() as session:
            xsrf = await self._refresh_session(session)
            if not xsrf:
                return None

            rate_info = await self.get_rate(session)
            if not rate_info:
                return None

            rate_value = rate_info.get("rate")
            rate_token = rate_info.get("rate_token")

            amount_rub = round(amount_thb * float(rate_value))

            order_url = f"{self.base_url}/api/recurring/new-order"
            payload = {
                "point_id": self.point_id,
                "payment_currency": "RUB",
                "settlement_currency": "THB",
                "settlement_amount": amount_thb,
                "rate_token": rate_token,
                "type": "online",
            }

            try:
                async with session.post(
                    order_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"NSPK order creation failed: {resp.status} - {text}")
                        return None

                    res = await resp.json()
                    payment_ref = res.get("payment_reference")
                    if payment_ref:
                        return {
                            "reference": payment_ref,
                            "link": f"{self.base_url}/pay/{payment_ref}",
                            "amount_rub": amount_rub,
                            "amount_thb": amount_thb,
                            "rate": rate_value,
                        }
                    return None
            except Exception as e:
                logger.error(f"NSPK order error: {e}")
                return None


# Singleton
nspk_service = NSPKService()
