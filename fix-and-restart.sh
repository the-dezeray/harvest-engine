#!/bin/bash

echo "🔧 Applying Prophet Scale Fix..."
echo ""

echo "📋 Changes applied:"
echo "  ✓ ML Service now trains on n_flows (not n_bytes)"
echo "  ✓ Scale factor increased to 150,000"
echo "  ✓ Frontend updated to use new scale"
echo ""

echo "🛑 Stopping services..."
docker-compose down

echo ""
echo "🚀 Starting services (ML will retrain on startup)..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "🔍 Checking ML Service (training may take 30-60 seconds)..."
sleep 10

echo ""
echo "📈 ML Service Health:"
curl -s http://localhost:8001/health | python -m json.tool 2>/dev/null || echo "ML service still starting..."

echo ""
echo "📊 API Status:"
curl -s http://localhost:8000/ | python -m json.tool 2>/dev/null || echo "API still starting..."

echo ""
echo "✅ Fix applied! Monitor the dashboard at http://localhost:3000"
echo ""
echo "Expected behavior:"
echo "  - Live traffic: 5-10 million (scaled)"
echo "  - Predicted: 4-12 million"
echo "  - Should be within same order of magnitude"
echo ""
echo "📝 See PROPHET_SCALE_FIX.md for details"
echo ""
echo "🔬 To monitor worker predictions:"
echo "  docker-compose logs -f worker | grep orchestrator"
