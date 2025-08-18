#!/bin/bash

# Driftor Local Development Startup Script

set -e

echo "🚀 Starting Driftor Local Development Environment"
echo "================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    
    echo "⚠️  Please edit .env file with your configuration:"
    echo "   - Set secure SECRET_KEY, ENCRYPTION_KEY, JWT_SECRET_KEY"
    echo "   - Configure integrations (Jira, GitHub, Slack) if needed"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "🔧 Starting infrastructure services..."

# Start Docker services (using local compose file without Vault)
docker-compose -f docker-compose.local.yml up -d

echo "⏳ Waiting for services to be ready..."

# Wait for PostgreSQL
echo "  Waiting for PostgreSQL..."
until docker exec driftor_v2-postgres-1 pg_isready -U driftor > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ PostgreSQL is ready"

# Wait for Redis
echo "  Waiting for Redis..."
until docker exec driftor_v2-redis-1 redis-cli ping > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ Redis is ready"

# Wait for ChromaDB
echo "  Waiting for ChromaDB..."
until curl -s http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ ChromaDB is ready"

# Wait for Ollama and pull model
echo "  Waiting for Ollama..."
until curl -s http://localhost:11434 > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ Ollama is ready"

echo "  Pulling Ollama model (this may take a few minutes)..."
docker exec driftor_v2-ollama-1 ollama pull llama3.1:8b || echo "  ⚠️  Model pull failed, will try to use existing model"

echo "🐍 Setting up Python environment..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade pip
pip install --upgrade pip

# Install dependencies
echo "  Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install -e .
fi

echo "🗄️  Setting up database..."

# Run database migrations
python -m alembic upgrade head

echo "📊 Creating test data..."

# Create test data
python scripts/create_test_data.py

echo "🎯 Starting Driftor API server..."

# Start the main application
python -m driftor.main &
API_PID=$!

# Wait a moment for the server to start
sleep 5

echo ""
echo "✅ Driftor is now running!"
echo "=========================="
echo ""
echo "🌐 Services:"
echo "   API Server:      http://localhost:8000"
echo "   API Docs:        http://localhost:8000/docs" 
echo "   Health Check:    http://localhost:8000/health"
echo "   Grafana:         http://localhost:3000 (admin/admin)"
echo "   Prometheus:      http://localhost:9090"
echo ""
echo "🧪 Test the system:"
echo "   python scripts/test_api.py"
echo ""
echo "📝 View logs:"
echo "   tail -f logs/driftor.log"
echo ""
echo "⏹️  To stop:"
echo "   Ctrl+C to stop API server"
echo "   docker-compose down to stop all services"
echo ""

# Keep the script running until Ctrl+C
trap "echo ''; echo '⏹️  Stopping Driftor...'; kill $API_PID 2>/dev/null; docker-compose -f docker-compose.local.yml down; echo 'Stopped.'; exit 0" INT

echo "Press Ctrl+C to stop all services..."
wait $API_PID