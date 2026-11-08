#!/usr/bin/env bash
# SessionStart hook for /watch — one-line status so users know what's wired up.
# Silent when ready. Points at the installer when something is missing.
set -euo pipefail

CONFIG_FILE="$HOME/.config/watch/.env"

# Warn if the secrets file has loose permissions.
if [[ -f "$CONFIG_FILE" ]]; then
  perms=$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE" 2>/dev/null || echo "")
  if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
    echo "/watch: WARNING — $CONFIG_FILE has permissions $perms (should be 600)."
    echo "  Fix: chmod 600 $CONFIG_FILE"
  fi
fi

# Read a key from the env or the config file without exporting it.
read_key() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    echo "${!name}"
    return
  fi
  if [[ -f "$CONFIG_FILE" ]]; then
    awk -F= -v k="$name" '
      /^[[:space:]]*#/ { next }
      $1 == k {
        sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2);
        gsub(/^["'\'']|["'\'']$/, "", $2);
        print $2; exit
      }
    ' "$CONFIG_FILE"
  fi
}

HAS_FFMPEG=""
HAS_YTDLP=""
command -v ffmpeg >/dev/null 2>&1 && HAS_FFMPEG="yes"
command -v yt-dlp >/dev/null 2>&1 && HAS_YTDLP="yes"

HAS_KEY=""
[[ -n "$(read_key GROQ_API_KEY)" || -n "$(read_key OPENAI_API_KEY)" ]] && HAS_KEY="yes"

HAS_LOCAL=""
if command -v python3 >/dev/null 2>&1; then
  if python3 - <<'PY' >/dev/null 2>&1
import importlib.util, sys
sys.exit(0 if (importlib.util.find_spec("mlx_whisper") or importlib.util.find_spec("whisper")) else 1)
PY
  then
    HAS_LOCAL="yes"
  fi
fi

if [[ -z "$HAS_FFMPEG" || -z "$HAS_YTDLP" ]]; then
  echo "/watch: needs ffmpeg + yt-dlp. Run \`python3 \$CLAUDE_PLUGIN_ROOT/scripts/setup.py\` once to install."
  exit 0
fi

# Binaries + any Whisper backend → silent.
if [[ -n "$HAS_KEY" || -n "$HAS_LOCAL" ]]; then
  exit 0
fi

echo "/watch: ready for videos with captions. For the Whisper fallback add GROQ_API_KEY / OPENAI_API_KEY to ~/.config/watch/.env, or \`pip3 install openai-whisper\` (local, no key)."
