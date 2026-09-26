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

echo [*] Construyendo imagen de compilacion Linux (amd64)...
docker build --platform linux/amd64 -f Dockerfile.linux_build -t j360more-builder:linux-amd64 .

if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir la imagen de Docker para amd64.
    exit /b 1
)

echo.
echo [*] Compilando binario ELF nativo de Linux amd64 dentro de Docker...
docker run --rm --platform linux/amd64 -v "%cd%:/workspace" -w /workspace j360more-builder:linux-amd64 bash build_linux.sh

if %errorlevel% neq 0 (
    echo [ERROR] Fallo en la compilacion de Linux amd64.
    exit /b 1
)

if exist "dist\j360More-v1.5.1-linux-amd64.tar.gz" (
    python -c "import tarfile; t = tarfile.open('dist/j360More-v1.5.1-linux-amd64.tar.gz'); t.extractall('dist'); t.close()" >nul 2>nul
)

echo.
echo [*] Construyendo imagen de compilacion Linux (arm64)...
docker build --platform linux/arm64 -f Dockerfile.linux_build -t j360more-builder:linux-arm64 .

if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir la imagen de Docker para arm64.
    exit /b 1
)

echo.
echo [*] Compilando binario ELF nativo de Linux arm64 dentro de Docker...
docker run --rm --platform linux/arm64 -v "%cd%:/workspace" -w /workspace j360more-builder:linux-arm64 bash build_linux.sh

if %errorlevel% neq 0 (
    echo [ERROR] Fallo en la compilacion de Linux arm64.
    exit /b 1
)

echo.
echo =======================================================
echo    COMPILACION LOCAL PARA LINUX COMPLETADA CON EXITO!
echo =======================================================
echo Archivos generados en dist/:
echo   - dist/j360More (amd64)
echo   - dist/j360More-v1.5.1-linux-amd64.tar.gz (incluye viiper-amd64)
echo   - dist/j360More-v1.5.1-linux-arm64.tar.gz (incluye viiper-arm64)
echo =======================================================
