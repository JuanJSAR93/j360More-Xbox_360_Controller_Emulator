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

# 4. Limpiar compilaciones anteriores de Linux
echo "[*] Limpiando carpetas temporales..."
rm -rf build
mkdir -p dist
rm -f dist/j360More dist/*.tar.gz

# 5. Compilar con PyInstaller en un solo binario
echo "[*] Compilando ejecutable nativo de Linux (PyInstaller)..."
pyinstaller --noconfirm --onefile --windowed --noupx \
    --name "j360More" \
    --add-data "assets:assets" \
    --collect-all "resvg_py" \
    --collect-all "PIL" \
    --collect-all "qrcode" \
    gui_app.py

# 6. Preparar paquete final en dist/
echo "[*] Preparando paquete final en dist/..."
chmod +x dist/j360More
rm -f dist/config_mapping.json

# 7. Empaquetar tar.gz listo para distribuir (solo j360More nativo)
echo "[*] Creando archivo comprimido j360More-v1.5.0-linux-x86_64.tar.gz..."
cd dist
rm -f config_mapping.json
tar -czvf j360More-v1.5.0-linux-x86_64.tar.gz j360More
cd ..

echo ""
echo "======================================================="
echo "     ¡COMPILACIÓN PARA LINUX COMPLETADA CON ÉXITO!     "
echo "======================================================="
echo "Binario ejecutable: dist/j360More"
echo "Archivo comprimido: dist/j360More-v1.5.0-linux-x86_64.tar.gz"
echo ""
echo "Para ejecutar en Linux:"
echo "  ./dist/j360More"
echo "======================================================="
