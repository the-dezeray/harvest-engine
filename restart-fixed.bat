@echo off
echo.
echo 🔧 Applying CORRECTED Prophet Scale Fix...
echo.
echo Changes:
echo   ✓ ML Service: n_flows (not n_bytes)
echo   ✓ Scale factor: 2x (not 150,000x)
echo   ✓ Chart rendering: Fixed width/height errors
echo.

echo 🛑 Stopping services...
docker-compose down

echo.
echo 🚀 Restarting services...
docker-compose up -d

echo.
echo ⏳ Waiting 10 seconds for startup...
timeout /t 10 /nobreak >nul

echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo 📈 Expected Values:
echo   Live traffic: ~80 flows/sec
echo   Prophet prediction: ~69 flows/sec
echo   Should match closely!
echo.

echo 🌐 Dashboard: http://localhost:3000
echo 📊 ML Service: http://localhost:8001/health
echo.

echo 🔬 To monitor worker (PowerShell):
echo   docker-compose logs worker --tail 50 ^| Select-String "orchestrator"
echo.

echo ✅ Done! Check the dashboard - values should now match!
pause
