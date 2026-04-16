:: =============================================================================
:: Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
:: Date   : 10 April 2026
:: =============================================================================
@echo off
setlocal enabledelayedexpansion
title Stock Analysis Agent - Startup

:: ── Change to project root ──────────────────────────────────
cd /d "%~dp0"

echo ============================================================
echo   Stock Analysis Agent - Startup Check
echo ============================================================
echo.

:: ── 1. Check Python ──────────────────────────────────────────
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Python not found. Please install Python 3.11+ and add it to PATH.
    echo          Download from: https://www.python.org/downloads/
    goto :error
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo   [OK]   Python %PY_VER% found.

:: ── 2. Check uv ──────────────────────────────────────────────
echo [2/5] Checking uv package manager...
uv --version >nul 2>&1
if errorlevel 1 (
    echo   [WARN] uv not found. Installing uv now...
    pip install uv >nul 2>&1
    if errorlevel 1 (
        echo   [FAIL] Could not install uv. Install manually:
        echo          pip install uv
        echo          OR: https://docs.astral.sh/uv/getting-started/installation/
        goto :error
    )
    echo   [OK]   uv installed.
) else (
    for /f "tokens=1,2" %%a in ('uv --version 2^>^&1') do set UV_VER=%%b
    echo   [OK]   uv !UV_VER! found.
)

:: ── 3. Check .env ────────────────────────────────────────────
echo [3/5] Checking .env configuration...
if not exist ".env" (
    echo   [WARN] .env file not found.
    if exist ".env.example" (
        echo          Copying .env.example to .env...
        copy ".env.example" ".env" >nul
        echo   [WARN] .env created from template. Please edit it with your AWS credentials:
        echo          AWS_ACCESS_KEY_ID=your_key_here
        echo          AWS_SECRET_ACCESS_KEY=your_secret_here
        echo.
        set /p OPEN_ENV="   Open .env in Notepad now? [Y/N]: "
        if /i "!OPEN_ENV!"=="Y" (
            notepad .env
            echo   Waiting for you to save .env...
            pause
        )
    ) else (
        echo   [FAIL] Neither .env nor .env.example found. Cannot proceed.
        goto :error
    )
) else (
    :: Check that AWS keys are not empty
    findstr /i "AWS_ACCESS_KEY_ID=$" .env >nul 2>&1
    if not errorlevel 1 (
        echo   [WARN] .env has empty AWS credentials. Please update before running analysis.
        set /p OPEN_ENV2="   Open .env in Notepad now? [Y/N]: "
        if /i "!OPEN_ENV2!"=="Y" (
            notepad .env
            echo   Waiting for you to save .env...
            pause
        )
    ) else (
        echo   [OK]   .env found and configured.
    )
)

:: ── 4. Install / sync dependencies ───────────────────────────
echo [4/5] Syncing Python dependencies with uv...
uv sync --quiet
if errorlevel 1 (
    echo   [FAIL] Dependency sync failed. Check pyproject.toml and internet connectivity.
    echo          Try manually: uv sync
    goto :error
)
echo   [OK]   All dependencies installed.

:: ── 5. Create session directory ──────────────────────────────
if not exist ".sessions" mkdir .sessions
echo   [OK]   Session directory ready.

:: ── Launch ───────────────────────────────────────────────────
echo.
echo ============================================================
echo   Stock Analysis Agent starting at: http://localhost:8510
echo   Press Ctrl+C in this window to stop the server.
echo ============================================================
echo.
echo   Usage modes:
echo     - Single stock: Enter a ticker like NSE:RELIANCE or AAPL
echo     - Batch mode:   Upload a stocks.txt file
echo.

:: Open browser after a short delay
start "" /b cmd /c "timeout /t 3 >nul && start http://localhost:8510"

:: Start Streamlit
uv run streamlit run src/ui/Home.py --server.port 8510 --server.headless false
goto :eof

:error
echo.
echo ============================================================
echo   Startup failed. Fix the issues above and re-run startup.bat
echo ============================================================
pause
exit /b 1
