#!/usr/bin/env python3
"""HTTP Webhook server for receiving Telegram ad channel updates.

When an ad schedule is posted to the ads channel, Telegram posts an update to this webhook.
The server records the message in `memory/ads-inbox.json` and immediately re-plans the slot
via `scripts/pipeline.py gate`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.channels import messages_from_updates, read_inbox, save_inbox  # noqa: E402
from newsagent.runtime import iso, load_dotenv, repo_root  # noqa: E402


def trigger_preflight() -> str | None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pipeline.py"), "gate"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 1:
        print(f"[ADS WEBHOOK] gate error: {proc.stdout.strip() or proc.stderr.strip()}", file=sys.stderr)
        return None
    return proc.stdout.strip()


class AdsWebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "service": "ads-webhook"}\n')
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        load_dotenv()
        channel = os.environ.get("ADS_CHANNEL", "").strip()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            payload = {}

        # Handle direct trigger endpoint: POST /trigger
        if self.path == "/trigger":
            run_id = trigger_preflight()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "triggered", "run_id": run_id}).encode())
            return

        # Telegram webhook update
        fresh, _ = messages_from_updates(payload if "result" in payload else {"result": [payload]}, channel)

        if not fresh and "channel_post" in payload:
            post = payload["channel_post"]
            text = post.get("text") or post.get("caption") or ""
            if text and "date" in post:
                dt = datetime.fromtimestamp(int(post["date"]), tz=timezone.utc)
                fresh = [{"text": text, "message_at": dt, "message_id": post.get("message_id")}]

        if fresh:
            known = {item.get("message_id"): item for item in read_inbox()}
            for item in fresh:
                known[item.get("message_id")] = {
                    "text": item["text"],
                    "message_at": iso(item["message_at"]),
                    "message_id": item.get("message_id"),
                }
            save_inbox(list(known.values()))
            print(f"[ADS WEBHOOK] Received new ad message from channel. Triggering run...", flush=True)
            run_id = trigger_preflight()
            print(f"[ADS WEBHOOK] Triggered preflight run: {run_id}", flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}\n')

    def log_message(self, format, *args):
        # Concise logging
        sys.stderr.write(f"[ADS WEBHOOK] {args[0]} - {args[1]} {args[2]}\n")


def main() -> int:
    load_dotenv()
    port = int(os.environ.get("WEBHOOK_PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AdsWebhookHandler)
    print(f"[ADS WEBHOOK] Server running on port {port}...", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[ADS WEBHOOK] Stopping server...", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
