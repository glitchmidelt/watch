# /watch: Claude can watch videos

Give Claude a video (a YouTube, TikTok, Instagram, X, Vimeo or Loom link, or a local `.mp4` / `.mov` file) and a question. Claude downloads it, pulls out frames and a transcript, looks at every frame as an image, and answers based on what is on screen and what is said.

```
/watch https://youtu.be/abc how does this creator hook the viewer?
/watch https://www.tiktok.com/@user/video/123 summarize this
/watch https://www.instagram.com/reel/XXXX/ what product is shown?
/watch bug-repro.mov what's going wrong?
```

This project merges two forks of [bradautomates/claude-video](https://github.com/bradautomates/claude-video) and keeps the best parts of each:

| Feature | From |
|---|---|
| Scene-change frames (one frame per shot, not one every N seconds) | taoufik123-collab/claude-watch |
| 0-10s **hook microscope** (2 fps + word-level transcript of the opening) | taoufik123-collab/claude-watch |
| Pacing metrics (cuts/min, shot length) and a structured `report.md` | taoufik123-collab/claude-watch |
| Optional Obsidian auto-save | taoufik123-collab/claude-watch |
| **Cookies** for Instagram, X, and private or age-restricted videos | mathiaschu/watch |
| **Local Whisper**: free and offline, no API key | mathiaschu/watch |
| Groq / OpenAI Whisper API (faster when you have a key) | both |

### Added in this merge

- **All four Whisper backends in one place.** Auto order: `groq` → `openai` → `mlx` → `local`. If a key is set, the API is used because it is faster. Without a key, transcription runs on your machine. The hook microscope gets word timestamps from every backend, local ones included.
- **Subtitles in the video's own language.** yt-dlp also fetches the original-language auto-captions (`.*-orig`, `ar`, `fr`), and the script picks the track that matches the spoken language over an auto-translated English one. This matters for Arabic, Darija and French content.
- **Clear login hint.** When Instagram or X refuses a download, the error tells you exactly which cookie flag to add.
- **Set-once config** through environment variables: `WATCH_COOKIES_FROM_BROWSER`, `WATCH_COOKIES`, `WATCH_WHISPER`, `WATCH_WHISPER_MODEL`, `WATCH_WHISPER_LANGUAGE`, `WATCH_SUB_LANGS`.
- **Bug fix:** the Whisper client used to be called `scripts/whisper.py`, which hid the real `openai-whisper` package (`import whisper` imported the script instead). It is now called `scripts/stt.py`.
- 16 new unit tests (23 in total).

## Install

**Claude Code (plugin):**
```
/plugin marketplace add glitchmidelt/watch
/plugin install watch@watch
```

**Manual (Claude Code / Codex skill folder):**
```bash
git clone https://github.com/glitchmidelt/watch.git ~/.claude/skills/watch
```

**claude.ai (web):** download `watch.skill` from the [latest release](https://github.com/glitchmidelt/watch/releases/latest) and upload it in Settings → Capabilities → Skills. Turn on "Code execution and file creation" first.

Then run this once:
```bash
python3 ~/.claude/skills/watch/scripts/setup.py
```

### Requirements

- Python 3.9+
- `ffmpeg` and `yt-dlp`. On macOS they install automatically with brew. On Linux and Windows, setup prints the exact commands.
- **Optional:** a Whisper backend, only needed for videos without captions. Pick one:
  - `GROQ_API_KEY` (cheap, fast) or `OPENAI_API_KEY` in `~/.config/watch/.env`
  - `pip3 install mlx-whisper` (Apple Silicon, local, free)
  - `pip3 install openai-whisper` (any OS, local, free; uses the `small` model by default)

## Instagram, X, private videos: cookies

Public videos need nothing. If a site asks for a login, use the cookies from **your own** browser session:

```
/watch https://www.instagram.com/reel/XXXX/ --cookies-from-browser firefox
/watch https://x.com/user/status/123 --cookies ~/Downloads/cookies.txt
```

To set it once, so every `/watch` uses it:
```bash
export WATCH_COOKIES_FROM_BROWSER=firefox   # or chrome, safari, edge, brave
```

Tips:
- Close Chrome fully (Cmd-Q) before using `chrome`. It locks its cookie file while it runs. Firefox usually works without closing it.
- If browser extraction fails, export a `cookies.txt` with the open-source "Get cookies.txt LOCALLY" extension (Chrome) or "cookies.txt" (Firefox), and use `--cookies`.
- Cookies are read when the command runs and passed straight to yt-dlp. They are never copied, stored or logged.

## Flags

| Flag | What it does |
|---|---|
| `--start T` / `--end T` | Focus on a section (`SS`, `MM:SS`, `HH:MM:SS`), with denser frames |
| `--intent "..."` | Why you are watching; it shapes the TL;DR in `report.md` |
| `--max-frames N` | Lower the frame cap (fewer tokens) |
| `--resolution W` | Frame width (default 512; use 1024 to read on-screen text) |
| `--fps F` | Override auto-fps (max 2), which turns off scene-change sampling |
| `--cookies-from-browser B` / `--cookies FILE` | Cookies for login-gated sources |
| `--whisper groq\|openai\|mlx\|local` | Force a Whisper backend |
| `--no-whisper` | No transcription, frames only |
| `--no-scene-change` | Uniform frame sampling |
| `--no-hook-microscope` | Skip the dense 0-10s pass |
| `--out-dir DIR` | Keep working files in a specific folder |

## Environment variables

| Variable | Example | Purpose |
|---|---|---|
| `WATCH_COOKIES_FROM_BROWSER` | `firefox` | Default browser for cookies |
| `WATCH_COOKIES` | `~/cookies.txt` | Default cookies.txt |
| `WATCH_WHISPER` | `local` | Force a backend |
| `WATCH_WHISPER_MODEL` | `medium` | Local model (tiny / base / small / medium / large-v3) |
| `WATCH_WHISPER_LANGUAGE` | `ar` | Language hint for local Whisper (auto-detected if unset) |
| `WATCH_SUB_LANGS` | `en,ar,fr` | Subtitle languages to request from yt-dlp |
| `WATCH_VAULT_DIR` | `~/Obsidian` | Obsidian vault for auto-save |

These variables can also go in `~/.config/watch/.env`, except `WATCH_VAULT_DIR`, which must be exported.

## How it works

1. `yt-dlp` downloads the video (up to 720p) and any captions. Local files are used in place.
2. `ffmpeg` extracts one frame per scene change. Static videos (screen recordings, talking heads) fall back to evenly spaced frames. The limits are 100 frames and 2 fps.
3. The first 10 seconds get a dense pass: 2 fps plus word-level timestamps.
4. The transcript comes from the captions. If there are none, Whisper (API or local) transcribes the audio.
5. The script prints the frame paths with timestamps and writes `report.md`. Claude `Read`s every frame, answers you, and fills in the report.

## Limits

- Best accuracy on videos under 10 minutes. For longer ones, use `--start` / `--end`.
- The Whisper API limit is 25 MB (about 50 minutes of audio). Local Whisper has no size limit but is slower on CPU.
- Region-locked videos, and private videos you cannot open yourself, will not download.

## Structure

```
scripts/
  watch.py       entry point
  download.py    yt-dlp wrapper: cookies, subtitle language picking
  frames.py      uniform + scene-change frames, hero frames
  hook.py        0-10s hook microscope
  pacing.py      cuts/min, shot lengths
  report.py      structured report.md
  transcribe.py  VTT parsing
  stt.py         Whisper: groq / openai (API) + mlx / local (on-device)
  setup.py       preflight + installer
  tests/         unittest suite
hooks/           SessionStart status hook
commands/        /watch slash command
```

Run the tests:
```bash
python3 -m unittest discover -s scripts/tests -t scripts
```

## Credits

- **Bradley Bonanno**: original [claude-video](https://github.com/bradautomates/claude-video) pipeline (MIT)
- **Taoufik**: [claude-watch](https://github.com/taoufik123-collab/claude-watch): scene-change frames, hook microscope, report, Obsidian
- **Mathias Schusterman**: [watch](https://github.com/mathiaschu/watch): local Whisper, browser cookies

MIT license, see [LICENSE](LICENSE) and [AUTHORS.md](AUTHORS.md).
