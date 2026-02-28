"""
Fundas Friends Survivor 50 — API
Serves survivor_data.json to the frontend page.
Hosted on Render.com free tier.
"""

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


# ── DATA ─────────────────────────────────────────────────────────────────────

DATA_FILE = os.path.join(os.path.dirname(__file__), "survivor_data.json")

DEFAULT_DATA = {
    "episode": 0,
    "eliminated": [],
    "milestones": {},
    "last_updated": None,
    "scrape_status": "no_data"
}


def load_data():
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_DATA


# ── HTTP SERVER ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suppress default access logs (Render shows them anyway)
        pass

    def send_cors_headers(self):
        # Allow any website (including your Netlify page) to call this API
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        # ── Health check ──────────────────────────────────────────────────
        if path in ("", "/", "/health"):
            body = json.dumps({
                "status": "ok",
                "service": "Fundas Friends Survivor 50 API",
                "time": datetime.now(timezone.utc).isoformat()
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        # ── Main data endpoint ────────────────────────────────────────────
        if path == "/data":
            data = load_data()
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            # Cache for 1 hour (scraper runs nightly anyway)
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(body)
            print(f"[{datetime.now()}] /data served — "
                  f"ep {data.get('episode',0)}, "
                  f"{len(data.get('eliminated',[]))} eliminated")
            return

        # ── 404 ───────────────────────────────────────────────────────────
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "not found"}).encode())


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Fundas Friends API running on port {port}")
    print(f"Data file: {DATA_FILE}")

    # Run the scraper once on startup to ensure data is fresh
    try:
        from scraper import main as run_scraper
        print("Running initial scrape on startup...")
        run_scraper()
    except Exception as e:
        print(f"Startup scrape failed (non-fatal): {e}")

    server.serve_forever()
