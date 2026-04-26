#!/usr/bin/env python3
"""殖民火星 — Web 服务器（Flask）

启动：
    python3 server.py            # 默认 http://localhost:5180
    python3 server.py --port 8000

打开浏览器访问 http://localhost:5180 即可游玩。
"""
from __future__ import annotations
import argparse
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

from game.web_session import WebSession


ROOT = Path(__file__).parent
app = Flask(__name__,
            static_folder=str(ROOT / "static"),
            static_url_path="/static")

# 单进程单局（足够个人游玩）
_session: WebSession | None = None


@app.route("/")
def index():
    return send_from_directory(str(ROOT / "static"), "index.html")


@app.post("/api/new_game")
def new_game():
    global _session
    body = request.get_json(force=True, silent=True) or {}
    n_players = int(body.get("players", 4))
    n_players = max(2, min(5, n_players))
    seed = body.get("seed")
    if seed is not None:
        seed = int(seed)
    human_idx = int(body.get("human_idx", 0))
    human_indices = [human_idx] if 0 <= human_idx < n_players else []
    dlcs = body.get("dlcs", [])
    _session = WebSession(n_players=n_players,
                          human_indices=human_indices,
                          seed=seed,
                          dlcs=dlcs)
    _session.start()
    return jsonify({"ok": True, "players": n_players, "seed": seed, "dlcs": dlcs})


@app.get("/api/dlc_save")
def dlc_save():
    """读取 DLC II 存档（解锁状态、章节进度）"""
    from game.dlc.parallel import load_save, FACTIONS, CHAPTERS
    save = load_save()
    return jsonify({
        "save": save,
        "factions": [
            {"key": f.key, "name": f.name, "description": f.description,
             "color": f.color, "quote": f.quote,
             "unlocked": f.key in save["factions_unlocked"]}
            for f in FACTIONS
        ],
        "chapters": [
            {"num": c.num, "name": c.name, "faction": c.faction,
             "intro": c.intro, "target": c.target_text,
             "completed": c.num in save["chapters_completed"]}
            for c in CHAPTERS
        ],
    })


@app.get("/api/state")
def get_state():
    if _session is None:
        return jsonify({"started": False})
    full = request.args.get("full") == "1"
    snap = _session.full_snapshot() if full else _session.snapshot()
    return jsonify(snap)


@app.post("/api/submit")
def submit():
    if _session is None:
        return jsonify({"ok": False, "error": "no game"}), 400
    body = request.get_json(force=True, silent=True) or {}
    ok = _session.submit(body)
    return jsonify({"ok": ok})


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5180)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    print(f"╔════════════════════════════════════════════════╗")
    print(f"║  🚀 殖民火星 — Web Server                      ║")
    print(f"║  📡 http://{args.host}:{args.port}                       ║")
    print(f"║  按 Ctrl+C 停止                                ║")
    print(f"╚════════════════════════════════════════════════╝")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
