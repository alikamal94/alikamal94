"""Optional persistence backend for the ICT Adaptive Scalper (standard library only).

TradingView alert() messages (JSON) are POSTed here, stored in SQLite, and turned into
rolling statistics that survive chart reloads - something Pine Script cannot do.

    python webhook_server.py --db trades.sqlite --port 8080 --token CHANGE_ME

Endpoints
    POST /tv?token=...   body = the JSON sent by the script's alert() calls
    GET  /stats?token=...   rolling 10/20/30/50-trade statistics and a suggested adaptive level

TradingView webhooks require a public HTTPS URL on port 443 (or 80): put this behind a reverse
proxy such as Caddy or nginx. Never expose it without the token.
"""
import argparse, json, sqlite3, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, received_at REAL NOT NULL, event TEXT NOT NULL,
    symbol TEXT, bar_time INTEGER, payload TEXT NOT NULL,
    UNIQUE(event, symbol, bar_time) ON CONFLICT IGNORE);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, direction TEXT, signal_time INTEGER,
    entry REAL, stop_loss REAL, take_profit REAL, score REAL, session TEXT, liquidity TEXT,
    adaptive_level INTEGER, exit_time INTEGER, exit_reason TEXT, result_r REAL);
"""


def store(db, msg):
    """Idempotent: a re-sent alert with the same (event, symbol, bar time) is ignored."""
    ev = msg.get("event", "?")
    cur = db.execute("INSERT INTO events(received_at,event,symbol,bar_time,payload) VALUES(?,?,?,?,?)",
                     (time.time(), ev, msg.get("symbol"), msg.get("time"), json.dumps(msg)))
    if cur.rowcount == 0:
        return "duplicate"
    if ev in ("BUY", "SELL"):
        db.execute("INSERT INTO trades(symbol,direction,signal_time,entry,stop_loss,take_profit,score,"
                   "session,liquidity,adaptive_level) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (msg.get("symbol"), msg.get("direction"), msg.get("time"), msg.get("entry"),
                    msg.get("stop_loss"), msg.get("take_profit"), msg.get("score"), msg.get("session"),
                    msg.get("liquidity"), msg.get("adaptive_level")))
    elif ev == "EXIT":
        row = db.execute("SELECT id FROM trades WHERE symbol=? AND result_r IS NULL ORDER BY id DESC LIMIT 1",
                         (msg.get("symbol"),)).fetchone()
        if row:
            db.execute("UPDATE trades SET exit_time=?, exit_reason=?, result_r=? WHERE id=?",
                       (msg.get("time"), msg.get("reason"), msg.get("result_r"), row[0]))
    db.commit()
    return "stored"


def rolling(rs, n):
    w = rs[-n:]
    if not w:
        return None
    gp = sum(r for r in w if r > 0); gl = -sum(r for r in w if r <= 0)
    return dict(trades=len(w), win_rate=round(100 * sum(r > 0 for r in w) / len(w), 1),
                profit_factor=round(gp / gl, 2) if gl > 0 else None, expectancy_r=round(sum(w) / len(w), 3))


def stats(db, min_sample=20, window=20, tighten=0.0, relax=0.25, step=1, max_level=4, cooldown=5):
    """Replays the same deterministic level rule the Pine script uses, over the WHOLE stored history."""
    rs = [r[0] for r in db.execute("SELECT result_r FROM trades WHERE result_r IS NOT NULL ORDER BY id")]
    level, last = 0, 0
    for i in range(1, len(rs) + 1):
        if i < min_sample or i - last < cooldown:
            continue
        w = rs[max(0, i - window):i]; ex = sum(w) / len(w)
        if ex < tighten and level < max_level:
            level, last = level + step, i
        elif ex > relax and level > 0:
            level, last = level - step, i
    return dict(completed_trades=len(rs), suggested_adaptive_level=level,
                windows={str(n): rolling(rs, n) for n in (10, 20, 30, 50)})


def make_handler(db, token):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def _auth(self):
            return parse_qs(urlparse(self.path).query).get("token", [""])[0] == token

        def do_POST(self):
            if urlparse(self.path).path != "/tv" or not self._auth():
                return self._send(403, {"error": "forbidden"})
            try:
                n = min(int(self.headers.get("Content-Length", 0)), 65536)
                msg = json.loads(self.rfile.read(n))
                assert isinstance(msg, dict)
            except Exception:
                return self._send(400, {"error": "body must be a JSON object"})
            self._send(200, {"status": store(db, msg)})

        def do_GET(self):
            if urlparse(self.path).path != "/stats" or not self._auth():
                return self._send(403, {"error": "forbidden"})
            self._send(200, stats(db))

        def log_message(self, *a):
            pass
    return H


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="trades.sqlite"); ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--token", required=True)
    a = ap.parse_args()
    conn = sqlite3.connect(a.db, check_same_thread=False)
    conn.executescript(SCHEMA)
    print(f"listening on {a.host}:{a.port}")
    ThreadingHTTPServer((a.host, a.port), make_handler(conn, a.token)).serve_forever()
