#!/usr/bin/env python3
"""Local mock server for demonstrating health_check.py retry behavior."""

import argparse
import http.server
import json
import socketserver
import subprocess
import sys
import threading
from pathlib import Path


class FlakyHandler(http.server.BaseHTTPRequestHandler):
    failures_before_success = 2
    calls = 0

    def do_GET(self):
        type(self).calls += 1
        if self.path == "/not-found":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return

        if type(self).calls <= type(self).failures_before_success:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"temporary failure")
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="Run a local retry demo for health_check.py")
    parser.add_argument("--failures", type=int, default=2, help="HTTP 500 responses before success")
    parser.add_argument("--not-found", action="store_true", help="Demonstrate that HTTP 404 is not retried")
    args = parser.parse_args()

    FlakyHandler.failures_before_success = args.failures
    FlakyHandler.calls = 0

    with socketserver.TCPServer(("127.0.0.1", 0), FlakyHandler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        health_check = Path(__file__).with_name("health_check.py")
        path = "/not-found" if args.not_found else "/health"
        code = (
            "import json, tools.health_check as hc; "
            f"hc.SERVICES={{'demo':{{'host':'127.0.0.1','port':{port},'path':'{path}','timeout':1}}}}; "
            "hc.INFRASTRUCTURE={}; "
            "print(json.dumps(hc.run_health_checks(service='demo', json_output=True, retries=2, timeout_secs=1, backoff_secs=0), indent=2))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(health_check.parents[1]),
            text=True,
            capture_output=True,
            check=False,
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
