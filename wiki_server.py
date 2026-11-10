#!/usr/bin/env python3
"""Combo Dex site server: static files + the wiki database (SQLite)."""
from __future__ import annotations

import json
import sqlite3
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "combos.db"
HOST = "0.0.0.0"
PORT = 8788
_lock = threading.Lock()


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute(
        """CREATE TABLE IF NOT EXISTS combos (
            id TEXT PRIMARY KEY,
            game TEXT NOT NULL,
            character TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_combos_game_char ON combos(game, character)")
    con.commit()
    return con


CON = db()


def row_to_combo(payload: str) -> dict | None:
    try:
        c = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(c, dict) or not c.get("id"):
        return None
    c.pop("favorite", None)
    return c


def all_combos() -> list[dict]:
    with _lock:
        cur = CON.execute("SELECT payload FROM combos ORDER BY updated_at ASC")
        out = []
        for (payload,) in cur.fetchall():
            c = row_to_combo(payload)
            if c:
                out.append(c)
        return out


def upsert_many(rows) -> int:
    if not isinstance(rows, list):
        rows = [rows]
    n = 0
    with _lock:
        for c in rows:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or "").strip()
            game = str(c.get("game") or "").strip()
            char = str(c.get("character") or "").strip()
            if not cid or not game or not char:
                continue
            if not c.get("tokens") and not c.get("video"):
                continue
            body = dict(c)
            body.pop("favorite", None)
            CON.execute(
                """INSERT INTO combos(id, game, character, payload, updated_at)
                   VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(id) DO UPDATE SET
                     game=excluded.game,
                     character=excluded.character,
                     payload=excluded.payload,
                     updated_at=CURRENT_TIMESTAMP""",
                (cid, game, char, json.dumps(body, ensure_ascii=False)),
            )
            n += 1
        CON.commit()
    return n


def replace_all(rows) -> int:
    if not isinstance(rows, list):
        rows = []
    with _lock:
        CON.execute("DELETE FROM combos")
        CON.commit()
    return upsert_many(rows)


def delete_ids(ids) -> int:
    ids = [str(i) for i in ids if i]
    if not ids:
        return 0
    with _lock:
        CON.executemany("DELETE FROM combos WHERE id=?", [(i,) for i in ids])
        CON.commit()
    return len(ids)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _json(self, code: int, obj) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return None
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/wiki/combos", "/wiki/combos/"):
            self._json(200, {"combos": all_combos()})
            return
        if path in ("/", "/index.html"):
            self.path = "/Combo_Dex.html"
        super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/wiki/combos", "/wiki/combos/"):
            self.send_error(404)
            return
        body = self._read_json()
        rows = body.get("combos", body) if isinstance(body, dict) else body
        n = upsert_many(rows)
        self._json(200, {"ok": True, "saved": n, "combos": all_combos()})

    def do_PUT(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/wiki/combos", "/wiki/combos/"):
            self.send_error(404)
            return
        body = self._read_json()
        rows = body.get("combos", body) if isinstance(body, dict) else body
        n = replace_all(rows if isinstance(rows, list) else [])
        self._json(200, {"ok": True, "saved": n, "combos": all_combos()})

    def do_DELETE(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/wiki/combos/"):
            cid = path.rsplit("/", 1)[-1]
            delete_ids([cid])
            self._json(200, {"ok": True, "combos": all_combos()})
            return
        if path in ("/wiki/combos", "/wiki/combos/"):
            body = self._read_json() or {}
            ids = body.get("ids") if isinstance(body, dict) else body
            if not isinstance(ids, list):
                ids = []
            delete_ids(ids)
            self._json(200, {"ok": True, "combos": all_combos()})
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Combo Dex wiki on http://127.0.0.1:{PORT}/")
    httpd.serve_forever()
