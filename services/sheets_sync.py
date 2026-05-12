"""
POS Service — Google Sheets Product Sync.
Fetches product data from a Google Sheets price list and pushes it to the database.
"""
import asyncio
import os
import glob
from loguru import logger

from config import config
from services.cash_service import cash_service
from services.settings_service import settings_service


def _find_sa_file() -> str | None:
    """Find the Google Service Account JSON file."""
    sa_dir = config.GOOGLE_SA_PATH
    if not os.path.isdir(sa_dir):
        logger.warning(f"Google SA directory not found: {sa_dir}")
        return None
    json_files = glob.glob(os.path.join(sa_dir, "*.json"))
    return json_files[0] if json_files else None


def _fetch_products_from_sheets(spreadsheet_id: str | None = None) -> list[dict]:
    """
    Synchronous function that reads products from Google Sheets.
    Called via asyncio.to_thread() to avoid blocking the event loop.
    """
    import gspread

    sa_file = _find_sa_file()
    if not sa_file:
        logger.error("No Google Service Account JSON found.")
        return []

    # Use provided spreadsheet_id or fallback to config
    sid = spreadsheet_id or config.STORE_SPREADSHEET_ID
    if not sid:
        logger.warning("No Store Spreadsheet ID provided or configured.")
        return []

    try:
        gc = gspread.service_account(filename=sa_file)
        spreadsheet = gc.open_by_key(sid)

        # Find the "Store Price List" sheet (try common names)
        sheet = None
        for name in ["Store Price List", "Price List", "Прайс", "Products"]:
            try:
                sheet = spreadsheet.worksheet(name)
                break
            except gspread.exceptions.WorksheetNotFound:
                continue

        if not sheet:
            # Fallback to first sheet
            sheet = spreadsheet.sheet1
            logger.warning("Store price list sheet not found by name, using first sheet.")

        all_values = sheet.get_all_values()
        if len(all_values) < 2:
            logger.warning("Price list sheet has no data rows.")
            return []

        # Parse header row to find column indices and normalize homoglyphs
        header = []
        for h in all_values[0]:
            normalized = h.strip().lower()
            # Replace common Cyrillic homoglyphs with Latin equivalents
            replacements = {"с": "c", "а": "a", "е": "e", "о": "o", "р": "p", "х": "x"}
            for cyr, lat in replacements.items():
                normalized = normalized.replace(cyr, lat)
            header.append(normalized)

        # Try to detect columns
        name_col = _find_col(header, ["name", "product", "товар", "название"])
        cost_col = _find_col(header, ["cost", "cost price", "себест", "закуп"])
        sale_col = _find_col(header, ["sale", "sale price", "price", "цена", "продажа"])
        cat_col = _find_col(header, ["category", "категория", "cat", "тип"])

        if name_col is None or sale_col is None:
            logger.error(f"Could not detect required columns. Header: {header}")
            return []
            
        logger.info(f"Detected columns: name={name_col}, cost={cost_col}, sale={sale_col}, cat={cat_col} | Header: {header}")

        products = []
        for row in all_values[1:]:
            if len(row) <= max(name_col, sale_col):
                continue
            raw_name = row[name_col].strip()
            raw_sale = row[sale_col].strip()
            raw_cost = row[cost_col].strip() if cost_col is not None and len(row) > cost_col else "0"
            
            name = raw_name
            if not name:
                continue

            try:
                # Clean value from currency symbols and spaces
                clean_sale = raw_sale.replace("฿", "").replace("$", "").replace(" ", "").replace(",", ".").strip()
                sale_price = float(clean_sale or "0")
            except (ValueError, IndexError):
                logger.warning(f"Failed to parse sale price for '{name}': raw='{raw_sale}'")
                continue

            cost_price = 0
            if cost_col is not None and len(row) > cost_col:
                try:
                    clean_cost = raw_cost.replace("฿", "").replace("$", "").replace(" ", "").replace(",", ".").strip()
                    cost_price = float(clean_cost or "0")
                except ValueError:
                    pass

            category = "Other"
            if cat_col is not None and len(row) > cat_col:
                cat_val = row[cat_col].strip()
                if cat_val:
                    category = cat_val

            logger.debug(f"Parsed product: {name} | Sale: {sale_price} | Cost: {cost_price} | Category: {category}")
            products.append({
                "name": name,
                "cost_price": cost_price,
                "sale_price": sale_price,
                "category": category,
            })

        logger.info(f"Fetched {len(products)} products from Google Sheets.")
        return products

    except Exception as e:
        logger.error(f"Error fetching products from Google Sheets: {e}")
        return []


def _find_col(header: list[str], candidates: list[str]) -> int | None:
    """Find column index by checking multiple possible header names. Prioritizes exact matches."""
    # 1. Try exact matches first
    for i, h in enumerate(header):
        if h in candidates:
            return i
    
    # 2. Try substring matches
    for i, h in enumerate(header):
        for c in candidates:
            if c in h and len(c) > 3: # Avoid matching very short strings like 'id' inside other words
                return i
    return None


async def sync_products_from_sheets() -> int:
    """
    Async wrapper: fetches products from Google Sheets and upserts them into the DB.
    Returns the number of products synced.
    """
    # Try to get dynamic spreadsheet ID from DB settings first
    spreadsheet_id = await settings_service.get("STORE_SPREADSHEET_ID")
    
    products_data = await asyncio.to_thread(_fetch_products_from_sheets, spreadsheet_id)
    if not products_data:
        logger.warning("No products fetched from Google Sheets.")
        return 0

    count = await cash_service.upsert_products(products_data)
    return count
