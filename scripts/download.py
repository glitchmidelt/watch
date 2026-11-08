#!/usr/bin/env python3
"""Download a video via yt-dlp, or resolve a local file path.

Also fetches subtitles (manual first, then auto-generated) in VTT format so
transcribe.py can parse them without needing Whisper.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}

# Subtitle languages to ask yt-dlp for (comma-separated, regex allowed).
# `.*-orig` grabs the original-language auto captions of any video (Arabic,
# French, ...), not only English. Override with $WATCH_SUB_LANGS.
DEFAULT_SUB_LANGS = "en,en-US,en-GB,en-orig,.*-orig,ar,fr"

# Phrases yt-dlp prints when a source wants a logged-in session.
LOGIN_HINTS = (
    "login required", "log in", "sign in", "cookies", "private video",
    "age-restricted", "confirm your age", "rate-limit reached", "not available",
)


def is_url(source: str) -> bool:
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def resolve_local(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"File not found: {p}")
    if p.suffix.lower() not in VIDEO_EXTS:
        print(
            f"[watch] warning: {p.suffix} is not a known video extension, proceeding anyway",
            file=sys.stderr,
        )
    return {
        "video_path": str(p),
        "subtitle_path": None,
        "info": {"title": p.name, "url": str(p)},
        "downloaded": False,
    }


def _sub_lang(path: Path) -> str:
    """`video.en-US.vtt` -> `en-US`."""
    parts = path.name.split(".")
    return parts[-2] if len(parts) >= 3 else ""


def _pick_subtitle(out_dir: Path, video_language: str | None = None) -> Path | None:
    """Prefer subtitles in the video's own language, then English, then any.

    Auto-translated tracks (e.g. English generated from an Arabic video) are
    worse than the original-language track, so the spoken language wins.
    """
    candidates = sorted(out_dir.glob("video*.vtt"))
    if not candidates:
        return None
    if video_language:
        base = video_language.split("-")[0].lower()
        for wanted in (video_language, base, f"{video_language}-orig", f"{base}-orig"):
            for c in candidates:
                if _sub_lang(c).lower() == wanted.lower():
                    return c
        for c in candidates:
            if _sub_lang(c).lower().startswith(base):
                return c
    for c in candidates:
        if _sub_lang(c).endswith("-orig"):
            return c
    preferred = [c for c in candidates if _sub_lang(c).startswith("en")]
    return preferred[0] if preferred else candidates[0]


def cookie_args(cookies_from_browser: str | None = None, cookies_file: str | None = None) -> list[str]:
    """Build yt-dlp cookie flags for login-gated sources (Instagram, X, private YouTube).

    Falls back to $WATCH_COOKIES (a cookies.txt path) and
    $WATCH_COOKIES_FROM_BROWSER (chrome, firefox, safari, ...) so users can set
    it once. Cookies are read at runtime and passed straight to yt-dlp —
    never copied, stored, or logged by this skill.
    """
    cookies_file = cookies_file or os.environ.get("WATCH_COOKIES") or None
    cookies_from_browser = cookies_from_browser or os.environ.get("WATCH_COOKIES_FROM_BROWSER") or None
    if cookies_file:
        path = Path(cookies_file).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"cookies file not found: {path}")
        return ["--cookies", str(path)]
    if cookies_from_browser:
        return ["--cookies-from-browser", cookies_from_browser]
    return []


def _pick_video(out_dir: Path) -> Path | None:
    for ext in (".mp4", ".mkv", ".webm", ".mov"):
        for candidate in out_dir.glob(f"video*{ext}"):
            return candidate
    for candidate in out_dir.glob("video.*"):
        if candidate.suffix.lower() in VIDEO_EXTS:
            return candidate
    return None


def download_url(
    url: str,
    out_dir: Path,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
) -> dict:
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")
    cookies = cookie_args(cookies_from_browser, cookies_file)

    cmd = [
        "yt-dlp",
        "-N", "8",
        "-f", "bv*[height<=720]+ba/b[height<=720]/bv+ba/b",
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", os.environ.get("WATCH_SUB_LANGS") or DEFAULT_SUB_LANGS,
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--no-playlist",
        "--ignore-errors",
        *cookies,
        "-o", output_template,
        "--",
        url,
    ]

    # yt-dlp may exit non-zero if a subtitle variant fails (e.g. 429) even when
    # the video itself downloaded fine. Treat "video file present" as success.
    # stderr is teed: shown live to the user and kept to detect login walls.
    result = subprocess.run(cmd, stdout=sys.stderr, stderr=subprocess.PIPE, text=True)
    if result.stderr:
        sys.stderr.write(result.stderr)
        sys.stderr.flush()
    video = _pick_video(out_dir)
    if video is None:
        msg = f"yt-dlp did not produce a video file in {out_dir} (exit {result.returncode})"
        err = (result.stderr or "").lower()
        if not cookies and any(h in err for h in LOGIN_HINTS):
            msg += (
                "\n[watch] this source looks login-gated. Retry with your own cookies:"
                "\n  --cookies-from-browser chrome   (or firefox, safari, edge, brave)"
                "\n  --cookies ~/Downloads/cookies.txt"
                "\n  or set WATCH_COOKIES / WATCH_COOKIES_FROM_BROWSER once."
            )
        raise SystemExit(msg)
    info_path = out_dir / "video.info.json"
    info: dict = {}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "language": raw.get("language"),
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "duration": raw.get("duration"),
                "url": raw.get("webpage_url") or url,
            }
        except Exception as exc:
            print(f"[watch] info.json parse failed: {exc}", file=sys.stderr)
            info = {"url": url}

    subtitle = _pick_subtitle(out_dir, info.get("language"))

    return {
        "video_path": str(video),
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": True,
    }


def download(
    source: str,
    out_dir: Path,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
) -> dict:
    if is_url(source):
        return download_url(source, out_dir, cookies_from_browser, cookies_file)
    return resolve_local(source)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Download a video (or resolve a local path).")
    ap.add_argument("source")
    ap.add_argument("out_dir")
    ap.add_argument("--cookies-from-browser", default=None)
    ap.add_argument("--cookies", default=None)
    a = ap.parse_args()
    result = download(a.source, Path(a.out_dir), a.cookies_from_browser, a.cookies)
    print(json.dumps(result, indent=2))
