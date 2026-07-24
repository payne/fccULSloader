@echo off
echo Offline Callsign Lookup Installer for Windows

REM Check for Python installation
python --version > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.7 or higher from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Install required packages quietly
echo Installing dependencies...
pip install -q -r src/requirements.txt pyinstaller
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to install dependencies.
    pause
    exit /b 1
)

REM Clean only build artifacts, preserving dist folder
if exist build rmdir /s /q build > nul 2>&1
if exist *.spec del /f /q *.spec > nul 2>&1

echo Building executable...
python create_build\build_executable.py --platform windows --quiet > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to build executable.
    pause
    exit /b 1
)

REM Clean up silently - but preserve dist folder
echo Cleaning up build artifacts...
if exist build rmdir /s /q build > nul 2>&1
if exist *.spec del /f /q *.spec > nul 2>&1
if exist __pycache__ rmdir /s /q __pycache__ > nul 2>&1
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" > nul 2>&1
if exist "callsign-lookup-*.pkg" del /f /q "callsign-lookup-*.pkg" > nul 2>&1
if exist "callsign-lookup-*.exe.manifest" del /f /q "callsign-lookup-*.exe.manifest" > nul 2>&1
if exist "warn-callsign-lookup-*.txt" del /f /q "warn-callsign-lookup-*.txt" > nul 2>&1

REM Double-check that build folder is gone (sometimes it's recreated)
timeout /t 1 /nobreak > nul
if exist build rmdir /s /q build > nul 2>&1

REM Get version from build_executable.py directly
for /f "tokens=*" %%i in ('python create_build\build_executable.py --get-version') do set VERSION=%%i

echo Build completed successfully.
echo Executable: dist\callsign-lookup-windows\callsign-lookup-%VERSION%.exe