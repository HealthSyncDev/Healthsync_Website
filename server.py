"""Serve public/. The page is index.html, styles.css, and script.js."""
from http.server import HTTPServer, SimpleHTTPRequestHandler

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="public", **kwargs)

    def end_headers(self):
        # ponytail: one origin; add a list if more sites call this
        if self.headers.get("Origin") == "https://healthsync.ae":
            self.send_header("Access-Control-Allow-Origin", "https://healthsync.ae")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

if __name__ == "__main__":
    print("http://127.0.0.1:5714", flush=True)
    try:
        HTTPServer(("0.0.0.0", 5714), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
