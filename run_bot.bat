@echo off
cls
color 0A
echo ==========================================
echo    DEAL PULSE BOT — AUTO-RESTART ACTIVE
echo ==========================================
echo.

:: تفعيل venv تلقائياً
call "%~dp0venv\Scripts\activate.bat"

:loop
echo [%time%] Starting bot...
python "%~dp0deal_pulse_bot.py"
echo.
echo [%time%] Bot stopped. Restarting in 3 seconds...
timeout /t 3 >nul
goto loop
