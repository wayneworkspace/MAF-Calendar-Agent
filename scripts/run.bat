@echo off
REM Double-click to start the bot WITHOUT Docker (creates venv on first run, restarts on crash).
cd /d %~dp0\..
if not exist .venv (
    echo [setup] creating virtual environment...
    py -m venv .venv || python -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r app\requirements.txt
)
:loop
.venv\Scripts\python.exe app\main.py
echo.
echo [bot exited with code %errorlevel%] restarting in 5s... (Ctrl+C to stop)
timeout /t 5 >nul
goto loop
