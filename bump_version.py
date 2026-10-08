#!/usr/bin/env python3
"""
bump_version.py - Actualizador automático de versiones para j360More.

Actualiza de manera consistente todos los archivos del proyecto donde se
encuentra registrada la versión:
  1. gui_app.py
  2. version_info.txt
  3. package_windows.py
  4. docs/index.html
  5. .github/workflows/build.yml
  6. build_windows.bat
  7. build_linux.sh
  8. build_linux.bat
  9. README.md
  10. README_es.md
"""

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_current_version() -> str:
    """Extrae la versión actual desde gui_app.py."""
    gui_path = os.path.join(BASE_DIR, "gui_app.py")
    with open(gui_path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not m:
        raise ValueError("No se pudo encontrar APP_VERSION en gui_app.py")
    return m.group(1)

def parse_semver(ver_str: str):
    """Parsea una versión semver como '1.6.0' en una tupla de enteros (major, minor, patch)."""
    clean = ver_str.strip().lstrip("v")
    parts = clean.split(".")
    if len(parts) < 2:
        raise ValueError(f"Formato de versión inválido: {ver_str}. Use 'X.Y' o 'X.Y.Z'.")
    major = int(parts[0])
    minor = int(parts[1])
    patch = int(parts[2]) if len(parts) > 2 else 0
    return major, minor, patch

def bump_file(rel_path: str, old_ver: str, new_ver: str, repl_func):
    """Modifica un archivo aplicando una función de reemplazo, preservando saltos de línea."""
    full_path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(full_path):
        print(f"  [-] Omitido (no existe): {rel_path}")
        return False

    with open(full_path, "rb") as f:
        raw_bytes = f.read()
    detected_newline = "\r\n" if b"\r\n" in raw_bytes else "\n"

    with open(full_path, "r", encoding="utf-8") as f:
        old_content = f.read()

    new_content = repl_func(old_content, old_ver, new_ver)
    if old_content == new_content:
        print(f"  [=] Sin cambios: {rel_path}")
        return False

    with open(full_path, "w", encoding="utf-8", newline=detected_newline) as f:
        f.write(new_content)
    print(f"  [+] Actualizado: {rel_path}")
    return True

def update_all_files(old_ver: str, new_ver: str):
    old_maj, old_min, old_pat = parse_semver(old_ver)
    new_maj, new_min, new_pat = parse_semver(new_ver)

    print(f"\n[*] Actualizando versión en todos los archivos: v{old_ver} -> v{new_ver}\n")

    # 1. gui_app.py
    def repl_gui(content, o, n):
        return re.sub(
            r'^(APP_VERSION\s*=\s*["\'])' + re.escape(o) + r'(["\'])',
            r'\g<1>' + n + r'\2',
            content,
            flags=re.MULTILINE
        )
    bump_file("gui_app.py", old_ver, new_ver, repl_gui)

    # 2. version_info.txt
    def repl_version_info(content, o, n):
        # filevers=(1, 6, 0, 0)
        c = re.sub(
            r'filevers=\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)',
            f'filevers=({new_maj}, {new_min}, {new_pat}, 0)',
            content
        )
        c = re.sub(
            r'prodvers=\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)',
            f'prodvers=({new_maj}, {new_min}, {new_pat}, 0)',
            c
        )
        c = re.sub(
            r"StringStruct\('FileVersion',\s*'[^']+'\)",
            f"StringStruct('FileVersion', '{new_maj}.{new_min}.{new_pat}.0')",
            c
        )
        c = re.sub(
            r"StringStruct\('ProductVersion',\s*'[^']+'\)",
            f"StringStruct('ProductVersion', '{new_maj}.{new_min}.{new_pat}.0')",
            c
        )
        return c
    bump_file("version_info.txt", old_ver, new_ver, repl_version_info)

    # 3. package_windows.py
    def repl_pkg_win(content, o, n):
        c = content.replace(f"j360More-v{o}-", f"j360More-v{n}-")
        return re.sub(r'ver\s*=\s*["\']' + re.escape(o) + r'["\']', f'ver = "{n}"', c)
    bump_file("package_windows.py", old_ver, new_ver, repl_pkg_win)

    # 4. docs/index.html
    def repl_docs(content, o, n):
        c = re.sub(
            r'("softwareVersion":\s*")[^"]+(")',
            r'\g<1>' + n + r'\2',
            content
        )
        c = re.sub(
            r'(<span class="window-title">j360More\s+v)[^<]+(</span>)',
            r'\g<1>' + n + r'\2',
            c
        )
        return c
    bump_file("docs/index.html", old_ver, new_ver, repl_docs)

    # 5. .github/workflows/build.yml
    def repl_build_yml(content, o, n):
        c = re.sub(
            r'(else\s*\{\s*"v)' + re.escape(o) + r'("\s*\})',
            r'\g<1>' + n + r'\2',
            content
        )
        c = re.sub(
            r'(APP_VER=")' + re.escape(o) + r'(")',
            r'\g<1>' + n + r'\2',
            c
        )
        return c
    bump_file(".github/workflows/build.yml", old_ver, new_ver, repl_build_yml)

    # 6. build_windows.bat
    def repl_build_win_bat(content, o, n):
        return content.replace(f"j360More-v{o}-", f"j360More-v{n}-")
    bump_file("build_windows.bat", old_ver, new_ver, repl_build_win_bat)

    # 7. build_linux.sh
    def repl_build_linux_sh(content, o, n):
        return content.replace(f"j360More-v{o}-", f"j360More-v{n}-")
    bump_file("build_linux.sh", old_ver, new_ver, repl_build_linux_sh)

    # 8. build_linux.bat
    def repl_build_linux_bat(content, o, n):
        return content.replace(f"j360More-v{o}-", f"j360More-v{n}-")
    bump_file("build_linux.bat", old_ver, new_ver, repl_build_linux_bat)

    # 9. README.md
    def repl_readme(content, o, n):
        return content.replace(f"j360More-v{o}-", f"j360More-v{n}-")
    bump_file("README.md", old_ver, new_ver, repl_readme)

    # 10. README_es.md
    def repl_readme_es(content, o, n):
        return content.replace(f"j360More-v{o}-", f"j360More-v{n}-")
    bump_file("README_es.md", old_ver, new_ver, repl_readme_es)

    print(f"\n[OK] ¡Versión actualizada exitosamente a v{new_ver} en todos los archivos!")

def main():
    old_ver = get_current_version()
    major, minor, patch = parse_semver(old_ver)

    suggested_patch = f"{major}.{minor}.{patch + 1}"
    suggested_minor = f"{major}.{minor + 1}.0"
    suggested_major = f"{major + 1}.0.0"

    new_ver = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower().lstrip("-")
        if arg in ("patch", "p"):
            new_ver = suggested_patch
        elif arg in ("minor", "m"):
            new_ver = suggested_minor
        elif arg in ("major", "maj"):
            new_ver = suggested_major
        elif arg in ("help", "h", "?"):
            print("Uso:")
            print("  python bump_version.py           (modo interactivo)")
            print("  python bump_version.py 1.7.0     (especificar version)")
            print("  python bump_version.py patch     (subir patch: 1.6.0 -> 1.6.1)")
            print("  python bump_version.py minor     (subir minor: 1.6.0 -> 1.7.0)")
            print("  python bump_version.py major     (subir major: 1.6.0 -> 2.0.0)")
            sys.exit(0)
        else:
            new_ver = sys.argv[1].strip().lstrip("v")
    else:
        print("=" * 60)
        print("          ACTUALIZADOR DE VERSIÓN - j360More")
        print("=" * 60)
        print(f"\nVersión actual del proyecto: v{old_ver}")
        print("\nOpciones de incremento:")
        print(f"  [1] Patch  -> v{suggested_patch} (corrección de errores / detalles)")
        print(f"  [2] Minor  -> v{suggested_minor} (nuevas funciones compatibles)")
        print(f"  [3] Major  -> v{suggested_major} (cambios grandes / incompatibles)")
        print(f"  [4] Manual -> Escribir versión personalizada")
        print()

        try:
            choice = input("Selecciona una opción (1-4) o escribe la nueva versión: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            sys.exit(0)

        if not choice:
            print("No se ingresó ninguna opción. Cancelando.")
            sys.exit(0)

        if choice == "1":
            new_ver = suggested_patch
        elif choice == "2":
            new_ver = suggested_minor
        elif choice == "3":
            new_ver = suggested_major
        elif choice == "4":
            custom = input("Escribe la nueva versión (ej. 1.7.0): ").strip().lstrip("v")
            if custom:
                new_ver = custom
            else:
                print("Versión vacía. Cancelando.")
                sys.exit(0)
        else:
            # Si escribió directamente una versión como '1.6.1'
            new_ver = choice.lstrip("v")

    # Validar formato
    try:
        parse_semver(new_ver)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if new_ver == old_ver:
        print(f"[!] La nueva versión (v{new_ver}) es idéntica a la actual (v{old_ver}). No hay cambios.")
        sys.exit(0)

    update_all_files(old_ver, new_ver)

if __name__ == "__main__":
    main()
