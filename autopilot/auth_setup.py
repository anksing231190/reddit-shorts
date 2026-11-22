"""One-time, on YOUR computer: get a YouTube refresh token for the autopilot.

  python -m autopilot.auth_setup --client-id XXX.apps.googleusercontent.com --client-secret YYY

Opens your browser, you sign in with the channel's Google account, and it prints the refresh token.
Store the three values as GitHub repository secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
The OAuth client must be of type "Desktop app".
"""
import argparse
import http.server
import secrets
import urllib.parse
import webbrowser

import requests

from .youtube import SCOPES

PORT = 8765


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--client-secret", required=True)
    a = ap.parse_args()
    state = secrets.token_urlsafe(16)
    redirect = f"http://127.0.0.1:{PORT}/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": a.client_id, "redirect_uri": redirect, "response_type": "code", "scope": " ".join(SCOPES),
        "access_type": "offline", "prompt": "consent", "state": state})
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done - you can close this tab and return to the terminal.")

        def log_message(self, *args):
            pass

    print("Opening your browser to sign in...\nIf it does not open, visit:\n" + url)
    webbrowser.open(url)
    srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if got.get("state") != state or "code" not in got:
        raise SystemExit(f"Sign-in failed: {got}")
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "code": got["code"], "client_id": a.client_id, "client_secret": a.client_secret,
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("refresh_token")
    if not tok:
        raise SystemExit("No refresh token returned - remove the app's access at myaccount.google.com/permissions and retry.")
    print("\nYT_REFRESH_TOKEN =", tok)
    print("\nAdd YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN as GitHub repository secrets. Keep them private.")


if __name__ == "__main__":
    main()
