@echo off
setlocal
echo =======================================================
echo    COMPILADOR LOCAL DE j360More PARA LINUX (DOCKER)
echo =======================================================
echo.

REM Auto-detectar Docker Desktop si no esta en el PATH
where docker >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin" (
        set "PATH=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin;%PATH%"
    ) else if exist "C:\Program Files\Docker\Docker\resources\bin" (
        set "PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%"
    )
)

where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Docker no se encuentra instalado o no esta en el PATH.
    echo Por favor inicia Docker Desktop para compilar localmente para Linux.
    exit /b 1
)

echo [*] Construyendo imagen de compilacion Linux...
docker build -f Dockerfile.linux_build -t j360more-builder:linux .

if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir la imagen de Docker.
    exit /b 1
)

echo.
echo [*] Compilando binario ELF nativo de Linux dentro de Docker...
docker run --rm -v "%cd%:/workspace" -w /workspace j360more-builder:linux bash build_linux.sh

if %errorlevel% neq 0 (
    echo [ERROR] Fallo en la compilacion de Linux.
    exit /b 1
)

REM Extraer j360More en dist si no se pudo copiar directamente por bloqueo virtiofs
if exist "dist\j360More-v1.5.0-linux-x86_64.tar.gz" (
    python -c "import tarfile; t = tarfile.open('dist/j360More-v1.5.0-linux-x86_64.tar.gz'); t.extractall('dist'); t.close()" >nul 2>nul
)

echo.
echo =======================================================
echo    COMPILACION LOCAL PARA LINUX COMPLETADA CON EXITO!
echo =======================================================
echo Archivos generados en dist/:
echo   - dist/j360More
echo   - dist/j360More-v1.5.0-linux-x86_64.tar.gz
echo =======================================================
