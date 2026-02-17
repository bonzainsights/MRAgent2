"""
MRAgent — Shared Helper Utilities
Common functions used across the project.

Created: 2026-02-15
"""

import os
import time
import base64
import hashlib
import platform
from pathlib import Path
from datetime import datetime
from functools import wraps


def get_timestamp() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now().isoformat()


def get_timestamp_short() -> str:
    """Return current timestamp in compact format for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_system_context() -> str:
    """Return a context string about the current system for prompt injection."""
    cwd = os.getcwd()
    user = os.getenv("USER", os.getenv("USERNAME", "unknown"))
    home = str(Path.home())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

    return (
        f"Current Time: {now}\n"
        f"OS: {platform.system()} {platform.release()}\n"
        f"User: {user}\n"
        f"Home: {home}\n"
        f"CWD: {cwd}"
    )


def truncate(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def base64_to_file(b64_data: str, filepath: Path) -> Path:
    """Decode a base64 string and save to file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(b64_data)
    filepath.write_bytes(raw)
    return filepath


def file_to_base64(filepath: Path) -> str:
    """Read a file and return its base64 encoding."""
    return base64.b64encode(Path(filepath).read_bytes()).decode("utf-8")


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate: ~4 characters per token (OpenAI-ish).
    Good enough for context window management without importing tiktoken.
    """
    return max(1, len(text) // 4)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0,
                       max_delay: float = 30.0):
    """
    Decorator for retrying functions with exponential backoff.

    Usage:
        @retry_with_backoff(max_retries=3)
        def call_api(): ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def generate_id(prefix: str = "") -> str:
    """Generate a short unique ID based on timestamp + random bytes."""
    raw = f"{time.time()}-{os.urandom(4).hex()}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"{prefix}{short_hash}" if prefix else short_hash


def format_file_size(size_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
