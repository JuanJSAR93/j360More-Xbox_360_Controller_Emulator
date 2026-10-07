@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    python bump_version.py
) else (
    python bump_version.py "%~1"
)

if %errorlevel% equ 0 (
    echo.
    echo =======================================================
    echo Proceso completado con exito.
    echo =======================================================
) else (
    echo.
    echo [ERROR] Ocurrio un error al cambiar la version.
)

pause
