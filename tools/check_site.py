"""Integrity check for ComboDex. No Node required. Fails before a broken page can ship."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\amand\Downloads\Combo_Dex")
errs: list[str] = []


def fail(msg):
    errs.append(msg)


def extract_balanced(src, start):
    if start >= len(src) or src[start] not in "{[":
        raise ValueError("no opener")
    opener, closer = ("{", "}") if src[start] == "{" else ("[", "]")
    depth = 0
    i = start
    in_str = None
    esc = False
    while i < len(src):
        c = src[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_str:
                in_str = None
        else:
            if c in "\"'`":
                in_str = c
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return src[start : i + 1], i + 1
        i += 1
    raise ValueError("unbalanced")


def json_assign(text, name):
    i = text.find(name + "=")
    if i < 0:
        raise ValueError(f"missing {name}")
    j = i + len(name) + 1
    while j < len(text) and text[j].isspace():
        j += 1
    obj, end = json.JSONDecoder().raw_decode(text, j)
    return obj, end


def main():
    index = ROOT / "index.html"
    app_p = ROOT / "cdx-app.js"
    i18n_p = ROOT / "cdx-i18n.js"
    por_p = ROOT / "cdx-portraits.js"
    ft_p = ROOT / "cdx-ft.js"
    css_p = ROOT / "cdx.css"
    needed = [index, app_p, i18n_p, por_p, ft_p, css_p]
    for p in needed:
        if not p.exists():
            fail(f"missing {p.name}")
    if errs:
        return

    html = index.read_text(encoding="utf-8")
    for src in ["cdx-i18n.js", "cdx-portraits.js", "cdx-ft.js", "cdx-app.js", "cdx.css"]:
        if src not in html:
            fail(f"index.html does not load {src}")

    twin = ROOT / "Combo_Dex.html"
    if twin.exists():
        a = index.read_bytes()
        b = twin.read_bytes()
        if a != b:
            fail("Combo_Dex.html diverges from index.html — copy or hardlink them")

    if "]},meter" in app_p.read_text(encoding="utf-8"):
        fail("cdx-app.js contains ]},meter (this emptied ComboDex once)")

    app = app_p.read_text(encoding="utf-8")
    ki = app.find("const ke=")
    if ki < 0:
        fail("const ke= missing")
    else:
        ke_start = app.find("{", ki)
        try:
            ke_src, after_ke = extract_balanced(app, ke_start)
        except ValueError as e:
            fail(f"ke braces: {e}")
            ke_src = ""
            after_ke = ke_start
        rest = app[after_ke:].lstrip()
        if not rest.startswith(",b=") and ",b=" not in app[after_ke : after_ke + 8]:
            fail("b= does not follow ke")
        bi = app.find("b=", after_ke)
        b_start = app.find("{", bi)
        try:
            b_src, _ = extract_balanced(app, b_start)
        except ValueError as e:
            fail(f"b braces: {e}")
            b_src = ""
        ke_keys = [a or b for a, b in re.findall(r'[{,](?:"([^"]+)"|([a-z0-9]+)):\[', ke_src)]
        b_keys = [a or b for a, b in re.findall(r'[{,](?:"([^"]+)"|([a-z0-9]+)):\{name:', b_src)]
        if set(ke_keys) != set(b_keys):
            fail(f"ke/b keys differ: extra ke {set(ke_keys)-set(b_keys)} extra b {set(b_keys)-set(ke_keys)}")
        if len(ke_keys) < 10:
            fail(f"too few games in ke: {ke_keys}")

    try:
        portraits, _ = json_assign(por_p.read_text(encoding="utf-8"), "window.CDX_PORTRAITS")
        if not isinstance(portraits, dict) or len(portraits) < 50:
            fail(f"CDX_PORTRAITS too small: {len(portraits) if isinstance(portraits, dict) else type(portraits)}")
    except Exception as e:
        fail(f"CDX_PORTRAITS JSON: {e}")
    try:
        logos, _ = json_assign(por_p.read_text(encoding="utf-8"), "window.CDX_LOGOS")
        if not isinstance(logos, dict) or "2xko" not in logos:
            fail("CDX_LOGOS missing 2xko")
    except Exception as e:
        fail(f"CDX_LOGOS JSON: {e}")
    try:
        xko, _ = json_assign(ft_p.read_text(encoding="utf-8"), "window.CDX_FT_2XKO")
        if not isinstance(xko, list) or len(xko) < 100:
            fail(f"CDX_FT_2XKO rows {len(xko) if isinstance(xko, list) else xko}")
    except Exception as e:
        fail(f"CDX_FT_2XKO JSON: {e}")
    try:
        ft, _ = json_assign(ft_p.read_text(encoding="utf-8"), "window.CDX_FT")
        if not isinstance(ft, dict) or "mkxl" not in ft or "t8" not in ft:
            fail("CDX_FT missing mkxl or t8")
        if len(ft.get("mkxl") or []) < 100:
            fail("CDX_FT.mkxl too small")
    except Exception as e:
        fail(f"CDX_FT JSON: {e}")

    i18n = i18n_p.read_text(encoding="utf-8")
    for lang in ("fr:{", "en:{", "es:{"):
        if lang not in i18n:
            fail(f"i18n missing {lang}")

    allowed = {
        "combo-dex-final-v1",
        "combo-dex-ui-v1",
        "cdx-pending",
        "cdx-lang",
        "cdx-ft-map",
    }
    for m in re.finditer(r'localStorage\.setItem\((["\'])([^"\']+)\1', app + i18n):
        key = m.group(2)
        if key in allowed or key.startswith("cdx-ft:"):
            continue
        fail(f"unexpected localStorage key {key}")

    if "CRÉÉ PAR VSQC" not in html:
        fail("footer signature missing")

    if errs:
        print("FAIL")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print("OK ComboDex integrity")
    print(f"  games {len(ke_keys)}  portraits {len(portraits)}  ft games {list(ft)}")


if __name__ == "__main__":
    main()
