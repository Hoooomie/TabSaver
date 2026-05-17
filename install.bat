@echo off
title TabSaver Setup

echo ========================================
echo    TabSaver - Chrome Tab Saver Setup
echo ========================================
echo.

:: ========== 1. Create data directories ==========
echo [1/4] Creating data directories...
set "DATA_DIR=%APPDATA%\TabSaver\data"
set "HOST_DIR=%APPDATA%\TabSaver\native-host"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%HOST_DIR%" mkdir "%HOST_DIR%"
echo       Done: %APPDATA%\TabSaver\

:: ========== 2. Copy Native Host files ==========
echo [2/4] Installing Native Messaging Host...
set "SCRIPT_DIR=%~dp0"
copy /Y "%SCRIPT_DIR%native-host\tab_saver_host.py" "%HOST_DIR%\" >nul 2>&1
if errorlevel 1 (
    echo       [ERROR] Failed to copy tab_saver_host.py!
    pause
    exit /b 1
)
echo       Native Host script installed.

:: ========== 3. Generate and register NM manifest ==========
echo [3/4] Registering Native Messaging Host...

set "HOST_SCRIPT=%HOST_DIR%\tab_saver_host.py"
set "MANIFEST_FILE=%HOST_DIR%\com.tabsaver.host.json"

:: Use Python to generate manifest (avoids JSON escaping issues in batch)
python -c "import json; m=json.load(open(r'%SCRIPT_DIR%native-host\com.tabsaver.host.json','r',encoding='utf-8')); m['path']=r'%HOST_SCRIPT%'; json.dump(m,open(r'%MANIFEST_FILE%','w',encoding='utf-8'),indent=2,ensure_ascii=False)" 2>nul

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

:: ========== 4. Initialize sessions data ==========
echo [4/4] Initializing data file...
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
echo Next steps:
echo.
echo   1. Open Chrome browser
echo   2. Go to chrome://extensions/
echo   3. Enable "Developer mode" (top right)
echo   4. Click "Load unpacked"
echo   5. Select folder: %SCRIPT_DIR%extension
echo   6. Note the Extension ID (on the extension card)
echo.
echo   7. Edit file: %MANIFEST_FILE%
echo      Replace EXTENSION_ID_PLACEHOLDER with your actual Extension ID
echo      Format: chrome-extension://YOUR_EXTENSION_ID/
echo.
echo   8. Run start.bat to launch the desktop app
echo.
echo IMPORTANT: Step 7 is required! The extension cannot
echo communicate with the Native Host without it.
echo.
pause
