#!/bin/bash
# Intelli-Credit - Quick Setup & Run Script

set -e

echo "🏦 Intelli-Credit — AI Credit Decisioning Engine"
echo "================================================="

# Backend setup
echo ""
echo "📦 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

# Copy .env if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created .env from .env.example — please add your API keys!"
fi

cd ..

# Frontend setup
echo ""
echo "📦 Setting up frontend..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install --silent
fi
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run the application:"
echo "  Terminal 1 (Backend):  cd backend && source venv/bin/activate && python main.py"
echo "  Terminal 2 (Frontend): cd frontend && npm start"
echo ""
echo "Backend will be at:  http://localhost:8000"
echo "Frontend will be at: http://localhost:3000"
echo "API docs at:         http://localhost:8000/docs"
