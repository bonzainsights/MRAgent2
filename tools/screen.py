"""
MRAgent — Screen Capture Tool
Lightweight cross-platform screenshot via pyautogui.

Created: 2026-02-15
"""

import base64
import io
import time

from tools.base import Tool
from config.settings import IMAGES_DIR
from utils.helpers import get_timestamp_short
from utils.logger import get_logger

logger = get_logger("tools.screen")


class ScreenCaptureTool(Tool):
    """Capture a screenshot of the current screen."""

    name = "capture_screen"
    description = (
        "Take a screenshot of the current screen. Returns the image as base64 "
        "and saves it locally. Use with a vision model to understand screen content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "region": {
                "type": "object",
                "description": "Optional region to capture: {x, y, width, height}",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                },
            },
            "quality": {
                "type": "integer",
                "description": "JPEG quality 1-95, lower = smaller file (default: 60)",
            },
        },
        "required": [],
    }

    def execute(self, region: dict = None, quality: int = 60) -> str:
        try:
            import pyautogui
        except ImportError:
            return "❌ pyautogui not installed. Install with: pip install pyautogui"

        self.logger.info("Capturing screenshot...")
        start_time = time.time()

        try:
            # Capture
            if region:
                screenshot = pyautogui.screenshot(
                    region=(region["x"], region["y"],
                            region["width"], region["height"])
                )
            else:
                screenshot = pyautogui.screenshot()

            # Compress to JPEG for smaller size
            buffer = io.BytesIO()
            screenshot.save(buffer, format="JPEG", quality=quality)
            img_bytes = buffer.getvalue()
            b64 = base64.b64encode(img_bytes).decode("utf-8")

            # Save locally
            timestamp = get_timestamp_short()
            filepath = IMAGES_DIR / f"screen_{timestamp}.jpg"
            filepath.write_bytes(img_bytes)

            duration_ms = (time.time() - start_time) * 1000
            size_kb = len(img_bytes) / 1024

            self.logger.info(f"Screenshot saved: {filepath} ({size_kb:.1f}KB, {duration_ms:.0f}ms)")

            return (
                f"📸 Screenshot captured ({screenshot.size[0]}x{screenshot.size[1]}, "
                f"{size_kb:.1f}KB)\n"
                f"Saved: {filepath}\n"
                f"Base64 length: {len(b64)} chars"
            )

        except Exception as e:
            return f"❌ Error capturing screen: {e}"

    def capture_as_base64(self, quality: int = 60) -> str | None:
        """Capture screen and return raw base64 (for vision model input)."""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="JPEG", quality=quality)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            self.logger.error(f"Screen capture failed: {e}")
            return None
