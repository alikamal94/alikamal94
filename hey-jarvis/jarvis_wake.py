"""Hey Jarvis: always-on wake word for OpenJarvis.

Say "Hey Jarvis", wait for the chime, ask your question, and Jarvis answers
out loud. Runs inside the OpenJarvis Python environment.

    python jarvis_wake.py            # listen forever
    python jarvis_wake.py --check    # load everything once and exit
    python jarvis_wake.py --threshold 0.6   # stricter wake word
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
FRAME = 1280  # 80 ms, what openWakeWord expects
WAKE_MODEL = "hey_jarvis"

if os.environ.get("OPENJARVIS_HOME"):
    LOG_DIR = Path(os.environ["OPENJARVIS_HOME"])
elif os.name == "nt":
    LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpenJarvis"
else:
    LOG_DIR = Path.home() / ".openjarvis"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "hey-jarvis.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("hey-jarvis")


# --------------------------------------------------------------------------- speech out

def _system_say(text: str) -> None:
    """Speak with the operating system's built-in voice."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["say", text], check=False)
        elif system == "Windows":
            ps = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Speak([Console]::In.ReadToEnd())"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                input=text, text=True, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            for cmd in ("espeak-ng", "espeak", "spd-say"):
                if shutil.which(cmd):
                    subprocess.run([cmd, text], check=False)
                    return
            log.warning("No text-to-speech program found (install espeak-ng).")
    except Exception as exc:  # never let speech kill the listener
        log.warning("Speech failed: %s", exc)


class Voice:
    """Use an OpenJarvis TTS backend if one is configured, else the OS voice."""

    def __init__(self) -> None:
        self._session = None
        try:
            from openjarvis.cli._voice_chat import VoiceSession

            session = VoiceSession()
            if session.get_tts_backend() is not None:
                self._session = session
        except Exception:
            self._session = None

    def say(self, text: str) -> None:
        text = _for_speech(text)
        if not text:
            return
        if self._session is not None:
            try:
                from rich.console import Console
                from openjarvis.cli._voice_chat import speak

                speak(text, Console(quiet=True), self._session)
                return
            except Exception as exc:
                log.warning("OpenJarvis voice failed, using system voice: %s", exc)
        _system_say(text)


def _for_speech(text: str) -> str:
    """Strip markdown and code so the answer sounds natural."""
    text = re.sub(r"```.*?```", " (code shown on screen) ", text, flags=re.S)
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.S)
    text = re.sub(r"[*_`#>|]+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def chime() -> None:
    import sounddevice as sd

    t = np.linspace(0, 0.15, int(SAMPLE_RATE * 0.15), endpoint=False)
    tone = np.concatenate([np.sin(2 * np.pi * 880 * t), np.sin(2 * np.pi * 1320 * t)])
    fade = np.minimum(1, np.minimum(np.arange(tone.size), np.arange(tone.size)[::-1]) / 400)
    try:
        sd.play((0.25 * tone * fade).astype(np.float32), SAMPLE_RATE)
        sd.wait()
    except Exception:
        pass


# --------------------------------------------------------------------------- wake word

def load_wake_model():
    import openwakeword
    from openwakeword.model import Model

    path = openwakeword.models[WAKE_MODEL]["model_path"]
    return Model(wakeword_model_paths=[path])


def wait_for_wake_word(model, threshold: float) -> float:
    """Block until "Hey Jarvis" is heard. Returns the detection score."""
    import sounddevice as sd

    model.reset()
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME) as stream:
        warmup = 15  # ignore the first ~1 s while the model fills its buffer
        while True:
            frame, _ = stream.read(FRAME)
            scores = model.predict(frame[:, 0])
            if warmup:
                warmup -= 1
                continue
            score = max(scores.values())
            if score >= threshold:
                return score


# --------------------------------------------------------------------------- main loop

class Assistant:
    def __init__(self) -> None:
        from openjarvis import Jarvis
        from openjarvis.cli._voice_chat import VoiceSession

        self.voice = Voice()
        self.ears = VoiceSession()
        if self.ears.get_stt_backend() is None:
            raise RuntimeError(
                "Speech recognition could not load. The first run must be online "
                "to download the Whisper model; also check that faster-whisper "
                "and sounddevice are installed."
            )
        self.jarvis = Jarvis()

    def listen(self) -> str:
        from openjarvis.speech.voice_io import record_until_silence

        audio = record_until_silence()
        result = self.ears.get_stt_backend().transcribe(
            audio, format="wav", language=self.ears.get_stt_language()
        )
        text = (result.text or "").strip()
        # People often say "Hey Jarvis, what's..." in one breath; drop the name.
        return re.sub(r"^\W*(hey\W+)?jarvis\W*", "", text, flags=re.I).strip()

    def handle(self) -> None:
        chime()
        question = self.listen()
        if not question:
            log.info("Heard the wake word but no question.")
            return
        log.info("You: %s", question)
        try:
            answer = self.jarvis.ask(question)
        except Exception as exc:
            log.exception("Jarvis failed")
            answer = f"Sorry, something went wrong. {exc}"
        log.info("Jarvis: %s", answer)
        self.voice.say(answer)


def main() -> int:
    parser = argparse.ArgumentParser(description="Always-on 'Hey Jarvis' for OpenJarvis")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="0-1, higher means fewer false wake-ups (default 0.5)")
    parser.add_argument("--check", action="store_true", help="load everything and exit")
    args = parser.parse_args()

    log.info("Loading wake word, speech recognition and Jarvis...")
    model = load_wake_model()
    assistant = Assistant()
    # Warm up speech recognition (downloads the Whisper model on first run).
    assistant.ears.get_stt_backend().transcribe(
        _silent_wav(), format="wav", language=assistant.ears.get_stt_language()
    )
    if args.check:
        log.info("Everything loaded. Hey Jarvis is ready.")
        return 0

    log.info('Ready. Say "Hey Jarvis".')
    while True:
        try:
            score = wait_for_wake_word(model, args.threshold)
            log.info("Wake word heard (score %.2f)", score)
            assistant.handle()
        except KeyboardInterrupt:
            return 0
        except Exception:
            # Mic unplugged, sleep/wake, etc. Wait and keep going.
            log.exception("Listener error; retrying in 5 s")
            time.sleep(5)


def _silent_wav() -> bytes:
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * SAMPLE_RATE)
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
