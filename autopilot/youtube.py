"""Minimal YouTube Data API v3 + Analytics API client using an OAuth refresh token.

Environment: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (create with `python -m autopilot.auth_setup`).
Quota (10,000 units/day default): upload 1600, videos.update 50, list calls 1.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]
_token: dict = {}


def token() -> str:
    if _token.get("exp", 0) > time.time() + 60:
        return _token["access"]
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    _token.update(access=d["access_token"], exp=time.time() + d.get("expires_in", 3600))
    return _token["access"]


def _h(extra=None):
    return {"Authorization": f"Bearer {token()}", **(extra or {})}


def _check(r):
    if r.status_code >= 400:
        try:
            e = r.json()["error"]
            why = "; ".join(f"{x.get('reason')}: {x.get('message')}" for x in e.get("errors", [])) or e.get("message")
        except Exception:
            why = " ".join(r.text.split())[:300]
        hint = {"youtubeSignupRequired": " - this Google login has no YouTube channel: re-authorize and pick the "
                "channel (brand account) on Google's account chooser"}.get((e.get("errors") or [{}])[0].get("reason", "")
                                                                         if "e" in locals() else "", "")
        raise RuntimeError(f"YouTube API {r.status_code}: {why}{hint}")
    return r


def upload(video: Path, title: str, description: str, tags: list[str], category: str = "27",
           made_for_kids: bool = False, privacy: str = "private", publish_at: str | None = None) -> str:
    """publish_at (RFC3339 UTC): the video stays private and YouTube makes it public at that time."""
    meta = {
        "snippet": {"title": title[:100], "description": description[:4900], "tags": tags, "categoryId": category},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": made_for_kids,
                   "containsSyntheticMedia": False, "embeddable": True},
    }
    if publish_at:
        meta["status"]["publishAt"] = publish_at
    size = video.stat().st_size
    r = _check(requests.post(f"{UPLOAD}?uploadType=resumable&part=snippet,status", headers=_h({
        "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(size)}), data=json.dumps(meta), timeout=60))
    loc = r.headers["Location"]
    for attempt in range(5):
        try:
            with open(video, "rb") as f:
                r = requests.put(loc, headers=_h({"Content-Type": "video/mp4"}), data=f, timeout=600)
            if r.status_code in (200, 201):
                return r.json()["id"]
            if r.status_code < 500:
                _check(r)
        except requests.RequestException:
            pass
        time.sleep(5 * 2 ** attempt)
    raise RuntimeError("upload failed after retries")


def schedule(video_id: str, publish_at_iso: str):
    """Video must be private; YouTube flips it public at publish_at (RFC3339, UTC)."""
    body = {"id": video_id, "status": {"privacyStatus": "private", "publishAt": publish_at_iso,
                                       "selfDeclaredMadeForKids": False}}
    _check(requests.put(f"{API}/videos?part=status", headers=_h({"Content-Type": "application/json"}),
                        data=json.dumps(body), timeout=30))


def my_channel_id() -> str:
    r = _check(requests.get(f"{API}/channels", params={"part": "id", "mine": "true"}, headers=_h(), timeout=30))
    return r.json()["items"][0]["id"]


def recent_comments(channel_id: str, max_pages: int = 2) -> list[dict]:
    out, page = [], None
    for _ in range(max_pages):
        params = {"part": "snippet", "allThreadsRelatedToChannelId": channel_id, "maxResults": 100,
                  "order": "time", "textFormat": "plainText"}
        if page:
            params["pageToken"] = page
        d = _check(requests.get(f"{API}/commentThreads", params=params, headers=_h(), timeout=30)).json()
        for it in d.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            out.append({"id": it["id"], "video_id": it["snippet"].get("videoId"), "author": s["authorDisplayName"],
                        "text": s["textDisplay"], "likes": s.get("likeCount", 0), "published": s["publishedAt"],
                        "replies": it["snippet"].get("totalReplyCount", 0)})
        page = d.get("nextPageToken")
        if not page:
            break
    return out


def retention_curve(video_id: str, start: str, end: str) -> list[tuple[float, float]]:
    r = _check(requests.get(ANALYTICS, params={
        "ids": "channel==MINE", "startDate": start, "endDate": end, "metrics": "audienceWatchRatio",
        "dimensions": "elapsedVideoTimeRatio", "filters": f"video=={video_id}"}, headers=_h(), timeout=30))
    return [(row[0] * 100, row[1] * 100) for row in r.json().get("rows", [])]


def video_stats(video_ids: list[str], start: str, end: str) -> dict[str, dict]:
    if not video_ids:
        return {}
    r = _check(requests.get(ANALYTICS, params={
        "ids": "channel==MINE", "startDate": start, "endDate": end,
        "metrics": "views,averageViewPercentage,averageViewDuration,likes,subscribersGained",
        "dimensions": "video", "filters": "video==" + ",".join(video_ids[:200])}, headers=_h(), timeout=30))
    cols = [c["name"] for c in r.json().get("columnHeaders", [])]
    return {row[0]: dict(zip(cols[1:], row[1:])) for row in r.json().get("rows", [])}


def publish_now(video_id: str, privacy: str = "public"):
    """Set an uploaded video's privacy right now: public (publish immediately) or private (hide it)."""
    body = {"id": video_id, "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                                       "containsSyntheticMedia": False, "embeddable": True}}
    _check(requests.put(f"{API}/videos?part=status", headers=_h({"Content-Type": "application/json"}),
                        data=json.dumps(body), timeout=30))
