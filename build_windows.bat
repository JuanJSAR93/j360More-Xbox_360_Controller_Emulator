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
    --version-file "version_info.txt" ^
    --add-data "assets;assets" ^
    --collect-all "vgamepad" ^
    --collect-all "resvg_py" ^
    --collect-all "PIL" ^
    --collect-all "qrcode" ^
    gui_app.py

if %errorlevel% neq 0 (
    echo [ERROR] Fallo en la compilacion de Windows.
    exit /b 1
)

echo.
echo [*] Empaquetando versiones para Windows AMD64 y ARM64...
python package_windows.py

echo.
echo =======================================================
echo   ¡COMPILACION PARA WINDOWS COMPLETADA CON EXITO!
echo =======================================================
echo Paquete AMD64: dist\j360More-v1.6.0-windows-amd64.zip
echo Paquete ARM64: dist\j360More-v1.6.0-windows-arm64.zip
echo Paquete Plugins: dist\j360More-v1.6.0-plugins-support.zip
echo =======================================================
