@echo off
chcp 65001 > nul
title Compilador j360More - PyInstaller

echo =======================================================
echo          COMPILADOR OFICIAL DE j360More (UI)
echo =======================================================
echo.

:: 1. Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no está instalado o no se encuentra en el PATH.
    echo Por favor, instala Python 3.10 o superior y vuelve a intentar.
    pause
    exit /b 1
)

:: 2. Instalar / verificar dependencias
echo [*] Verificando e instalando dependencias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Hubo un problema instalando las dependencias.
    pause
    exit /b 1
)

:: 3. Limpiar carpetas temporales build y dist anteriores
echo [*] Limpiando carpetas temporales build y dist...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: 3.5 Generar icon.ico a partir de icon.svg si es necesario
echo [*] Verificando iconos de la aplicación...
if exist "assets\icon.svg" (
    python -c "import os, io, resvg_py; from PIL import Image; (lambda: [open('assets/icon.png', 'wb').write(resvg_py.svg_to_bytes(svg_path='assets/icon.svg', width=256)), Image.open('assets/icon.png').save('assets/icon.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])] if not os.path.exists('assets/icon.ico') else None)()"
)

:: 4. Seleccionar modo de empaquetado
echo.
echo Selecciona el formato de compilación:
echo   [1] Archivo Único (Solo j360More.exe + config_mapping.json) [Por defecto]
echo   [2] Aplicación Distribuida (Arranque ultra rápido en carpeta dist\j360More\)
echo.
set "BUILD_MODE=1"
set /p "USER_CHOICE=Ingresa 1 o 2 (Enter para 1): "
if "%USER_CHOICE%"=="2" set "BUILD_MODE=2"

if "%BUILD_MODE%"=="1" (
    echo.
    echo [*] Compilando j360More en UN SOLO ARCHIVO (.exe standalone)...
    pyinstaller --noconfirm --onefile --windowed --noupx ^
        --name "j360More" ^
        --icon "assets\icon.ico" ^
        --version-file "version_info.txt" ^
        --add-data "assets;assets" ^
        --add-data "bin;bin" ^
        --collect-all "vgamepad" ^
        --collect-all "resvg_py" ^
        gui_app.py
    
    if %errorlevel% neq 0 (
        echo [ERROR] La compilación falló. Revisa los mensajes de error arriba.
        pause
        exit /b 1
    )
    
    echo [*] Copiando config_mapping.json y binarios auxiliares junto al ejecutable...
    if exist "config_mapping.json" copy /y "config_mapping.json" "dist\" >nul
    if exist "bin" xcopy /e /i /y "bin" "dist\bin" >nul
    
    echo.
    echo =======================================================
    echo     ¡COMPILACIÓN EXITOSA (ARCHIVO ÚNICO)!
    echo =======================================================
    echo Ejecutable listo en: dist\j360More.exe
    echo Configuración en:   dist\config_mapping.json
    echo (No requiere carpeta _internal)
    echo.
) else (
    echo.
    echo [*] Compilando j360More en modo aplicación distribuida (Arranque instantáneo)...
    pyinstaller --noconfirm --onedir --windowed ^
        --name "j360More" ^
        --icon "assets\icon.ico" ^
        --version-file "version_info.txt" ^
        --add-data "assets;assets" ^
        --add-data "bin;bin" ^
        --collect-all "vgamepad" ^
        --collect-all "resvg_py" ^
        gui_app.py
    
    if %errorlevel% neq 0 (
        echo [ERROR] La compilación falló. Revisa los mensajes de error arriba.
        pause
        exit /b 1
    )
    
    echo [*] Copiando archivos de configuración a dist\j360More...
    if exist "config_mapping.json" copy /y "config_mapping.json" "dist\j360More\" >nul
    if exist "assets" xcopy /e /i /y "assets" "dist\j360More\assets" >nul
    if exist "bin" xcopy /e /i /y "bin" "dist\j360More\bin" >nul
    attrib +h "dist\j360More\_internal" >nul 2>&1
    
    echo.
    echo =======================================================
    echo     ¡COMPILACIÓN EXITOSA (MODO RÁPIDO)!
    echo =======================================================
    echo Aplicación lista en: dist\j360More\j360More.exe
    echo.
)
pause
