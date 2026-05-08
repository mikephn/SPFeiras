import json
from pathlib import Path

from flask import Flask, jsonify, render_template

app = Flask(__name__)
DATA_PATH = Path(__file__).parent / "feiras.json"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/feiras")
def api_feiras():
    if not DATA_PATH.exists():
        return jsonify({"error": "feiras.json not found — run: uv run python extract.py"}), 404
    with open(DATA_PATH, encoding="utf-8") as f:
        return jsonify(json.load(f))


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Local:   http://localhost:5000")
    print(f"Network: http://{local_ip}:5000  ← open this on your phone (same WiFi)")
    app.run(host="0.0.0.0", debug=False, port=5000)

