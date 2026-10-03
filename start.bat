@echo off
setlocal EnableExtensions
title CCS screening - launcher

rem Starts the CCS screening app for local manual testing:
rem   backend  -> http://127.0.0.1:8000  (FastAPI, run from src\ without installing)
rem   frontend -> http://localhost:3000  (Next.js dev server)
rem Each server runs in its own window. Close that window (or press Ctrl+C in it)
rem to stop it. Open the app at http://localhost:3000, not 127.0.0.1:3000: the
rem backend only accepts browser requests from exactly http://localhost:3000.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND_URL=http://127.0.0.1:8000"
set "FRONTEND_URL=http://localhost:3000"
set "WAIT_SECONDS=90"

echo Checking prerequisites...
where python >nul 2>&1 || (echo ERROR: python was not found on PATH.& goto :fail)
where npm >nul 2>&1 || (echo ERROR: npm was not found on PATH.& goto :fail)
where curl.exe >nul 2>&1 || (echo ERROR: curl.exe was not found; it is needed for the health checks.& goto :fail)
python -c "import fastapi, uvicorn, openpyxl, numpy, scipy" >nul 2>&1 || (echo ERROR: missing Python packages. Run: python -m pip install -e ".[dev,web]"& goto :fail)
if not exist "%ROOT%\data\Requested_data_GEOTHOPICA_pozzi_piemonte.xlsx" (echo ERROR: dataset not found in "%ROOT%\data".& goto :fail)
if not exist "%ROOT%\frontend\node_modules" (echo ERROR: frontend dependencies missing. Run "npm ci" in "%ROOT%\frontend".& goto :fail)
call :port_free 8000 || goto :fail
call :port_free 3000 || goto :fail

echo Starting backend on %BACKEND_URL% ...
set "PYTHONPATH=%ROOT%\src"
set "CCS_CORS_ORIGINS=%FRONTEND_URL%"
start "CCS backend (port 8000)" /D "%ROOT%" cmd /k python -m uvicorn ccs_screen.web.app:app --host 127.0.0.1 --port 8000
call :wait_for "%BACKEND_URL%/health" backend || goto :fail
echo Backend is healthy.

echo Starting frontend on %FRONTEND_URL% ...
start "CCS frontend (port 3000)" /D "%ROOT%\frontend" cmd /k npm run dev
call :wait_for "%FRONTEND_URL%" frontend || goto :fail
echo Frontend is ready.

start "" "%FRONTEND_URL%"
echo.
echo Running.
echo   Frontend: %FRONTEND_URL%
echo   Backend:  %BACKEND_URL%   (API docs: %BACKEND_URL%/docs)
echo To stop, close the "CCS backend" and "CCS frontend" windows.
echo.
pause
exit /b 0

rem -- helpers ---------------------------------------------------------------

:port_free
netstat -ano | findstr /R /C:":%~1 .*LISTENING" >nul
if not errorlevel 1 (
    echo ERROR: port %~1 is already in use. Stop whatever is using it and try again.
    exit /b 1
)
exit /b 0

:wait_for
set /a "_tries=0"
:wait_loop
curl.exe -sf -o nul "%~1" >nul 2>&1 && exit /b 0
set /a "_tries+=1"
if %_tries% geq %WAIT_SECONDS% (
    echo ERROR: the %~2 did not respond at %~1 within %WAIT_SECONDS% seconds. Check its window for errors.
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto :wait_loop

:fail
echo.
echo Startup aborted.
pause
exit /b 1
