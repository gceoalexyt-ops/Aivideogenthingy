#!/usr/bin/env python3
"""One-time setup, run on YOUR computer: sign in with Google and print a YouTube upload refresh token.

    python tools/youtube/get_refresh_token.py path/to/client_secret.json

Opens your browser at Google's sign-in page (you sign in there; this script never sees your password)
and asks permission to upload videos. Pick the NEW channel when Google asks which account/channel.
Then paste the three printed values into GitHub as repository secrets. Standard library only.
"""

import http.server
import json
import sys
import urllib.parse
import urllib.request
import webbrowser

PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def main():
    cfg = json.load(open(sys.argv[1]))
    cfg = cfg.get("installed") or cfg.get("web")
    cid, secret = cfg["client_id"], cfg["client_secret"]
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent",
    })  # fmt: skip
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done - you can close this tab and go back to the terminal.")

        def log_message(self, *a):
            pass

    print("Opening your browser to sign in. If it doesn't open, visit:\n" + url)
    webbrowser.open(url)
    srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if "error" in got:
        raise SystemExit(f"Google returned an error: {got['error']}")
    data = urllib.parse.urlencode({
        "code": got["code"], "client_id": cid, "client_secret": secret,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }).encode()  # fmt: skip
    tok = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data))
    print("\nAdd these as GitHub repository secrets (Settings > Secrets and variables > Actions):\n")
    print(f"YT_CLIENT_ID      = {cid}")
    print(f"YT_CLIENT_SECRET  = {secret}")
    print(f"YT_REFRESH_TOKEN  = {tok['refresh_token']}")
    print("\nDon't paste these into chat or commit them anywhere.")


if __name__ == "__main__":
    main()
