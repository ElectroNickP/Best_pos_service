#!/bin/bash

# Best Sea — POS Service Management Script
# Usage: ./manage.sh [start|stop|restart|logs|status|setup]

COMMAND=$1

case $COMMAND in
  setup)
    echo "🏗  Setting up environment..."
    if [ ! -f .env ]; then
      echo "📝 Creating .env from .env.example..."
      cp .env.example .env
      echo "⚠️  Please edit .env and provide your API keys and spreadsheet IDs!"
    fi
    mkdir -p google_service_account
    mkdir -p data
    echo "✅ Setup complete. Put your Google Service Account JSON in 'google_service_account/' folder."
    ;;

  start)
    echo "🚀 Starting POS Service..."
    docker compose up -d --build
    echo "✅ Service started at http://localhost:8000"
    echo "📜 View logs with: ./manage.sh logs"
    ;;

  stop)
    echo "🛑 Stopping POS Service..."
    docker compose down
    ;;

  restart)
    echo "🔄 Restarting POS Service..."
    docker compose restart
    ;;

  logs)
    docker compose logs -f pos
    ;;

  status)
    docker compose ps
    ;;

  *)
    echo "Usage: $0 {start|stop|restart|logs|status|setup}"
    exit 1
    ;;
esac
