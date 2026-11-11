"""Check ComboDex, then copy the site folder to the public Pages clone."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\amand\Downloads\Combo_Dex")
LIVE = Path(r"C:\Users\amand\AppData\Local\Temp\ComboDex_live")
FILES = [
    "index.html",
    "cdx-i18n.js",
    "cdx-portraits.js",
    "cdx-ft.js",
    "cdx-app.js",
    "cdx-kc-data.js",
    "cdx-kc-infil.js",
    "cdx-kc.js",
    "cdx.css",
    "img/akali-5m-hitbox.png",
]


def main():
    check = subprocess.run([sys.executable, str(ROOT / "tools" / "check_site.py")], cwd=ROOT)
    if check.returncode:
        sys.exit(check.returncode)
    if not LIVE.exists():
        print("no Pages clone at", LIVE)
        sys.exit(1)
    for name in FILES:
        src = ROOT / name
        if not src.exists():
            print("missing", name)
            sys.exit(1)
        dst = LIVE / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print("copied", name)
    for folder in ["portraits/MKXL", "portraits/GBVSR", "portraits/BBCF", "portraits/SF4", "portraits/MvC2", "pad"]:
        src = ROOT / folder
        dst = LIVE / folder
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print("copied", folder)
    print("OK shipped to Pages clone (commit/push separately)")


if __name__ == "__main__":
    main()
