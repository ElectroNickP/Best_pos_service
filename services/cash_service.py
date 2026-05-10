"""
POS Service — Cash Service.
Core business logic for cash sessions, sales, and reporting.
Migrated from Best_sea_job_orders/services/cash_service.py and made standalone.
"""
import datetime
from sqlalchemy import select, update, text
from sqlalchemy.orm import selectinload
from loguru import logger

from models import AsyncSessionLocal, Product, CashSession, Sale, SaleItem
from services.time_utils import get_phuket_now, get_phuket_today, get_day_bounds


class CashService:

    # ── Products ──────────────────────────────────────────────────────────

    async def get_active_products(self, category: str | None = None) -> list[Product]:
        """Returns list of active products, optionally filtered by category."""
        async with AsyncSessionLocal() as session:
            query = select(Product).where(Product.is_active == True)
            if category:
                query = query.where(Product.category == category)
            query = query.order_by(Product.category, Product.name)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_active_categories(self) -> list[str]:
        """Returns unique categories of active products."""
        async with AsyncSessionLocal() as session:
            query = select(Product.category).where(Product.is_active == True).distinct()
            result = await session.execute(query)
            return [r[0] for r in result.all() if r[0]]

    async def get_product_by_id(self, product_id: int) -> Product | None:
        """Fetch a single product by ID."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).where(Product.id == product_id))
            return result.scalars().first()

    async def upsert_products(self, products_data: list[dict]) -> int:
        """
        Bulk upsert products from an external source (Google Sheets).
        Returns the number of products synced.
        """
        if not products_data:
            return 0

        async with AsyncSessionLocal() as session:
            # Mark all as inactive first
            await session.execute(update(Product).values(is_active=False))

            for p_info in products_data:
                query = select(Product).where(Product.name == p_info["name"])
                result = await session.execute(query)
                product = result.scalars().first()

                if product:
                    product.cost_price = p_info.get("cost_price", 0)
                    product.sale_price = p_info["sale_price"]
                    product.category = p_info.get("category", "Other")
                    product.is_active = True
                else:
                    new_product = Product(
                        name=p_info["name"],
                        cost_price=p_info.get("cost_price", 0),
                        sale_price=p_info["sale_price"],
                        category=p_info.get("category", "Other"),
                        is_active=True,
                    )
                    session.add(new_product)

            await session.commit()
            logger.info(f"Synced {len(products_data)} products.")
            return len(products_data)

    # ── Sessions ──────────────────────────────────────────────────────────

    async def get_active_session(self, pier: str) -> CashSession | None:
        """Returns active (open) session for a pier, if any."""
        async with AsyncSessionLocal() as session:
            query = (
                select(CashSession)
                .where(CashSession.pier == pier, CashSession.status == "open")
                .order_by(CashSession.id.desc())
            )
            result = await session.execute(query)
            return result.scalars().first()

    async def get_last_session(self, pier: str) -> CashSession | None:
        """Returns the most recent session (open or closed) for a pier."""
        async with AsyncSessionLocal() as session:
            query = (
                select(CashSession)
                .where(CashSession.pier == pier)
                .order_by(CashSession.id.desc())
                .limit(1)
            )
            result = await session.execute(query)
            return result.scalars().first()

    async def open_session(
        self, pier: str, manager_id: int, manager_name: str | None = None
    ) -> CashSession:
        """Opens a new cash session. Returns existing if already open."""
        existing = await self.get_active_session(pier)
        if existing:
            return existing

        async with AsyncSessionLocal() as session:
            new_session = CashSession(
                pier=pier,
                manager_id=manager_id,
                manager_name=manager_name,
                status="open",
            )
            session.add(new_session)
            await session.commit()
            await session.refresh(new_session)
            logger.info(f"Session #{new_session.id} opened for pier {pier} by manager {manager_id}")
            return new_session

    async def close_session(self, session_id: int) -> bool:
        """Closes an active session by ID."""
        async with AsyncSessionLocal() as session:
            query = select(CashSession).where(CashSession.id == session_id)
            result = await session.execute(query)
            cash_session = result.scalars().first()

            if cash_session and cash_session.status == "open":
                cash_session.status = "closed"
                cash_session.closed_at = get_phuket_now()
                await session.commit()
                logger.info(f"Session #{session_id} closed.")
                return True
            return False

    # ── Sales ─────────────────────────────────────────────────────────────

    async def record_sale(
        self,
        session_id: int | None,
        pier: str,
        manager_id: int,
        items_data: list[dict],
        payment_type: str = "cash",
    ) -> Sale:
        """
        Records a sale with multiple items.
        items_data format: [{'name': str, 'quantity': int, 'price': float}]
        """
        async with AsyncSessionLocal() as session:
            total_amount = sum(item["quantity"] * item["price"] for item in items_data)

            new_sale = Sale(
                session_id=session_id,
                pier=pier,
                manager_id=manager_id,
                total_amount=total_amount,
                payment_type=payment_type,
                status="completed",
            )
            session.add(new_sale)
            await session.flush()

            for item in items_data:
                sale_item = SaleItem(
                    sale_id=new_sale.id,
                    product_name=item["name"],
                    quantity=item["quantity"],
                    price_per_unit=item["price"],
                    total_price=item["quantity"] * item["price"],
                )
                session.add(sale_item)

            await session.commit()
            await session.refresh(new_sale)
            logger.info(f"Sale #{new_sale.id} recorded: {total_amount}฿ ({payment_type})")
            return new_sale

    async def cancel_sale(self, sale_id: int) -> bool:
        """Marks a sale as cancelled (soft delete)."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Sale).where(Sale.id == sale_id))
            sale = result.scalars().first()
            if sale and sale.status == "completed":
                sale.status = "cancelled"
                await session.commit()
                logger.info(f"Sale #{sale_id} cancelled.")
                return True
            return False

    # ── Reports ───────────────────────────────────────────────────────────

    async def get_session_report(self, session_id: int) -> dict:
        """Returns a detailed summary of all sales within a session."""
        async with AsyncSessionLocal() as session:
            query = (
                select(Sale)
                .where(Sale.session_id == session_id, Sale.status == "completed")
                .options(selectinload(Sale.items))
                .order_by(Sale.created_at)
            )
            result = await session.execute(query)
            sales = result.scalars().all()
            return self._build_report(sales, session)

    async def get_daily_report(self, pier: str, date: datetime.date | None = None) -> dict:
        """
        Returns aggregated daily report for all sales on a pier for a given date.
        Includes profit/margin analytics by cross-referencing product cost prices.
        """
        if date is None:
            date = get_phuket_today()

        day_start, day_end = get_day_bounds(date)

        async with AsyncSessionLocal() as session:
            query = (
                select(Sale)
                .where(
                    Sale.pier == pier,
                    Sale.status == "completed",
                    Sale.created_at >= day_start,
                    Sale.created_at < day_end,
                )
                .options(selectinload(Sale.items))
                .order_by(Sale.created_at)
            )
            result = await session.execute(query)
            sales = result.scalars().all()

            # Fetch product cost prices for margin calculation
            products_result = await session.execute(select(Product))
            all_products = products_result.scalars().all()
            cost_map = {p.name: p.cost_price for p in all_products}

        return self._build_report(sales, cost_map=cost_map, date=date)

    def _build_report(
        self,
        sales: list[Sale],
        cost_map: dict[str, float] | None = None,
        date: datetime.date | None = None,
    ) -> dict:
        """Build a unified report dict from a list of sales."""
        if cost_map is None:
            cost_map = {}

        report = {
            "date": date.strftime("%d.%m.%Y") if date else None,
            "total_amount": 0,
            "total_cost": 0,
            "total_profit": 0,
            "cash_amount": 0,
            "online_amount": 0,
            "sales_count": len(sales),
            "items_summary": {},
            "transactions": [],
        }

        for sale in sales:
            report["total_amount"] += sale.total_amount
            if sale.payment_type == "cash":
                report["cash_amount"] += sale.total_amount
            else:
                report["online_amount"] += sale.total_amount

            tx_items = []
            for item in sale.items:
                name = item.product_name
                cost_per_unit = cost_map.get(name, 0)
                item_cost = cost_per_unit * item.quantity
                item_profit = item.total_price - item_cost

                report["total_cost"] += item_cost
                report["total_profit"] += item_profit

                if name not in report["items_summary"]:
                    report["items_summary"][name] = {
                        "qty": 0,
                        "unit_price": item.price_per_unit,
                        "cost_price": cost_per_unit,
                        "subtotal": 0,
                        "cost_total": 0,
                        "profit": 0,
                        "cash": 0,
                        "online": 0,
                    }
                s = report["items_summary"][name]
                s["qty"] += item.quantity
                s["subtotal"] += item.total_price
                s["cost_total"] += item_cost
                s["profit"] += item_profit
                if sale.payment_type == "cash":
                    s["cash"] += item.total_price
                else:
                    s["online"] += item.total_price

                tx_items.append({
                    "name": item.product_name,
                    "qty": item.quantity,
                    "price": item.price_per_unit,
                    "total": item.total_price,
                    "cost": cost_per_unit,
                })

            report["transactions"].append({
                "sale_id": sale.id,
                "time": sale.created_at.strftime("%H:%M") if sale.created_at else "?",
                "payment": sale.payment_type,
                "amount": sale.total_amount,
                "items": tx_items,
            })

        report["margin_pct"] = (
            round((report["total_profit"] / report["total_amount"] * 100), 1)
            if report["total_amount"] > 0
            else 0
        )

        return report


# Singleton instance
cash_service = CashService()
