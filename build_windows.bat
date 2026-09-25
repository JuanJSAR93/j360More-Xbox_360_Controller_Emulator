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
    --add-data "bin;bin" ^
    --collect-all "resvg_py" ^
    --collect-all "PIL" ^
    --collect-all "qrcode" ^
    gui_app.py

if %errorlevel% neq 0 (
    echo [ERROR] Fallo en la compilacion de Windows.
    exit /b 1
)

echo.
echo [*] Copiando binarios auxiliares a dist/...
if exist "bin" (
    xcopy /e /i /y "bin" "dist\bin" >nul
)

if exist "dist\config_mapping.json" (
    del /q "dist\config_mapping.json"
)

echo.
echo [*] Creando paquete ZIP de Windows (j360More-v1.5.0-windows-amd64.zip)...
python -c "import zipfile, os; z = zipfile.ZipFile('dist/j360More-v1.5.0-windows-amd64.zip', 'w', zipfile.ZIP_DEFLATED); z.write('dist/j360More.exe', 'j360More.exe'); v_src = 'bin/viiper-amd64.exe' if os.path.exists('bin/viiper-amd64.exe') else ('dist/bin/viiper.exe' if os.path.exists('dist/bin/viiper.exe') else ('bin/viiper.exe' if os.path.exists('bin/viiper.exe') else None)); (z.write(v_src, 'bin/viiper.exe') if v_src else None); z.close()"

echo.
echo =======================================================
echo   ¡COMPILACION PARA WINDOWS COMPLETADA CON EXITO!
echo =======================================================
echo Ejecutable: dist\j360More.exe
echo Paquete ZIP: dist\j360More-v1.5.0-windows-amd64.zip
echo =======================================================
