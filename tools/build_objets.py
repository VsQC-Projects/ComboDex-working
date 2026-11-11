"""objets/<game>.txt + objets/<game>/<id>.webp  ->  cdx-objets.js (window.CDX_OBJETS)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
data, report = {}, []
for txt in sorted((ROOT / "objets").glob("*.txt")):
    game, rows, seen = txt.stem, [], set()
    for line in txt.read_text(encoding="utf-8-sig").splitlines():
        p = [x.strip() for x in line.split("|")]
        if len(p) < 7 or not p[0] or p[0] in seen:
            continue
        d = ROOT / "objets" / game
        if not (d / f"{p[0]}.webp").exists() and not (d / f"{p[0]}-1.webp").exists():
            continue
        seen.add(p[0])
        n = 0
        while (d / f"{p[0]}-{n + 1}.webp").exists():
            n += 1
        rows.append(p[:7] + ([n] if n else []))
    if rows:
        data[game] = rows
    report.append(f"{game}:{len(rows)}")
js = "window.CDX_OBJETS=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
(ROOT / "cdx-objets.js").write_text(js, encoding="utf-8")
print(" ".join(report), "| total", sum(len(v) for v in data.values()))
