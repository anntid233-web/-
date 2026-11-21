#!/bin/bash
# Proxy Shop Bot - Run script

set -e

# Check for .env file
if [ ! -f .env ]; then
    echo "❌ .env file not found! Copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check required variables
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ BOT_TOKEN not set in .env"
    exit 1
fi

echo "🚀 Starting Proxy Shop Bot..."

# Create data directory
mkdir -p data

# Run with Docker Compose if available
if command -v docker-compose &> /dev/null; then
    echo "🐳 Using Docker Compose..."
    docker-compose up -d --build
    echo "✅ Bot started in background. Check logs: docker-compose logs -f"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "🐳 Using Docker Compose v2..."
    docker compose up -d --build
    echo "✅ Bot started in background. Check logs: docker compose logs -f"
else
    echo "🐍 Using Python directly..."
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON=python3
    elif command -v python &> /dev/null; then
        PYTHON=python
    else
        echo "❌ Python not found. Install Python 3.10+ or use Docker."
        exit 1
    fi
    
    # Install dependencies
    echo "📦 Installing dependencies..."
    $PYTHON -m pip install -r requirements.txt --quiet
    
    # Run bot
    echo "✅ Starting bot..."
    $PYTHON main.py
fi