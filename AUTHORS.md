# Authors & credits

## Original project

**Bradley Bonanno**: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)

The original `/watch` skill: the yt-dlp download, the ffmpeg frame pipeline, the Groq/OpenAI
Whisper backends, the multi-surface install flow and the SessionStart hook. MIT, © 2026 Bradley Bonanno.

## Forks merged here

**Taoufik**: [taoufik123-collab/claude-watch](https://github.com/taoufik123-collab/claude-watch)

Scene-change frame extraction, the 0-10s hook microscope, pacing metrics, the structured
`report.md` and optional Obsidian auto-save.

**Mathias Schusterman**: [mathiaschu/watch](https://github.com/mathiaschu/watch)

Local transcription (mlx-whisper / openai-whisper) and browser-cookie support for
login-gated sources.

## This distribution

**Abdlali Hammoujane**: merged both forks. It runs all four Whisper backends through one
selector (with word timestamps everywhere), picks subtitles in the video's own language,
adds the login-wall hint, the `WATCH_*` config and the `stt.py` rename (which fixes the
`openai-whisper` import), plus tests.
