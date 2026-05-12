# Best Sea — POS Service (Standalone)

Professional Point-of-Sale (POS) microservice designed for autonomous operation on any pier. It manages sales, cash sessions, and provides detailed financial reporting independently.

---

## 🚀 One-Click Deployment

This service is designed to be moved to any server easily. Follow these steps:

1. **Clone/Copy** this folder to your server.
2. **Setup environment**:
   ```bash
   chmod +x manage.sh
   ./manage.sh setup
   ```
3. **Configure**:
   - Edit the `.env` file (Set your `API_KEY`, `BOT_TOKENS`, and `STORE_SPREADSHEET_ID`).
   - Place your Google Service Account JSON file into the `google_service_account/` directory.
4. **Launch**:
   ```bash
   ./manage.sh start
   ```

---

## 🏗 Features & Autonomy

- **Standalone Operation**: Works independently of the main bot. All logic and data are contained within.
- **Reporting Source of Truth**: Calculates revenue, profit, and margins locally.
- **Auto-Sync**: Automatically fetches product prices from Google Sheets on every session open.
- **Telegram Logging**: Sends real-time logs and daily financial summaries to a Telegram topic.
- **Cross-Platform**: Works as a web app on any device or as a Telegram Mini App.

---

## ⚙️ Configuration (The `.env` file)

| Variable | Description |
|----------|-------------|
| `API_KEY` | Secret key for admin access (e.g., `best_pos_secret_2024`) |
| `BOT_TOKENS` | Tokens of bots that can open this POS as a Mini App |
| `STORE_SPREADSHEET_ID` | The ID of your Google Sheet price list |
| `PIER_NAME` | Name of the pier (e.g., `Yamu`) |

---

## 🛠 Management CLI

Use `./manage.sh` for all operations:
- `./manage.sh start` — Build and start containers in background
- `./manage.sh stop` — Stop all services
- `./manage.sh logs` — View real-time logs (useful for debugging sync/telegram)
- `./manage.sh status` — Check if the service and database are running

---

## 📁 Project Structure

- `api/` — Web endpoints (Sales, Sessions, Checkout)
- `models/` — Database schema (PostgreSQL + SQLAlchemy)
- `services/` — Business logic (Reporting, NSPK Payments, Sheets Sync)
- `web/static/` — Frontend (HTML/JS/CSS)
- `data/` — Local logs and database volume persistence

---

## 🔐 Security

- **Mini App**: Uses HMAC signature verification for secure Telegram integration.
- **Admin**: Uses `X-API-Key` for service-to-service communication.
- **Settings**: Dynamic settings (like Telegram Chat IDs) are stored in the database and can be managed via the "Settings" tab in the UI.

---

## 📄 License & Support
Developed for **Best Sea** operations. For maintenance, check the logs in `data/pos.log` or via `./manage.sh logs`.
