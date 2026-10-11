# Auto-posting Shorts to YouTube

When Claude finishes a Short it adds an `upload.json` next to the video and pushes. The
**Post to YouTube** workflow (`.github/workflows/youtube-upload.yml`) then uploads it with the
YouTube Data API and commits `posted.json` (video id + link) beside it, so nothing is posted twice.

## One-time setup (about 15 minutes, done by you, not Claude)

1. **Google Cloud project:** go to https://console.cloud.google.com, create a project, and enable
   **YouTube Data API v3** (APIs & Services → Library).
2. **OAuth consent screen:** choose *External*, fill in the app name and your email, and add the
   scope `.../auth/youtube.upload`. Then set the publishing status to **In production**. In
   *Testing* mode the login expires every 7 days and posting would stop.
3. **OAuth client:** go to APIs & Services → Credentials → Create credentials → OAuth client ID →
   *Desktop app*, and download the JSON file.
4. **Sign in once on your computer:**
   `python tools/youtube/get_refresh_token.py ~/Downloads/client_secret_XXXX.json`.
   Sign in with Google in the browser that opens and **pick the new channel**. Google will warn that
   the app isn't verified; it's your own app, so choose *Advanced → continue*.
5. **GitHub secrets:** in the repo, go to Settings → Secrets and variables → Actions → New repository
   secret, and add `YT_CLIENT_ID`, `YT_CLIENT_SECRET` and `YT_REFRESH_TOKEN` with the printed values.
   Never paste them into chat or a file in the repo.
6. **Audit:** Google locks videos uploaded through a new, unaudited API project to **private**. Fill in
   the YouTube API Services audit form (https://support.google.com/youtube/contact/yt_api_form) to lift
   that. It's free, but approval can take a few weeks. Until then each video is uploaded as private;
   switch it to public in YouTube Studio (one click), or keep posting from the phone app.

After that, every new `upload.json` that gets pushed is posted automatically. To post a video
again or retry one, run the workflow from the Actions tab (*Run workflow*).

## upload.json

```json
{
  "video": "my_short.mp4",
  "title": "…  #shorts",
  "description": "…",
  "tags": ["…"],
  "category": "28",
  "privacy": "public",
  "made_for_kids": false,
  "publish_at": "2026-10-12T15:00:00Z"
}
```

`publish_at` is optional; if it's set, the video is scheduled for that time instead of going live
straight away.
