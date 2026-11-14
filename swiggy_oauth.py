import base64, hashlib, http.server, json, secrets, ssl, urllib.parse, urllib.request, webbrowser

ctx = ssl._create_unverified_context()
def post_get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    return json.loads(urllib.request.urlopen(req, context=ctx).read())

meta = post_get("https://mcp.swiggy.com/.well-known/oauth-authorization-server")
reg = post_get(meta["registration_endpoint"], json.dumps({"client_name": "Basket Blanket", "redirect_uris": ["http://localhost:8765/callback"], "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "none"}).encode(), {"Content-Type": "application/json"})
ver = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
cha = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode({"response_type": "code", "client_id": reg["client_id"], "redirect_uri": "http://localhost:8765/callback", "scope": "mcp:tools", "code_challenge": cha, "code_challenge_method": "S256"})
code_box = {}
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code_box["c"] = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [""])[0]
        self.send_response(200); self.end_headers(); self.wfile.write(b"Done! Go back to Terminal.")
    def log_message(self, *a): pass
s = http.server.HTTPServer(("localhost", 8765), H)
webbrowser.open(url)
while "c" not in code_box: s.handle_request()
tok = post_get(meta["token_endpoint"], urllib.parse.urlencode({"grant_type": "authorization_code", "code": code_box["c"], "redirect_uri": "http://localhost:8765/callback", "client_id": reg["client_id"], "code_verifier": ver}).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
print("\nYOUR SWIGGY TOKEN:\n" + tok["access_token"])
