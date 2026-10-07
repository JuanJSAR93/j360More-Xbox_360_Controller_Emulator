@echo off
setlocal
cd /d "%~dp0"

:: Verificar si ya tiene privilegios de Administrador
fsutil dirty query %systemdrive% >nul 2>&1
if %errorlevel% equ 0 (
    goto :run_server
)

echo Solicitando permisos de Administrador a Windows...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd.exe -ArgumentList '/c \"\"%~f0\"\" :elevated' -Verb RunAs"
exit /b

:run_server
title Servidor HIDMaestro (MODO ADMINISTRADOR)
if exist "%~dp0bin\hidmaestro_host-amd64.exe" (
    cd /d "%~dp0bin"
) else if exist "%~dp0bin\hidmaestro" (
    cd /d "%~dp0bin\hidmaestro"
) else (
    cd /d "%~dp0bin"
)

echo ===================================================
echo   Iniciando HIDMaestro Host con Privilegios Elevados
echo ===================================================

if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" (
    if exist "hidmaestro_host-arm64.exe" (
        hidmaestro_host-arm64.exe --port=3255
        goto :eof
    )
    if exist "arm64\hidmaestro_host.exe" (
        arm64\hidmaestro_host.exe --port=3255
        goto :eof
    )
)

if exist "hidmaestro_host-amd64.exe" (
    hidmaestro_host-amd64.exe --port=3255
    goto :eof
)
if exist "hidmaestro_host.exe" (
    hidmaestro_host.exe --port=3255
    goto :eof
)
if exist "amd64\hidmaestro_host.exe" (
    amd64\hidmaestro_host.exe --port=3255
    goto :eof
)
