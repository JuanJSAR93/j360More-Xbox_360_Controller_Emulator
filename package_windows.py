import os
import shutil
import zipfile

def package():
    dist_dir = "dist"
    exe_path = os.path.join(dist_dir, "j360More.exe")
    if not os.path.exists(exe_path):
        print(f"[!] No se encontro {exe_path}")
        return

    # 1. Preparar carpeta AMD64
    amd64_dir = os.path.join(dist_dir, "j360More-windows-amd64")
    if os.path.exists(amd64_dir):
        shutil.rmtree(amd64_dir)
    os.makedirs(os.path.join(amd64_dir, "bin"), exist_ok=True)
    shutil.copy2(exe_path, os.path.join(amd64_dir, "j360More.exe"))
    
    # Copiar DLL y EXEs de AMD64 quitando sufijo amd64
    for src_candidates, dst_name in [
        (["HIDMaestro.Core.amd64.dll", "HIDMaestro.Core.dll"], "HIDMaestro.Core.dll"),
        (["hidmaestro_host-amd64.exe", "hidmaestro_host.exe"], "hidmaestro_host.exe"),
        (["viiper-amd64.exe", "viiper_amd64.exe", "viiper.exe"], "viiper.exe"),
    ]:
        for sname in src_candidates:
            src = os.path.join("bin", sname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(amd64_dir, "bin", dst_name))
                break
    
    # 2. Preparar carpeta ARM64
    arm64_dir = os.path.join(dist_dir, "j360More-windows-arm64")
    if os.path.exists(arm64_dir):
        shutil.rmtree(arm64_dir)
    os.makedirs(os.path.join(arm64_dir, "bin"), exist_ok=True)
    shutil.copy2(exe_path, os.path.join(arm64_dir, "j360More.exe"))

    # Copiar DLL y EXEs de ARM64 quitando sufijo arm64
    for src_candidates, dst_name in [
        (["HIDMaestro.Core.arm64.dll", "HIDMaestro.Core.dll"], "HIDMaestro.Core.dll"),
        (["hidmaestro_host-arm64.exe", "hidmaestro_host.exe"], "hidmaestro_host.exe"),
        (["viiper_arm64.exe", "viiper-arm64.exe", "viiper.exe"], "viiper.exe"),
    ]:
        for sname in src_candidates:
            src = os.path.join("bin", sname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(arm64_dir, "bin", dst_name))
                break

    # 3. Crear ZIPs
    def make_zip(source_dir, zip_name):
        zip_path = os.path.join(dist_dir, zip_name)
        print(f"[*] Generando {zip_path}...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, source_dir)
                    zf.write(full_p, rel_p)
        print(f"[+] {zip_name} creado ({os.path.getsize(zip_path)} bytes)")

    ver = "1.6.0"
    try:
        import re
        with open("gui_app.py", "r", encoding="utf-8") as f:
            m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', f.read(), re.MULTILINE)
            if m:
                ver = m.group(1)
    except Exception:
        pass

    make_zip(amd64_dir, f"j360More-v{ver}-windows-amd64.zip")
    make_zip(arm64_dir, f"j360More-v{ver}-windows-arm64.zip")

    # 4. Crear paquete de plugins separado (j360More-v{ver}-plugins-support.zip)
    plugins_src = "plugins"
    if os.path.exists(plugins_src):
        plugins_zip_name = f"j360More-v{ver}-plugins-support.zip"
        plugins_zip_path = os.path.join(dist_dir, plugins_zip_name)
        print(f"[*] Generando {plugins_zip_path}...")
        with zipfile.ZipFile(plugins_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(plugins_src):
                dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__", "tests")]
                for f in files:
                    if f.endswith(".pyc") or f.endswith(".pyo"):
                        continue
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, ".")
                    zf.write(full_p, rel_p)
        print(f"[+] {plugins_zip_name} creado ({os.path.getsize(plugins_zip_path)} bytes)")

if __name__ == "__main__":
    package()
