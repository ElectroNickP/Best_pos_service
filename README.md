# Best Sea — POS Service

Standalone Point-of-Sale microservice for pier operations and tourist shopping.

## Features

- 🛒 **POS Register** — Cash sessions, multi-item sales (cash & online), daily reports
- 📦 **Product Management** — Auto-sync from Google Sheets, categories, cost/sale prices
- 💳 **NSPK Payments** — Russian SBP → THB conversion for tourist online orders
- 📊 **Analytics** — Revenue, cost, profit, margin per product and per day
- 🔐 **Dual Auth** — API Key (for bot integration) + Telegram initData (for Mini App)
- 🌐 **Dual Frontend** — Works as both standalone web app and Telegram Mini App

## Quick Start

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your API_KEY, BOT_TOKENS, STORE_SPREADSHEET_ID
# Place Google Service Account JSON in google_service_account/

docker-compose up -d --build
# POS available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL (Docker or local)
docker run -d --name pos_db -e POSTGRES_DB=pos_db -e POSTGRES_USER=pos_user -e POSTGRES_PASSWORD=pos_password -p 5433:5432 postgres:16-alpine

cp .env.example .env
# Edit .env

python main.py
```

## API Documentation

Once running, visit **http://localhost:8000/docs** for interactive Swagger UI.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/products` | List active products |
| POST | `/api/v1/products/sync` | Sync from Google Sheets |
| GET | `/api/v1/sessions/active?pier=Yamu` | Get active session |
| POST | `/api/v1/sessions/open` | Open cash session |
| POST | `/api/v1/sessions/close` | Close session |
| POST | `/api/v1/sales` | Record a sale |
| GET | `/api/v1/sales/daily-report?pier=Yamu` | Daily report |
| POST | `/api/v1/checkout` | Tourist order + NSPK payment |
| GET | `/health` | Health check |

### Authentication

- **Bot integration**: Pass `X-API-Key: <your-key>` header
- **Mini App**: Telegram `initData` validated against configured bot tokens
- **URL token**: `?token=<hmac-token>` for backward compatibility

## Integration with Telegram Bot

Add to the bot's `.env`:
```
POS_API_URL=http://localhost:8000
POS_API_KEY=your-secret-api-key-change-me
```

The bot uses `services/pos_client.py` to communicate with this service.

## Architecture

```
Best_pos_service/
├── main.py              # FastAPI application
├── config.py            # Environment-based configuration
├── api/                 # REST API endpoints
│   ├── auth.py          # Authentication (API Key + Telegram)
│   ├── products.py      # Product management
│   ├── sessions.py      # Cash sessions
│   ├── sales.py         # Sales & reports
│   ├── checkout.py      # Tourist checkout + NSPK
│   └── health.py        # Health check
├── models/              # Database layer
│   ├── database.py      # Async engine + sessions
│   └── schemas.py       # SQLAlchemy models
├── services/            # Business logic
│   ├── cash_service.py  # Core POS operations
│   ├── payment_service.py # NSPK (async)
│   ├── sheets_sync.py   # Google Sheets sync
│   └── time_utils.py    # Phuket timezone
└── web/static/          # Frontend (POS + Tourist Shop)
```
