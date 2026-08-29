"""Local text-to-speech support for the Orbit desktop service."""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Any


class VoiceSynthesisError(RuntimeError):
    """Raised when Orbit cannot create local speech audio."""


class LocalVoice:
    """Lazily load a Piper model and return spoken WAV bytes."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._voice: Any | None = None

    def synthesize(self, text: str) -> bytes:
        if not self.model_path.is_file():
            raise VoiceSynthesisError(f"Voice model not found: {self.model_path}")

        try:
            from piper import PiperVoice
            from piper.config import SynthesisConfig
        except ImportError as exc:
            raise VoiceSynthesisError("The local Piper voice engine is not installed.") from exc

        try:
            if self._voice is None:
                self._voice = PiperVoice.load(str(self.model_path))

            audio = io.BytesIO()
            with wave.open(audio, "wb") as wav_file:
                # The frontend brightens playback; a slower source preserves a natural pace.
                self._voice.synthesize_wav(
                    text,
                    wav_file,
                    syn_config=SynthesisConfig(length_scale=1.15),
                )
            return audio.getvalue()
        except Exception as exc:
            raise VoiceSynthesisError("The local voice could not create audio.") from exc
