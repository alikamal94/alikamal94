#!/usr/bin/env bash
# Hey Jarvis installer for macOS and Linux.
#   curl -fsSL https://raw.githubusercontent.com/alikamal94/alikamal94/claude/funny-shannon-6zt71u/hey-jarvis/install.sh | bash
set -euo pipefail

RAW="https://raw.githubusercontent.com/alikamal94/alikamal94/claude/funny-shannon-6zt71u/hey-jarvis"
OJ_HOME="${OPENJARVIS_HOME:-$HOME/.openjarvis}"
PY="$OJ_HOME/.venv/bin/python"
APP_DIR="$OJ_HOME/hey-jarvis"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

# 1. OpenJarvis itself (skipped if already installed)
if [ ! -x "$PY" ]; then
    say "Installing OpenJarvis (about 3 minutes)..."
    curl -fsSL https://open-jarvis.github.io/OpenJarvis/install.sh | bash
fi
[ -x "$PY" ] || { echo "OpenJarvis did not install to $OJ_HOME. Fix that first, then re-run."; exit 1; }

# 2. Audio libraries (Linux only; macOS already has them)
if [ "$(uname)" = "Linux" ] && command -v apt-get >/dev/null; then
    say "Installing microphone and voice libraries (may ask for your password)..."
    sudo apt-get install -y libportaudio2 espeak-ng || echo "Could not install audio libs; continuing."
fi

# 3. Wake word + speech recognition into the OpenJarvis environment
say "Installing wake word and speech recognition..."
uv pip install --python "$PY" "openwakeword==0.4.0" "faster-whisper>=1.0" "av>=11,<19" \
    "sounddevice>=0.5" "soundfile>=0.12" "numpy>=1.24"

# 4. The listener script
mkdir -p "$APP_DIR"
here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$here" ] && [ -f "$here/jarvis_wake.py" ]; then
    cp "$here/jarvis_wake.py" "$APP_DIR/"
else
    curl -fsSL "$RAW/jarvis_wake.py" -o "$APP_DIR/jarvis_wake.py"
fi

# 5. Download the speech model now so the first "Hey Jarvis" is instant
say "Downloading speech model and checking everything loads..."
"$PY" "$APP_DIR/jarvis_wake.py" --check

# 6. Start automatically at login
if [ "$(uname)" = "Darwin" ]; then
    # A Terminal window owns the microphone permission on macOS, so we launch
    # through a .command file added to Login Items.
    launcher="$APP_DIR/Hey Jarvis.command"
    cat > "$launcher" <<EOF
#!/bin/bash
printf '\\e]0;Hey Jarvis\\a'
exec "$PY" "$APP_DIR/jarvis_wake.py"
EOF
    chmod +x "$launcher"
    osascript -e "tell application \"System Events\" to delete (every login item whose name is \"Hey Jarvis.command\")" >/dev/null 2>&1 || true
    osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$launcher\", hidden:true}" >/dev/null
    say "Starting Hey Jarvis. If macOS asks for microphone access, click Allow."
    open "$launcher"
else
    unit="$HOME/.config/systemd/user/hey-jarvis.service"
    mkdir -p "$(dirname "$unit")"
    cat > "$unit" <<EOF
[Unit]
Description=Hey Jarvis wake word for OpenJarvis
After=sound.target pipewire.service pulseaudio.service

[Service]
ExecStart=$PY $APP_DIR/jarvis_wake.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now hey-jarvis.service
fi

say 'Done! Say "Hey Jarvis", wait for the chime, then ask your question.'
echo "Log: $OJ_HOME/hey-jarvis.log"
