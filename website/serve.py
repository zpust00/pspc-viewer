#!/usr/bin/env python3
"""
serve.py — local HTTP server for the PSPC Viewer website.

Usage:
    python website/serve.py          # http://localhost:8080
    python website/serve.py 9000     # custom port

Routes:
    /                         → website/index.html
    /download/PSPCViewer.exe  → dist/PSPCViewer.exe  (download)
    /pictures/<name>          → pictures/<name>       (images)
"""
import http.server
import os
import sys
import mimetypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

ROUTES = {
    "/":                        os.path.join(HERE, "index.html"),
    "/index.html":              os.path.join(HERE, "index.html"),
    "/download/PSPCViewer.exe": os.path.join(ROOT, "dist", "PSPCViewer.exe"),
}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()}  {fmt % args}")

    def do_GET(self):
        path = self.path.split("?")[0]

        # Static route table
        if path in ROUTES:
            self._serve_file(ROUTES[path],
                             attachment=(path.endswith(".exe")))
            return

        # /pictures/* served from ROOT/pictures/
        if path.startswith("/pictures/"):
            name = os.path.basename(path)
            fpath = os.path.join(ROOT, "pictures", name)
            self._serve_file(fpath)
            return

        self._404()

    def _serve_file(self, fpath, attachment=False):
        if not os.path.isfile(fpath):
            self._404()
            return
        mime, _ = mimetypes.guess_type(fpath)
        mime = mime or "application/octet-stream"
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        if attachment:
            fname = os.path.basename(fpath)
            self.send_header("Content-Disposition",
                             f'attachment; filename="{fname}"')
        self.end_headers()
        self.wfile.write(data)

    def _404(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"404 Not Found")


if __name__ == "__main__":
    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        print(f"\nPSPC Viewer website running at  http://localhost:{PORT}\n")
        print(f"  Download route:  http://localhost:{PORT}/download/PSPCViewer.exe")
        print(f"  Serving files from: {ROOT}")
        print(f"\n  Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
