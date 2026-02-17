"""
MRAgent — NVIDIA Image Generation Provider
Generates images via NVIDIA NIM REST API (Stable Diffusion 3 Medium & FLUX.1-dev).

Created: 2026-02-15
Updated: 2026-02-16 — Fixed endpoints and payload format
"""

import time
import base64
import requests
from pathlib import Path

from providers.base import ImageProvider
from config.settings import NVIDIA_KEYS, IMAGES_DIR
from utils.logger import get_logger
from utils.helpers import get_timestamp_short

logger = get_logger("providers.nvidia_image")

# NVIDIA NIM image generation endpoints — verified from build.nvidia.com (2026-02-16)
# Note: SD 3.5 Large has NO hosted API (download only). Using SD 3 Medium instead.
IMAGE_MODELS = {
    "sd-3-medium": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-3-medium",
        "key": "sd_35_large",
        "payload_format": "sd3",  # uses prompt, cfg_scale, aspect_ratio, steps, negative_prompt, seed
    },
    "flux-dev": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev",
        "key": "flux_dev",
        "payload_format": "flux",  # uses prompt, mode, cfg_scale, width, height, steps, seed
    },
}


class NvidiaImageProvider(ImageProvider):
    """
    NVIDIA NIM Image Generation provider.
    Uses REST API to generate images from text prompts.
    Returns base64-encoded images and saves them locally.
    """

    def __init__(self, rate_limit_rpm: int = 35):
        super().__init__(name="nvidia_image", rate_limit_rpm=rate_limit_rpm)
        self.logger.info("NVIDIA Image provider initialized")

    def generate_image(self, prompt: str, model: str = "flux-dev",
                       width: int = 1024, height: int = 1024,
                       steps: int = 50, cfg_scale: float = 5.0,
                       seed: int = 0, negative_prompt: str = "") -> dict:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the desired image
            model: "sd-3-medium" or "flux-dev" (default: flux-dev)
            width/height: Image dimensions (for flux-dev only)
            steps: Diffusion steps (more = higher quality, slower)
            cfg_scale: How closely to follow the prompt (1-20)
            seed: Random seed (0 = random)
            negative_prompt: What to avoid (sd-3-medium only)

        Returns:
            {"base64": str, "seed": int, "filepath": Path, "model": str}
        """
        if model not in IMAGE_MODELS:
            raise ValueError(f"Unknown image model: {model}. Available: {list(IMAGE_MODELS.keys())}")

        model_info = IMAGE_MODELS[model]
        endpoint = model_info["endpoint"]
        key_name = model_info["key"]
        api_key = NVIDIA_KEYS.get(key_name, "")

        if not api_key:
            raise ValueError(f"API key not set for {model} (env: NVIDIA_{key_name.upper()})")

        self.logger.info(f"Generating image: model={model}, prompt='{prompt[:60]}...'")
        start_time = time.time()

        def _make_request():
            # Build payload based on model format
            if model_info["payload_format"] == "flux":
                payload = {
                    "prompt": prompt,
                    "mode": "base",
                    "cfg_scale": cfg_scale,
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "seed": seed,
                }
            else:  # sd3 format
                payload = {
                    "prompt": prompt,
                    "cfg_scale": cfg_scale,
                    "aspect_ratio": "16:9",
                    "steps": steps,
                    "seed": seed,
                    "negative_prompt": negative_prompt or "",
                }

            resp = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
                timeout=120,  # Image gen can be slow
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = self._retry_call(_make_request)
            duration_ms = (time.time() - start_time) * 1000

            # Extract image — NVIDIA returns in 'artifacts' array
            artifacts = data.get("artifacts", [])
            if not artifacts:
                # Some models return in 'image' key instead
                if "image" in data:
                    b64_image = data["image"]
                    result_seed = data.get("seed", seed)
                else:
                    raise ValueError("No image data returned from API")
            else:
                b64_image = artifacts[0].get("base64", "")
                result_seed = artifacts[0].get("seed", seed)

            # Save image to disk
            timestamp = get_timestamp_short()
            filename = f"img_{timestamp}_{model.replace('.', '_').replace('-', '_')}.png"
            filepath = IMAGES_DIR / filename
            filepath.write_bytes(base64.b64decode(b64_image))

            self._track_call("image/generate", model, duration_ms, status="ok")
            self.logger.info(f"Image saved: {filepath} ({duration_ms:.0f}ms)")

            return {
                "base64": b64_image,
                "seed": result_seed,
                "filepath": filepath,
                "model": model,
                "prompt": prompt,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._track_call("image/generate", model, duration_ms, status=f"error: {e}")
            raise

    def list_models(self) -> list[dict]:
        """Return available image generation models."""
        available = []
        for model, info in IMAGE_MODELS.items():
            key_name = info["key"]
            has_key = bool(NVIDIA_KEYS.get(key_name))
            available.append({
                "name": model,
                "endpoint": info["endpoint"],
                "available": has_key,
            })
        return available
