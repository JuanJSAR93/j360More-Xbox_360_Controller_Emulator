#!/bin/bash
# =======================================================
#       COMPILADOR OFICIAL DE j360More PARA LINUX
# =======================================================

set -e

echo "======================================================="
echo "       COMPILADOR OFICIAL DE j360More (LINUX)          "
echo "======================================================="
echo ""

# 1. Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 no está instalado. Instálalo con:"
    echo "  sudo apt update && sudo apt install -y python3 python3-pip python3-tk"
    exit 1
fi

echo "[*] Python detectado: $(python3 --version)"

# 2. Verificar Tkinter
if ! python3 -c "import tkinter" &> /dev/null; then
    echo "[!] Advertencia: Tkinter no parece estar instalado. En distribuciones basadas en Debian/Ubuntu:"
    echo "    sudo apt install -y python3-tk"
fi

# 3. Instalar / actualizar dependencias
echo "[*] Instalando dependencias de Python..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

# 4. Detectar arquitectura de destino y binario de viiper correspondiente
RAW_ARCH=$(uname -m)
if [ "$RAW_ARCH" = "x86_64" ] || [ "$RAW_ARCH" = "amd64" ]; then
    PKG_ARCH="amd64"
    VIIPER_SRC="bin/viiper-amd64"
elif [ "$RAW_ARCH" = "aarch64" ] || [ "$RAW_ARCH" = "arm64" ]; then
    PKG_ARCH="arm64"
    VIIPER_SRC="bin/viiper-arm64"
else
    PKG_ARCH="$RAW_ARCH"
    VIIPER_SRC="bin/viiper"
fi

echo "[*] Arquitectura detectada: $RAW_ARCH -> Destino: $PKG_ARCH"
echo "[*] Binario VIIPER asignado: $VIIPER_SRC"

# 5. Limpiar carpetas temporales
echo "[*] Limpiando carpetas temporales..."
rm -rf /tmp/pybuild /tmp/pydist
mkdir -p /tmp/pybuild /tmp/pydist
mkdir -p dist

# 6. Compilar con PyInstaller en un solo binario dentro del contenedor
echo "[*] Compilando ejecutable nativo de Linux ($PKG_ARCH) con PyInstaller..."
pyinstaller --noconfirm --onefile --windowed --noupx \
    --workpath /tmp/pybuild \
    --distpath /tmp/pydist \
    --name "j360More" \
    --add-data "assets:assets" \
    --collect-all "resvg_py" \
    --collect-all "PIL" \
    --collect-all "qrcode" \
    gui_app.py

# 7. Preparar paquete final con bin/viiper integrado
echo "[*] Preparando paquete final en dist/..."
chmod +x /tmp/pydist/j360More

mkdir -p /tmp/pydist/bin
if [ -f "/workspace/$VIIPER_SRC" ]; then
    echo "[*] Copiando $VIIPER_SRC como bin/viiper ejecutable..."
    cp -f "/workspace/$VIIPER_SRC" /tmp/pydist/bin/viiper
    chmod +x /tmp/pydist/bin/viiper
elif [ -f "/workspace/bin/viiper" ]; then
    echo "[*] Copiando bin/viiper ejecutable..."
    cp -f "/workspace/bin/viiper" /tmp/pydist/bin/viiper
    chmod +x /tmp/pydist/bin/viiper
else
    echo "[!] Advertencia: No se encontro $VIIPER_SRC en el workspace."
fi

cd /tmp/pydist
echo "[*] Creando archivo comprimido j360More-v1.5.1-linux-${PKG_ARCH}.tar.gz..."
tar -czvf "/workspace/dist/j360More-v1.5.1-linux-${PKG_ARCH}.tar.gz" j360More bin/viiper
cp -f /tmp/pydist/j360More "/workspace/dist/j360More-${PKG_ARCH}" 2>/dev/null || true
if [ "$PKG_ARCH" = "amd64" ] || [ "$PKG_ARCH" = "x86_64" ]; then
    cp -f /tmp/pydist/j360More /workspace/dist/j360More 2>/dev/null || true
fi
cd /workspace

echo ""
echo "======================================================="
echo "  ¡COMPILACIÓN PARA LINUX ($PKG_ARCH) EXITOSA!         "
echo "======================================================="
echo "Binario ejecutable: dist/j360More-${PKG_ARCH}"
echo "Archivo comprimido: dist/j360More-v1.5.1-linux-${PKG_ARCH}.tar.gz"
echo "Contenido del tar:  j360More + bin/viiper ($PKG_ARCH)"
echo "======================================================="
