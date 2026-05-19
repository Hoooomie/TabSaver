@echo off
title TabSaver Setup

echo ========================================
echo    TabSaver - Chrome Tab Saver Setup
echo ========================================
echo.

:: ========== 1. Create data directories ==========
echo [1/5] Creating data directories...
set "DATA_DIR=%APPDATA%\TabSaver\data"
set "HOST_DIR=%APPDATA%\TabSaver\native-host"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%HOST_DIR%" mkdir "%HOST_DIR%"
echo       Done: %APPDATA%\TabSaver\

:: ========== 2. Copy Native Host files ==========
echo [2/5] Installing Native Messaging Host...
set "SCRIPT_DIR=%~dp0"
copy /Y "%SCRIPT_DIR%native-host\tab_saver_host.py" "%HOST_DIR%\" >nul 2>&1
if errorlevel 1 (
    echo       [ERROR] Failed to copy tab_saver_host.py!
    pause
    exit /b 1
)
echo       Native Host script installed.

:: ========== 3. Ask for Extension ID ==========
echo [3/5] Extension ID configuration...
echo.
echo   To find your Extension ID:
echo     1. Open Chrome and go to chrome://extensions/
echo     2. Enable "Developer mode" (top right)
echo     3. Click "Load unpacked" and select: %SCRIPT_DIR%extension
echo     4. The Extension ID will appear on the extension card
echo.
set /p "EXT_ID=   Enter your Extension ID: "

if "%EXT_ID%"=="" (
    echo.
    echo       [WARNING] No Extension ID provided.
    echo       The manifest will use a placeholder. You MUST edit it later:
    echo       %HOST_DIR%\com.tabsaver.host.json
    set "EXT_ID=EXTENSION_ID_PLACEHOLDER"
)

:: ========== 4. Generate and register NM manifest ==========
echo [4/5] Registering Native Messaging Host...

set "HOST_SCRIPT=%HOST_DIR%\tab_saver_host.py"
set "MANIFEST_FILE=%HOST_DIR%\com.tabsaver.host.json"

:: Use Python to generate manifest with correct path and extension ID
python -c "import json,sys;m=json.load(open(r'%SCRIPT_DIR%native-host\com.tabsaver.host.json','r',encoding='utf-8'));m['path']=r'%HOST_SCRIPT%';m['allowed_origins']=['chrome-extension://%s/'%sys.argv[1]];json.dump(m,open(r'%MANIFEST_FILE%','w',encoding='utf-8'),indent=2,ensure_ascii=False)" "%EXT_ID%" 2>nul

if not exist "%MANIFEST_FILE%" (
    echo       [ERROR] Failed to generate manifest file!
    pause
    exit /b 1
)
echo       Manifest generated: %MANIFEST_FILE%

:: Write to Windows registry
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.tabsaver.host" /ve /t REG_SZ /d "%MANIFEST_FILE%" /f >nul 2>&1
if errorlevel 1 (
    echo       [ERROR] Failed to write registry!
    pause
    exit /b 1
)
echo       Registry entry created.

:: ========== 5. Initialize sessions data ==========
echo [5/5] Initializing data file...
set "SESSIONS_FILE=%DATA_DIR%\sessions.json"
if not exist "%SESSIONS_FILE%" (
    echo {"sessions": []} > "%SESSIONS_FILE%"
    echo       Sessions data file created.
) else (
    echo       Sessions data file already exists, skipped.
)

:: ========== Done ==========
echo.
echo ========================================
echo          Setup Complete!
echo ========================================
echo.
if not "%EXT_ID%"=="EXTENSION_ID_PLACEHOLDER" (
    echo   Extension ID: %EXT_ID%
    echo.
    echo   You can now use TabSaver! Just reload the
    echo   extension in chrome://extensions/ if needed.
) else (
    echo   [ACTION REQUIRED] You skipped the Extension ID.
    echo   Please edit this file and replace EXTENSION_ID_PLACEHOLDER:
    echo   %MANIFEST_FILE%
)
echo.
echo   Desktop app: Run start.bat
echo.
pause
