"""Microsoft device-code sign-in -> Xbox Live -> XSTS -> Minecraft token.

Same chain as gceoalexyt-ops/Mcplayerweb server/auth.js. The user signs in
themselves at microsoft.com/link; the resulting token is written to
~/mc/auth.json (mode 600) and never printed.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CLIENT_ID = "000000004C12AE6F"
SCOPE = "service::user.auth.xboxlive.com::MBI_SSL"
OUT = os.path.expanduser("~/mc/auth.json")
CODE_FILE = os.path.expanduser("~/mc/signin_code.txt")


def post(url, body, form=False, headers=None):
    h = {"Accept": "application/json"}
    if form:
        data = urllib.parse.urlencode(body).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, {"raw": txt[:300]}


def main():
    st, d = post("https://login.live.com/oauth20_connect.srf",
                 {"client_id": CLIENT_ID, "scope": SCOPE, "response_type": "device_code"}, form=True)
    if "device_code" not in d:
        sys.exit(f"device code request failed: {st} {d}")
    with open(CODE_FILE, "w") as f:
        f.write(f"{d['verification_uri']} {d['user_code']}\n")
    print("SIGNIN", d["verification_uri"], d["user_code"], flush=True)

    interval = d.get("interval", 5)
    deadline = time.time() + d.get("expires_in", 900)
    while time.time() < deadline:
        time.sleep(interval)
        st, t = post("https://login.live.com/oauth20_token.srf",
                     {"client_id": CLIENT_ID, "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                      "device_code": d["device_code"]}, form=True)
        if "access_token" in t:
            ms = t["access_token"]
            break
        err = t.get("error")
        if err == "slow_down":
            interval += 5
        elif err != "authorization_pending":
            sys.exit(f"sign-in failed: {err} {t.get('error_description', '')}")
    else:
        sys.exit("sign-in code expired")
    print("microsoft ok", flush=True)

    xbl = None
    for prefix in ("t", "d"):
        st, x = post("https://user.auth.xboxlive.com/user/authenticate",
                     {"Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com",
                                     "RpsTicket": f"{prefix}={ms}"},
                      "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"},
                     headers={"x-xbl-contract-version": "1"})
        if x.get("Token"):
            xbl = x
            break
    if not xbl:
        sys.exit(f"xbox live failed: {st}")
    print("xbox live ok", flush=True)

    st, xs = post("https://xsts.auth.xboxlive.com/xsts/authorize",
                  {"Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl["Token"]]},
                   "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"},
                  headers={"x-xbl-contract-version": "1"})
    if not xs.get("Token"):
        sys.exit(f"xsts failed: {st} XErr={xs.get('XErr')}")
    uhs = xs["DisplayClaims"]["xui"][0]["uhs"]
    print("xsts ok", flush=True)

    st, mc = post("https://api.minecraftservices.com/authentication/login_with_xbox",
                  {"identityToken": f"XBL3.0 x={uhs};{xs['Token']}"})
    if "access_token" not in mc:
        sys.exit(f"minecraft login failed: {st} {mc.get('raw', mc.get('errorMessage', ''))[:200]}")
    print("minecraft login ok", flush=True)

    req = urllib.request.Request("https://api.minecraftservices.com/minecraft/profile",
                                 headers={"Authorization": "Bearer " + mc["access_token"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            prof = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.exit("this Microsoft account does not own Minecraft: Java Edition")
        sys.exit(f"profile failed: {e.code}")

    fd = os.open(OUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"access_token": mc["access_token"], "expires_at": time.time() + mc.get("expires_in", 86400),
                   "uuid": prof["id"], "name": prof["name"], "xuid": xs["DisplayClaims"]["xui"][0].get("xid", "")}, f)
    os.remove(CODE_FILE)
    print("PROFILE", prof["name"], flush=True)


main()
