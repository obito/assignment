#!/bin/bash

# Start LiveKit Voice Agent with Monitoring Stack
# This script starts Prometheus, Grafana, and the voice agent

echo "🚀 Starting LiveKit Voice Agent with Monitoring Stack..."

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo "❌ Error: .env.local file not found!"
    echo "Please create .env.local with your API keys:"
    echo "LIVEKIT_URL=your_livekit_url"
    echo "LIVEKIT_API_KEY=your_api_key"
    echo "LIVEKIT_API_SECRET=your_api_secret"
    echo "OPENAI_API_KEY=your_openai_key"
    exit 1
fi

# Start the monitoring stack
echo "📊 Starting monitoring services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service status
echo "🔍 Checking service status..."
docker-compose ps

# Display access information
echo ""
echo "✅ Monitoring stack started successfully!"
echo ""
echo "📊 Access your dashboards:"
echo "   Grafana Dashboard: http://localhost:3000 (admin/admin)"
echo "   Prometheus Metrics: http://localhost:9090"
echo "   Voice Agent Metrics: http://localhost:8000/metrics"
echo ""
echo "🧪 Run latency tests:"
echo "   uv run python test_latency.py"
echo ""
echo "📋 View logs:"
echo "   docker-compose logs -f voice-agent"
echo "   docker-compose logs -f prometheus"
echo "   docker-compose logs -f grafana"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
