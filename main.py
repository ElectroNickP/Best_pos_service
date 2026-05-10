"""
Best Sea POS Service — Main Application.
A standalone Point-of-Sale microservice for pier operations and tourist shopping.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Run with Docker:
    docker-compose up -d --build
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

from config import config
from models.database import init_db, close_db

# ── Lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info(f"🚀 POS Service starting... (Pier: {config.PIER_NAME})")
    await init_db()
    logger.info("✅ Database initialized.")

    # Initial product sync (non-blocking, failure is OK)
    try:
        from services.sheets_sync import sync_products_from_sheets
        count = await sync_products_from_sheets()
        logger.info(f"📦 Initial product sync: {count} products loaded.")
    except Exception as e:
        logger.warning(f"⚠️ Initial product sync failed (non-critical): {e}")

    yield

    # Shutdown
    await close_db()
    logger.info("🛑 POS Service stopped.")


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Best Sea POS Service",
    description="Standalone Point-of-Sale system for pier operations and tourist shopping.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include API Routers ──────────────────────────────────────────────────

from api.products import router as products_router
from api.sessions import router as sessions_router
from api.sales import router as sales_router
from api.checkout import router as checkout_router
from api.webhooks import router as webhooks_router
from api.health import router as health_router

app.include_router(products_router)
app.include_router(sessions_router)
app.include_router(sales_router)
app.include_router(checkout_router)
app.include_router(webhooks_router)
app.include_router(health_router)

# ── Static Files & Frontend ─────────────────────────────────────────────

STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "static")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_pos_app():
    """Serve the POS frontend (standalone web app or Mini App)."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "POS Service is running. Visit /docs for API documentation."}


@app.get("/shop", include_in_schema=False)
async def serve_tourist_shop():
    """Serve the tourist shop frontend."""
    shop_path = os.path.join(STATIC_DIR, "shop.html")
    if os.path.exists(shop_path):
        return FileResponse(shop_path)
    return {"message": "Tourist shop not deployed. Visit /docs for API documentation."}


# ── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info",
    )
