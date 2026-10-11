#!/usr/bin/env python3
"""Post every finished Short that has an upload.json and hasn't been posted yet.

Runs in GitHub Actions (see .github/workflows/youtube-upload.yml). For each sims/*/upload.json or
shorts/*/upload.json it uploads the video with the YouTube Data API and writes posted.json next to it
with the video id, so it's never posted twice. A video also counts as posted if posted.json exists on
any branch (the workflow checks out full history), so merging the PR afterwards doesn't re-post it.

Needs three repository secrets (see tools/youtube/README.md):
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Standard library only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE_HINT = "https://www.googleapis.com/auth/youtube.upload"


def posted_anywhere(folder: Path) -> bool:
    if (folder / "posted.json").exists():
        return True
    rel = (folder / "posted.json").relative_to(ROOT).as_posix()
    out = subprocess.run(["git", "log", "--all", "--format=%H", "-1", "--", rel], cwd=ROOT, capture_output=True, text=True)
    return bool(out.stdout.strip())


def access_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()  # fmt: skip
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data) as r:
        return json.load(r)["access_token"]


def upload(token: str, video: Path, meta: dict) -> str:
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "categoryId": str(meta.get("category", "28")),
        },
        "status": {
            "privacyStatus": meta.get("privacy", "public"),
            "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", False)),
        },
    }
    if meta.get("publish_at"):  # scheduled: YouTube needs it private until then
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = meta["publish_at"]
    size = video.stat().st_size
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        session = r.headers["Location"]
    with open(video, "rb") as fh:
        put = urllib.request.Request(session, data=fh.read(), method="PUT",
                                     headers={"Content-Type": "video/mp4", "Content-Length": str(size)})  # fmt: skip
        with urllib.request.urlopen(put) as r:
            return json.load(r)["id"]


def main() -> int:
    manifests = sorted(ROOT.glob("sims/*/upload.json")) + sorted(ROOT.glob("shorts/*/upload.json"))
    todo = [m for m in manifests if not posted_anywhere(m.parent)]
    if not todo:
        print("nothing new to post")
        return 0
    missing = [k for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.environ.get(k)]
    if missing:
        print(f"::warning::YouTube secrets not set ({', '.join(missing)}); not posting {[str(m.parent.name) for m in todo]}")
        return 0
    token = access_token()
    failed = False
    for m in todo:
        meta = json.loads(m.read_text())
        video = m.parent / meta["video"]
        try:
            vid = upload(token, video, meta)
        except urllib.error.HTTPError as e:
            print(f"::error::upload of {video} failed: {e.code} {e.read().decode()[:500]}")
            failed = True
            continue
        info = {"id": vid, "url": f"https://youtube.com/shorts/{vid}", "posted_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        (m.parent / "posted.json").write_text(json.dumps(info, indent=2) + "\n")
        print(f"posted {m.parent.name}: {info['url']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
