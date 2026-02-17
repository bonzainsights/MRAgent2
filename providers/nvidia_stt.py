"""
MRAgent — NVIDIA Speech-to-Text Provider
Uses NVIDIA Riva gRPC API (Whisper Large v3) for audio transcription.

Created: 2026-02-15

Note: Requires nvidia-riva-client package.
Falls back gracefully if not installed.
"""

import time

from providers.base import STTProvider
from config.settings import NVIDIA_KEYS
from utils.logger import get_logger

logger = get_logger("providers.nvidia_stt")

# STT configuration
RIVA_STT_URI = "grpc.nvcf.nvidia.com:443"
WHISPER_FUNCTION_ID = "1598d209-5e27-4d3c-8079-4751568b1081"


class NvidiaSTTProvider(STTProvider):
    """
    NVIDIA Riva STT provider using Whisper Large v3 via gRPC.
    Transcribes audio (from mic or file) to text.
    """

    def __init__(self, rate_limit_rpm: int = 35):
        super().__init__(name="nvidia_stt", rate_limit_rpm=rate_limit_rpm)
        self._riva_available = False
        self._asr_service = None
        self._init_riva()

    def _init_riva(self):
        """Initialize Riva client. Graceful fallback if not installed."""
        try:
            import riva.client
            self._riva = riva.client
            self._riva_available = True
            self.logger.info("NVIDIA Riva STT client loaded")
        except ImportError:
            self._riva_available = False
            self.logger.warning(
                "nvidia-riva-client not installed. STT disabled. "
                "Install with: pip install nvidia-riva-client"
            )

    def _get_service(self):
        """Get or create the ASR service connection."""
        if self._asr_service is not None:
            return self._asr_service

        if not self._riva_available:
            raise RuntimeError("nvidia-riva-client not installed")

        api_key = NVIDIA_KEYS.get("whisper_lv3", "")
        if not api_key:
            raise ValueError("NVIDIA_WHISPER_LV3 API key not set")

        auth = self._riva.Auth(
            uri=RIVA_STT_URI,
            use_ssl=True,
            metadata_args=[
                ["function-id", WHISPER_FUNCTION_ID],
                ["authorization", f"Bearer {api_key}"],
            ],
        )
        self._asr_service = self._riva.ASRService(auth)
        self.logger.info("Connected to NVIDIA Riva STT service")
        return self._asr_service

    def speech_to_text(self, audio_bytes: bytes,
                       language: str = "en-US",
                       sample_rate: int = 16000) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw PCM audio data (16-bit, mono)
            language: Language code
            sample_rate: Audio sample rate in Hz

        Returns:
            Transcribed text string
        """
        if not self._riva_available:
            raise RuntimeError("STT not available — install nvidia-riva-client")

        self.logger.info(f"STT: transcribing {len(audio_bytes)} bytes of audio")
        start_time = time.time()

        def _make_request():
            service = self._get_service()
            config = self._riva.RecognitionConfig(
                encoding=self._riva.AudioEncoding.LINEAR_PCM,
                language_code=language,
                max_alternatives=1,
                enable_automatic_punctuation=True,
                sample_rate_hertz=sample_rate,
                audio_channel_count=1,
            )
            response = service.offline_recognize(audio_bytes, config)
            return response

        try:
            response = self._retry_call(_make_request)
            duration_ms = (time.time() - start_time) * 1000

            # Extract transcript
            transcript = ""
            for result in response.results:
                if result.alternatives:
                    transcript += result.alternatives[0].transcript + " "

            transcript = transcript.strip()
            self._track_call("stt/recognize", "whisper-lv3", duration_ms, status="ok")
            self.logger.info(f"STT result: '{transcript[:80]}...' ({duration_ms:.0f}ms)")

            return transcript

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._track_call("stt/recognize", "whisper-lv3", duration_ms, status=f"error: {e}")
            raise

    def create_streaming_config(self, language: str = "en-US",
                                sample_rate: int = 16000):
        """
        Create a streaming recognition config for real-time transcription.

        Returns:
            StreamingRecognitionConfig for use with streaming API
        """
        if not self._riva_available:
            raise RuntimeError("STT not available — install nvidia-riva-client")

        return self._riva.StreamingRecognitionConfig(
            config=self._riva.RecognitionConfig(
                encoding=self._riva.AudioEncoding.LINEAR_PCM,
                language_code=language,
                max_alternatives=1,
                enable_automatic_punctuation=True,
                sample_rate_hertz=sample_rate,
                audio_channel_count=1,
            ),
            interim_results=True,
        )

    @property
    def available(self) -> bool:
        """Check if STT is available."""
        return self._riva_available and bool(NVIDIA_KEYS.get("whisper_lv3"))
