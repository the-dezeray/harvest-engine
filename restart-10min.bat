@echo off
echo.
echo 🔧 Switching to 10-minute aggregation...
echo.
echo Configuration:
echo   ✓ Frequency: 10_minutes (not 1_day)
echo   ✓ Target: n_bytes
echo   ✓ Scale factor: 100,000x
echo.
echo Why 10 minutes?
echo   - Smaller buckets = smaller numbers
echo   - 2.3 billion bytes per 10 min
echo   - = 3.8 million bytes/sec
echo   - Closer to your live traffic!
echo.

echo 🛑 Stopping services...
docker-compose down

echo.
echo 🚀 Restarting services (ML will retrain on 10-min data)...
docker-compose up -d

echo.
echo ⏳ Waiting 15 seconds for ML training...
timeout /t 15 /nobreak >nul

echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo 📈 Expected Values:
echo   Live traffic: ~4 million bytes/sec
echo   Prophet prediction: ~3.8 million bytes/sec
echo   Much closer match!
echo.

echo 🌐 Dashboard: http://localhost:3000
echo 📊 ML Service: http://localhost:8001/health
echo.

echo 🔬 To monitor worker (PowerShell):
echo   docker-compose logs worker --tail 50 ^| Select-String "orchestrator"
echo.

echo ✅ Done! Check the dashboard - should match much better now!
pause
