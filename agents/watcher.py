"""
MRAgent — Eagle Eye Watcher
Real-time screen monitoring agent with low-latency computer vision.

Uses:
1. Smart Diffing (only analyze if screen changes)
2. Lightweight Vision Model (Llama 3.2 11B)
3. Edge TTS + System Audio for feedback

Created: 2026-02-19
"""

import time
import asyncio
import subprocess
import threading
from pathlib import Path
from tempfile import gettempdir

from tools.screen import ScreenCaptureTool
from providers.nvidia_llm import NvidiaLLMProvider
from providers.tts import text_to_speech
from utils.logger import get_logger

logger = get_logger("agents.eagle_eye")

class EagleEyeWatcher:
    def __init__(self, interval: float = 3.0, diff_threshold: float = 5.0):
        self.interval = interval
        self.diff_threshold = diff_threshold
        self.running = False
        
        self.screen_tool = ScreenCaptureTool()
        self.llm = NvidiaLLMProvider()
        
        self.last_frame_b64 = None
        self.last_analysis_time = 0
        
        # Audio output path
        self.audio_file = Path(gettempdir()) / "mragent_eagle_eye.mp3"

    def start(self):
        """Start the monitoring loop."""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Eagle Eye activated! (Interval: {self.interval}s, Threshold: {self.diff_threshold}%)")
        print("\n🦅 Eagle Eye Watcher Active. Press Ctrl+C to stop.\n")
        
        # Run loop in a separate thread to keep main CLI responsive (if integrated)
        # But for standalone mode, we can just run blocking or async.
        # Here we'll run a blocking loop for simplicity in "Watch Mode".
        try:
            asyncio.run(self._loop())
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the loop."""
        self.running = False
        print("\n🦅 Eagle Eye deactivated.")

    async def _loop(self):
        """Main monitoring loop."""
        print("Waiting for screen activity...")
        
        while self.running:
            start_time = time.time()
            
            # 1. Capture for Diff (Low Quality, Grayscale)
            current_b64 = self.screen_tool.capture_as_base64(
                quality=50, resize_factor=0.5, grayscale=True
            )
            
            if not current_b64:
                logger.warning("Screen capture failed (returned None). Retrying...")
                await asyncio.sleep(self.interval)
                continue
            
            # 2. Check Diff
            diff = self.screen_tool.calculate_diff(self.last_frame_b64, current_b64)
            
            if diff > self.diff_threshold:
                logger.info(f"Movement detected! Diff: {diff:.1f}%")
                print(f"👁️  Activity detected ({diff:.1f}%) — Analyzing...")
                
                # 3. Analyze High-Res Frame
                await self._analyze_scene()
                
                # Update reference frame ONLY after successful analysis
                # to prevent analyzing the same change twice if it persists
                self.last_frame_b64 = current_b64
                self.last_analysis_time = time.time()
            else:
                # No change, just update reference to handle slow drift?
                # No, keep old reference to detect cumulative change.
                pass

            # Update last frame if it was None (first run)
            if self.last_frame_b64 is None:
                self.last_frame_b64 = current_b64

            # Sleep remaining time
            elapsed = time.time() - start_time
            sleep_time = max(0.1, self.interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _analyze_scene(self):
        """Send high-quality frame to VLM and speak result."""
        try:
            # Capture High-Res (but resized to 1024px max for speed)
            hq_b64 = self.screen_tool.capture_as_base64(
                quality=80, resize_factor=0.8, grayscale=False
            )
            
            # Prepare message
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe what just happened on my screen in one short sentence. Start with 'I see...'"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{hq_b64}"}
                        }
                    ]
                }
            ]
            
            # Call Llama 3.2 Vision
            # Note: We must ensure this model ID is mapped correctly in settings
            response = self.llm.chat(
                messages, 
                model="llama-3.2-11b-vision",
                stream=False,
                max_tokens=100
            )
            
            text = response["content"]
            print(f"🦅 {text}")
            
            # Speak
            await self._speak(text)
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            print(f"❌ Analysis failed: {e}")

    async def _speak(self, text: str):
        """Generate and play TTS."""
        path = await text_to_speech(text, str(self.audio_file))
        if path:
            self._play_audio(path)

    def _play_audio(self, path: str):
        """Play audio file using system CLI tools."""
        try:
            if sys.platform == "darwin":
                subprocess.run(["afplay", path], check=True)
            elif sys.platform == "linux":
                subprocess.run(["mpg123", path], check=True)
            # Windows omitted for brevity, can add later
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")

if __name__ == "__main__":
    # Test run
    import sys
    watcher = EagleEyeWatcher()
    watcher.start()
