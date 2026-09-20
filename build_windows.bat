@echo off
setlocal
echo =======================================================
echo       COMPILADOR OFICIAL DE j360More PARA WINDOWS
echo =======================================================
echo.

echo [*] Verificando dependencias de Python...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo [*] Compilando ejecutable standalone de Windows (PyInstaller)...
python -m PyInstaller --noconfirm --onefile --windowed --noupx ^
    --name "j360More" ^
    --icon "assets/icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "bin;bin" ^
    --collect-all "resvg_py" ^
    gui_app.py

if %errorlevel% neq 0 (
    echo [ERROR] Fallo en la compilacion de Windows.
    exit /b 1
)

echo.
echo [*] Copiando archivos de configuracion y binarios a dist/...
if exist "config_mapping.json" (
    copy /y "config_mapping.json" "dist\" >nul
)

if exist "bin" (
    xcopy /e /i /y "bin" "dist\bin" >nul
)

echo.
echo =======================================================
echo   ¡COMPILACION PARA WINDOWS COMPLETADA CON EXITO!
echo =======================================================
echo Ejecutable: dist\j360More.exe
echo =======================================================
