"""
MRAgent — NVIDIA Text-to-Speech Provider
Uses NVIDIA Riva gRPC API (Magpie TTS) for natural voice synthesis.

Created: 2026-02-15

Note: Requires nvidia-riva-client package.
Falls back gracefully if not installed.
"""

import time
import struct
import wave
from pathlib import Path

from providers.base import TTSProvider
from config.settings import NVIDIA_KEYS, DATA_DIR
from utils.logger import get_logger
from utils.helpers import get_timestamp_short

logger = get_logger("providers.nvidia_tts")

# TTS configuration
RIVA_TTS_URI = "grpc.nvcf.nvidia.com:443"
MAGPIE_FUNCTION_ID = "0149dedb-2be8-4195-b9a0-e57e0e14f972"

# Available voices
VOICES = {
    "female-1": "English-US.Female-1",
    "male-1": "English-US.Male-1",
    "female-2": "English-US.Female-2",
    "default": "English-US.Female-1",
}


class NvidiaTTSProvider(TTSProvider):
    """
    NVIDIA Riva TTS provider using Magpie TTS model via gRPC.
    Converts text to natural-sounding speech.
    """

    def __init__(self, rate_limit_rpm: int = 35):
        super().__init__(name="nvidia_tts", rate_limit_rpm=rate_limit_rpm)
        self._riva_available = False
        self._tts_service = None
        self._init_riva()

    def _init_riva(self):
        """Initialize Riva client. Graceful fallback if not installed."""
        try:
            import riva.client
            self._riva = riva.client
            self._riva_available = True
            self.logger.info("NVIDIA Riva TTS client loaded")
        except ImportError:
            self._riva_available = False
            self.logger.warning(
                "nvidia-riva-client not installed. TTS disabled. "
                "Install with: pip install nvidia-riva-client"
            )

    def _get_service(self):
        """Get or create the TTS service connection."""
        if self._tts_service is not None:
            return self._tts_service

        if not self._riva_available:
            raise RuntimeError("nvidia-riva-client not installed")

        api_key = NVIDIA_KEYS.get("magpie_tts", "")
        if not api_key:
            raise ValueError("NVIDIA_MAGPIE_TTS API key not set")

        auth = self._riva.Auth(
            uri=RIVA_TTS_URI,
            use_ssl=True,
            metadata_args=[
                ["function-id", MAGPIE_FUNCTION_ID],
                ["authorization", f"Bearer {api_key}"],
            ],
        )
        self._tts_service = self._riva.SpeechSynthesisService(auth)
        self.logger.info("Connected to NVIDIA Riva TTS service")
        return self._tts_service

    def text_to_speech(self, text: str, voice: str = "default",
                       language: str = "en-US",
                       sample_rate: int = 44100) -> bytes:
        """
        Convert text to speech audio using Magpie TTS.

        Args:
            text: Text to synthesize
            voice: Voice name (female-1, male-1, female-2, or full Riva voice name)
            language: Language code (e.g. en-US)
            sample_rate: Audio sample rate in Hz

        Returns:
            Raw PCM audio bytes
        """
        if not self._riva_available:
            raise RuntimeError("TTS not available — install nvidia-riva-client")

        # Resolve voice name
        voice_name = VOICES.get(voice, voice)
        self.logger.info(f"TTS: '{text[:50]}...' voice={voice_name}")

        start_time = time.time()

        def _make_request():
            service = self._get_service()
            response = service.synthesize(
                text,
                voice_name=voice_name,
                language_code=language,
                encoding=self._riva.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate,
            )
            return response.audio

        try:
            audio_bytes = self._retry_call(_make_request)
            duration_ms = (time.time() - start_time) * 1000

            self._track_call("tts/synthesize", "magpie-tts", duration_ms, status="ok")
            self.logger.info(f"TTS complete: {len(audio_bytes)} bytes ({duration_ms:.0f}ms)")

            return audio_bytes

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._track_call("tts/synthesize", "magpie-tts", duration_ms, status=f"error: {e}")
            raise

    def synthesize_to_file(self, text: str, filepath: Path = None,
                           voice: str = "default", language: str = "en-US",
                           sample_rate: int = 44100) -> Path:
        """
        Synthesize text and save as a WAV file.

        Returns:
            Path to the saved WAV file
        """
        audio_bytes = self.text_to_speech(text, voice, language, sample_rate)

        if filepath is None:
            timestamp = get_timestamp_short()
            filepath = DATA_DIR / "audio" / f"tts_{timestamp}.wav"

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Write as WAV
        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)

        self.logger.info(f"TTS saved to: {filepath}")
        return filepath

    @property
    def available(self) -> bool:
        """Check if TTS is available (riva client installed + API key set)."""
        return self._riva_available and bool(NVIDIA_KEYS.get("magpie_tts"))

    def list_voices(self) -> list[dict]:
        """Return available voice options."""
        return [
            {"name": k, "riva_name": v}
            for k, v in VOICES.items()
        ]
