"""Build cdx-theme.css from cdx.css: theme variables + per-theme overrides of hard-coded colors.

Themes (html[data-theme=...]): official (default, purple -> gold), wood and dojo (light surfaces).
Run:  python tools/gen_theme_css.py
"""
import colorsys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "cdx.css").read_text(encoding="utf-8")
src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)

HEX = re.compile(r"#([0-9a-fA-F]{3,8})\b")
COLOR_PROPS = ("color", "background", "background-color", "border", "border-color", "border-top", "border-bottom",
               "border-left", "border-right", "border-top-color", "border-bottom-color", "border-left-color",
               "border-right-color", "outline", "outline-color", "box-shadow", "text-shadow", "fill", "stroke",
               "accent-color", "caret-color", "text-decoration-color")


def parse_hex(h):
    h = h.lower()
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    a = h[6:8] if len(h) == 8 else ""
    return r, g, b, a


def to_hex(r, g, b, a=""):
    return "#" + "".join(f"{max(0, min(255, round(v * 255))):02x}" for v in (r, g, b)) + a


def lum(r, g, b):
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def map_light(hexv, prop, theme):
    r, g, b, a = parse_hex(hexv)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if 0.66 <= h <= 0.88 and s > 0.12:
        h = 0.07 if theme == "wood" else 0.02
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        if prop not in ("color", "fill") and lum(r, g, b) >= 0.2 and not prop.startswith(("border", "outline")):
            return to_hex(r, g, b, a)
    L = lum(r, g, b)
    warm = theme == "wood"
    if prop in ("color", "fill", "caret-color", "text-decoration-color"):
        if L > 0.18:
            if s < 0.2:
                if warm:
                    h, s = 0.08, 0.35
                return to_hex(*colorsys.hls_to_rgb(h, 0.16, s), a)
            return to_hex(*colorsys.hls_to_rgb(h, 0.3, max(s, 0.85)), a)
        return None
    if prop in ("text-shadow",):
        return "#0000"
    if prop.startswith("border") or prop.startswith("outline"):
        if L < 0.2:
            if theme == "dojo":
                return to_hex(0.11, 0.11, 0.13, a)
            return to_hex(*colorsys.hls_to_rgb(0.08 if s < 0.2 else h, 0.55, 0.32 if s < 0.2 else s), a)
        if L > 0.5 and s > 0.2:
            return to_hex(*colorsys.hls_to_rgb(h, 0.38, max(s, 0.8)), a)
        return None
    if prop == "box-shadow":
        return None
    # backgrounds
    if L < 0.2:
        if s < 0.2:
            base = (0.95, 0.9, 0.81) if warm else (1, 1, 1)
            if l > 0.12:
                base = (0.91, 0.85, 0.74) if warm else (0.95, 0.94, 0.92)
            return to_hex(*base, a)
        return to_hex(*colorsys.hls_to_rgb(h, 0.87, max(s, 0.75)), a)
    return None


def map_official(hexv, prop):
    r, g, b, a = parse_hex(hexv)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if 0.69 <= h <= 0.86 and s > 0.15:
        return to_hex(*colorsys.hls_to_rgb(0.115, l, min(s, 0.7)), a)
    return None


def split_rules(css):
    """Yield (media, selector, body) for plain rules, one level of @media supported."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        head = css[i:j].strip()
        if head.startswith("@media") or head.startswith("@supports"):
            depth, k = 1, j + 1
            while depth and k < n:
                depth += {"{": 1, "}": -1}.get(css[k], 0)
                k += 1
            inner = css[j + 1:k - 1]
            for _, sel, body in split_rules(inner):
                yield head, sel, body
            i = k
            continue
        if head.startswith("@"):
            depth, k = 1, j + 1
            while depth and k < n:
                depth += {"{": 1, "}": -1}.get(css[k], 0)
                k += 1
            i = k
            continue
        k = css.find("}", j)
        yield None, head, css[j + 1:k]
        i = k + 1


def scope(sel, theme):
    out = []
    for part in sel.split(","):
        p = part.strip()
        if not p:
            continue
        pre = f'html[data-theme="{theme}"]'
        if p.startswith(":root") or p == "html":
            out.append(pre + p.replace(":root", "").replace("html", "", 1))
        elif p.startswith("html"):
            out.append(pre + p[4:])
        else:
            out.append(pre + " " + p)
    return ",".join(out)


KEEP = re.compile(r"\.token|\.palette|\.numpad|save-combo|\.train-seq|\.tok-")
HOVER = {"dojo": (0xd9 / 255, 0x41 / 255, 0x2b / 255), "wood": (0x12 / 255, 0x0c / 255, 0x07 / 255)}


def overrides(theme):
    blocks = {}
    for media, sel, body in split_rules(src):
        if ":root" in sel and "--" in body:
            continue
        hover = theme in HOVER and (":hover" in sel or ":focus-visible" in sel)
        if theme != "official" and KEEP.search(sel) and not hover:
            continue
        decls = []
        if hover:
            for d in body.split(";"):
                if ":" not in d:
                    continue
                prop, val = d.split(":", 1)
                prop = prop.strip().lower()
                if prop.startswith(("border", "outline")) or prop == "box-shadow":
                    val = HEX.sub(lambda m: to_hex(*HOVER[theme], parse_hex(m.group(1))[3]), val)
                    val = re.sub(r"var\(--(purple|accent)[^)]*\)", to_hex(*HOVER[theme]), val)
                    if val.strip() != d.split(":", 1)[1].strip():
                        decls.append(f"{prop}:{val.strip()}")
            if decls:
                blocks.setdefault(media, []).append(f"{scope(sel, theme)}{{{';'.join(decls)}}}")
            if KEEP.search(sel):
                continue
            decls = []
        for d in body.split(";"):
            if ":" not in d:
                continue
            prop, val = d.split(":", 1)
            prop = prop.strip().lower()
            if prop not in COLOR_PROPS or not HEX.search(val):
                continue
            if hover and (prop.startswith(("border", "outline")) or prop == "box-shadow"):
                continue
            changed = False

            def rep(m):
                nonlocal changed
                v = map_official(m.group(1), prop) if theme == "official" else map_light(m.group(1), prop, theme)
                if v:
                    changed = True
                    return v
                return m.group(0)

            nv = HEX.sub(rep, val)
            if changed:
                decls.append(f"{prop}:{nv.strip()}")
        if any(d.startswith("background:") for d in decls):
            for d in body.split(";"):
                p = d.split(":", 1)[0].strip().lower()
                if p.startswith(("background-", "-webkit-background-")) and ":" in d:
                    decls.append(d.strip())
        if decls:
            blocks.setdefault(media, []).append(f"{scope(sel, theme)}{{{';'.join(decls)}}}")
    out = []
    for media, rules in blocks.items():
        body = "\n".join(rules)
        out.append(f"{media}{{\n{body}\n}}" if media else body)
    return "\n".join(out)


VARS = """
html[data-theme="official"]{--purple:#e8c77a;--purple2:#4a3f26;--accent:#e8c77a}
html[data-theme="official"] a{color:#e8c77a}
html[data-theme="wood"]{color-scheme:light;--bg:#b98a57;--panel:#f6ead3;--panel2:#ead8b6;--line:#a8865c;--ink:#2a1d12;--muted:#5a4129;--purple:#8a4b1c;--purple2:#e2c290;--good:#2f7a4f;--bad:#a8322a;--warn:#8a5a00;--accent:#8a4b1c}
html[data-theme="dojo"]{color-scheme:light;--bg:#e9e5dc;--panel:#ffffff;--panel2:#f3f0ea;--line:#1d1d22;--ink:#1d1d22;--muted:#55545c;--purple:#d9412b;--purple2:#fbe3dd;--good:#1f7a4a;--bad:#c2291b;--warn:#8a5a00;--accent:#d9412b}
html[data-theme="wood"] body{background:repeating-linear-gradient(91deg,#0000 0 22px,#0000000f 22px 24px,#0000 24px 61px,#ffffff12 61px 63px),repeating-linear-gradient(90deg,#0000 0 180px,#00000010 180px 182px),linear-gradient(180deg,#c49464,#a9784a) fixed;background-color:#b98a57}
html[data-theme="dojo"] body{background-color:#e9e5dc;background-image:linear-gradient(#1d1d2214 1px,#0000 1px),linear-gradient(90deg,#1d1d2214 1px,#0000 1px);background-size:40px 40px}
html[data-theme="wood"] .panel,html[data-theme="wood"] .home-tile{box-shadow:0 6px 14px #3b261455}
html[data-theme="dojo"] .panel,html[data-theme="dojo"] .home-tile{border-width:2px;box-shadow:4px 4px 0 #1d1d22}
html[data-theme="dojo"] .tab{border:2px solid #1d1d22;background:#fff}
html[data-theme="dojo"] .tab.active{background:#1d1d22;color:#fff;border-color:#1d1d22}
html[data-theme="wood"] .tab{background:#f3e6cfe6;box-shadow:0 2px 0 #3b261466}
html[data-theme="wood"] .tab.active{background:#2a1d12;color:#f3e6cf;border-color:#2a1d12}
html[data-theme="dojo"] .brand-btn{background:#1d1d22;color:#e9e5dc;padding:2px 10px}
html[data-theme="wood"] .brand-btn{color:#2a1d12}
html[data-theme="wood"] .brand-word{background:linear-gradient(90deg,#4a2a10,#8a4b1c);-webkit-background-clip:text;background-clip:text;color:transparent}
html[data-theme="wood"] .brand-mark{color:#8a4b1c}
html[data-theme="dojo"] .brand-word{background:none;color:#e9e5dc;-webkit-text-fill-color:#e9e5dc}
html[data-theme="dojo"] .brand-mark{color:#d9412b}
html[data-theme="official"] .brand-word{background:linear-gradient(90deg,#f3dc9c,#e8c77a);-webkit-background-clip:text;background-clip:text;color:transparent}
html[data-theme="wood"] .lang-switch button[aria-pressed=true]{background:#2a1d12;border-color:#2a1d12;color:#f3e6cf}
html[data-theme="dojo"] .lang-switch button[aria-pressed=true]{background:#d9412b;border-color:#d9412b;color:#fff}
html[data-theme="official"] .lang-switch button[aria-pressed=true]{background:linear-gradient(135deg,#a8873f,#7a6230);border-color:#e8c77a;color:#fff}
html[data-theme="wood"] .nav{background:#3b2614d9;border-color:#2a1d12}
html[data-theme="dojo"] .nav{background:#e9e5dcf0;border:2px solid #1d1d22;border-radius:0}
html[data-theme="wood"] input,html[data-theme="wood"] select,html[data-theme="wood"] textarea{background:#fffaf0;color:#2a1d12}
html[data-theme="dojo"] input,html[data-theme="dojo"] select,html[data-theme="dojo"] textarea{background:#fff;color:#1d1d22;border:2px solid #1d1d22}
html[data-theme="wood"] button.primary,html[data-theme="dojo"] button.primary{color:var(--ink)}
html[data-theme="official"] .home-tile:not(.home-kc):hover,html[data-theme="official"] .home-tile:not(.home-kc):focus-visible{border-color:#e8c77a;box-shadow:0 0 0 1px #e8c77a,0 0 14px #e8c77a66,0 0 32px #e8c77a33,inset 0 0 14px #e8c77a1f}
html[data-theme="dojo"] .home-tile:not(.home-kc):hover,html[data-theme="dojo"] .home-tile:not(.home-kc):focus-visible{border-color:#d9412b;box-shadow:0 0 0 2px #d9412b,4px 4px 0 #d9412b}
html[data-theme="wood"] .home-tile:not(.home-kc):hover,html[data-theme="wood"] .home-tile:not(.home-kc):focus-visible{border-color:#120c07;box-shadow:0 0 0 2px #120c07,0 6px 14px #3b261455}
html[data-theme="wood"] .token,html[data-theme="dojo"] .token{color:#f5f3f8}
html[data-theme="wood"] .token.mod,html[data-theme="dojo"] .token.mod{color:var(--muted)}
html[data-theme="dojo"] :is(select,input,textarea,summary):hover{border-color:#d9412b}
html[data-theme="wood"] :is(select,input,textarea,summary):hover{border-color:#120c07}
html[data-theme="dojo"] button:hover,html[data-theme="dojo"] .tab:hover{border-color:#d9412b}
html[data-theme="wood"] button:hover,html[data-theme="wood"] .tab:hover{border-color:#120c07}
.da-switch{position:fixed;right:12px;bottom:12px;z-index:30;display:flex;gap:4px;padding:5px;border-radius:11px;background:#000000b3;backdrop-filter:blur(4px)}
.da-switch button{padding:6px 10px;font:700 12px system-ui,sans-serif;border-radius:8px;border:1px solid #ffffff38;background:transparent;color:#fff}
.da-switch button[aria-pressed="true"]{background:#fff;color:#111;border-color:#fff}
html[data-theme="dojo"] .da-switch{background:#1d1d22}
html[data-theme="dojo"] .da-switch button[aria-pressed="true"]{background:#d9412b;border-color:#d9412b;color:#fff}
html[data-theme="wood"] .da-switch{background:#2a1d12d9}
body{position:relative}
.cdx-refs{position:absolute;inset:0;z-index:2;pointer-events:none;overflow:hidden}
.cdx-ref{position:absolute;object-fit:contain;pointer-events:auto;transform:rotate(var(--rot,0deg));transition:transform .18s,opacity .18s,filter .18s;user-select:none;-webkit-user-drag:none}
.cdx-ref:hover{transform:rotate(var(--rot,0deg)) scale(1.18)}
html[data-theme="official"] .cdx-ref{opacity:.5;filter:grayscale(.35)}
html[data-theme="official"] .cdx-ref:hover,html.cdx-hunting[data-theme="official"] .cdx-ref{opacity:1;filter:none}
html[data-theme="wood"] .cdx-ref{filter:drop-shadow(0 6px 5px #3b2614a0)}
html[data-theme="dojo"] .cdx-ref{filter:drop-shadow(3px 3px 0 #1d1d2240)}
.cdx-hunting .cdx-ref{cursor:pointer}
.cdx-ref.hunt-win{opacity:1!important;filter:drop-shadow(0 0 10px #ffd34d) drop-shadow(0 0 22px #ffd34d)!important;animation:huntWin .9s ease-in-out 3}
.cdx-ref.hunt-got{opacity:1!important;filter:drop-shadow(0 0 6px #ffd34d) drop-shadow(0 0 12px #ffd34d)!important}
.cdx-hunt .hunt-prog{font-size:13px}
.cdx-ref.hunt-reveal{opacity:1!important;filter:drop-shadow(0 0 6px #ff3b30) drop-shadow(0 0 16px #ff3b30)!important;outline:3px solid #ff3b30;outline-offset:6px;border-radius:50%;animation:huntReveal 1s ease-in-out infinite}
@keyframes huntReveal{50%{transform:rotate(0) scale(1.45)}}
.cdx-ref.hunt-shake{animation:huntShake .35s}
@keyframes huntWin{50%{transform:rotate(0) scale(1.6)}}
@keyframes huntShake{25%{translate:-5px 0}75%{translate:5px 0}}
.brand-btn{-webkit-touch-callout:none;user-select:none;position:relative}
.brand-btn.brand-charging::after{content:"";position:absolute;left:0;bottom:-3px;height:3px;width:100%;background:var(--accent,#e8c77a);transform-origin:left;animation:brandCharge 5s linear forwards;border-radius:2px}
@keyframes brandCharge{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.cdx-hunt{position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:45;width:min(460px,calc(100% - 24px));padding:12px 14px;border-radius:14px;background:var(--panel);color:var(--ink);border:2px solid var(--accent,#e8c77a);box-shadow:0 12px 30px #0008;display:grid;gap:6px;animation:huntIn .35s ease-out}
.cdx-hunt .hunt-top{display:flex;justify-content:space-between;gap:10px;align-items:center}
.cdx-hunt .hunt-time{font-variant-numeric:tabular-nums;font-size:12px;color:var(--muted)}
.cdx-hunt .hunt-hint{font-size:16px;font-weight:700;line-height:1.3}
.cdx-hunt .hunt-miss{color:var(--bad);font-weight:650;font-size:13px}
.cdx-hunt .hunt-found{display:flex;gap:12px;align-items:center}
.cdx-hunt .hunt-found img{width:64px;height:64px;object-fit:contain}
.cdx-hunt .hunt-btns{display:flex;justify-content:flex-end;gap:6px}
@keyframes huntIn{from{opacity:0;transform:translate(-50%,-16px)}}
@media (prefers-reduced-motion:reduce){.cdx-ref,.cdx-hunt,.cdx-ref.hunt-win{animation:none;transition:none}}
"""

out = ["/* generated by tools/gen_theme_css.py from cdx.css */"]
for t in ("official", "wood", "dojo"):
    out.append(f"/* {t} */")
    out.append(overrides(t))
out.append(VARS.strip())
(ROOT / "cdx-theme.css").write_text("\n".join(out) + "\n", encoding="utf-8")
print("cdx-theme.css", sum(len(x) for x in out), "chars")
