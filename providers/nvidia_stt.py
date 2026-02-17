"""
MRAgent — NVIDIA Speech-to-Text Provider
Uses NVIDIA NIM HTTP API (OpenAI-compatible) for audio transcription.
Avoids heavy dependencies like grpc/riva/ffmpeg.

Created: 2026-02-15
Updated: 2026-02-17 (Switch to HTTP API)
"""

import io
import time
from openai import OpenAI

from providers.base import STTProvider
from config.settings import NVIDIA_BASE_URL, get_api_key
from utils.logger import get_logger

logger = get_logger("providers.nvidia_stt")


class NvidiaSTTProvider(STTProvider):
    """
    NVIDIA NIM STT provider using OpenAI-compatible HTTP API.
    Transcribes audio to text using 'nvidia/whisper-large-v3'.
    """

    def __init__(self, rate_limit_rpm: int = 35):
        super().__init__(name="nvidia_stt", rate_limit_rpm=rate_limit_rpm)
        self.model = "nvidia/whisper-large-v3"
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize OpenAI client for NVIDIA NIM."""
        api_key = get_api_key("whisper_lv3")
        if api_key:
            self._client = OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=api_key,
            )
            self.logger.info("NVIDIA STT (HTTP) client initialized")
        else:
            self.logger.warning("NVIDIA_WHISPER_LV3 key not found. STT disabled.")

    def speech_to_text(self, audio_bytes: bytes,
                       language: str = "en",
                       sample_rate: int = 16000) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data (or OGG/MP3 bytes)
            language: Language code (ISO-639-1)
            sample_rate: Ignored for HTTP API (handled by server)

        Returns:
            Transcribed text string
        """
        if not self._client:
            raise RuntimeError("STT not available — missing API key")

        self.logger.info(f"STT: transcribing {len(audio_bytes)} bytes")
        start_time = time.time()

        def _make_request():
            # Wrap bytes in a named file-like object so OpenAI client detects it as a file
            # Telegram voice is usually OGG via Opus
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "voice.ogg" 

            return self._client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=language,
                response_format="json"
            )

        try:
            response = self._retry_call(_make_request)
            duration_ms = (time.time() - start_time) * 1000

            transcript = response.text
            
            self._track_call("audio/transcriptions", self.model, duration_ms, status="ok")
            self.logger.info(f"STT result: '{transcript[:80]}...' ({duration_ms:.0f}ms)")

            return transcript

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._track_call("audio/transcriptions", self.model, duration_ms, status=f"error: {e}")
            raise

    @property
    def available(self) -> bool:
        """Check if STT is available."""
        return self._client is not None
