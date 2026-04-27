@echo off
echo.
echo 🔧 Switching to n_bytes with proper scale...
echo.
echo Configuration:
echo   ✓ ML Service: n_bytes (network traffic in bytes)
echo   ✓ Scale factor: 375,000x
echo   ✓ Expected: ~15 million bytes/sec
echo.

echo 🛑 Stopping services...
docker-compose down

echo.
echo 🚀 Restarting services (ML will retrain on n_bytes)...
docker-compose up -d

echo.
echo ⏳ Waiting 15 seconds for ML training...
timeout /t 15 /nobreak >nul

echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo 📈 Expected Values:
echo   Live traffic: ~15 million bytes/sec
echo   Prophet prediction: ~14-16 million bytes/sec
echo   Much bigger numbers than n_flows!
echo.

echo 🌐 Dashboard: http://localhost:3000
echo 📊 ML Service: http://localhost:8001/health
echo.

echo 🔬 To monitor worker (PowerShell):
echo   docker-compose logs worker --tail 50 ^| Select-String "orchestrator"
echo.

echo ✅ Done! Check the dashboard - should show millions of bytes/sec!
pause
