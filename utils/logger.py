"""
MRAgent — Logging System
Provides timestamped, dual-output (console + file) logging with per-module loggers.

Created: 2026-02-15

Usage:
    from utils.logger import get_logger
    logger = get_logger("providers.nvidia_llm")
    logger.info("Connected to NVIDIA NIM API")
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Import paths from config — but handle circular import gracefully
try:
    from config.settings import LOGS_DIR, DEFAULTS
except ImportError:
    LOGS_DIR = Path(__file__).parent.parent / "data" / "logs"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULTS = {"log_level": "INFO"}


# ──────────────────────────────────────────────
# Custom Formatter
# ──────────────────────────────────────────────
class MRAgentFormatter(logging.Formatter):
    """Custom formatter: [2026-02-15 23:45:12] [MODULE] [LEVEL] message"""

    COLORS = {
        "DEBUG":    "\033[36m",    # Cyan
        "INFO":     "\033[32m",    # Green
        "WARNING":  "\033[33m",    # Yellow
        "ERROR":    "\033[31m",    # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        module = record.name.split(".")[-1] if "." in record.name else record.name
        level = record.levelname

        if self.use_colors:
            color = self.COLORS.get(level, "")
            return f"\033[90m[{timestamp}]\033[0m [{module}] {color}[{level}]{self.RESET} {record.getMessage()}"
        else:
            return f"[{timestamp}] [{module}] [{level}] {record.getMessage()}"


# ──────────────────────────────────────────────
# Logger Setup
# ──────────────────────────────────────────────
_loggers = {}
_file_handler = None


def _get_file_handler() -> RotatingFileHandler:
    """Create or return the shared file handler (rotating, max 5MB per file, keep 3)."""
    global _file_handler
    if _file_handler is None:
        log_file = LOGS_DIR / "mragent.log"
        _file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        _file_handler.setFormatter(MRAgentFormatter(use_colors=False))
        _file_handler.setLevel(logging.DEBUG)  # File captures everything
    return _file_handler


def get_logger(name: str = "mragent") -> logging.Logger:
    """
    Get a named logger with console (colorized) + file output.

    Args:
        name: Logger name, typically "module.submodule"
              e.g. "providers.nvidia_llm", "agents.core", "tools.terminal"

    Returns:
        Configured logging.Logger instance
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(f"mragent.{name}")
    logger.setLevel(getattr(logging, DEFAULTS.get("log_level", "INFO")))
    logger.propagate = False  # Don't bubble up to root logger

    # Console handler (colorized) — only WARNING+ to keep terminal clean
    # All details (INFO/DEBUG) go to the log file at data/logs/mragent.log
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(MRAgentFormatter(use_colors=True))
        console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)

    # File handler (shared across all loggers)
    file_handler = _get_file_handler()
    if file_handler not in logger.handlers:
        logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def log_api_call(logger: logging.Logger, provider: str, endpoint: str,
                 model: str = "", duration_ms: float = 0, status: str = "ok",
                 tokens_used: int = 0):
    """
    Structured log for API calls — easy to track usage and debug.

    Example output:
    [2026-02-15 23:45:12] [nvidia_llm] [INFO] API_CALL provider=nvidia endpoint=chat model=kimi-k2.5 duration=234ms tokens=150 status=ok
    """
    parts = [
        f"API_CALL provider={provider}",
        f"endpoint={endpoint}",
    ]
    if model:
        parts.append(f"model={model}")
    if duration_ms:
        parts.append(f"duration={duration_ms:.0f}ms")
    if tokens_used:
        parts.append(f"tokens={tokens_used}")
    parts.append(f"status={status}")

    logger.info(" ".join(parts))


def log_tool_execution(logger: logging.Logger, tool_name: str,
                       args: dict = None, result_preview: str = "",
                       duration_ms: float = 0, success: bool = True):
    """
    Structured log for tool executions.

    Example output:
    [2026-02-15 23:45:12] [tools] [INFO] TOOL_EXEC tool=terminal args={'command': 'ls'} duration=45ms success=True result="file1.py\nfile2.py..."
    """
    parts = [
        f"TOOL_EXEC tool={tool_name}",
    ]
    if args:
        # Truncate args to avoid huge log lines
        args_str = str(args)[:200]
        parts.append(f"args={args_str}")
    if duration_ms:
        parts.append(f"duration={duration_ms:.0f}ms")
    parts.append(f"success={success}")
    if result_preview:
        preview = result_preview[:100].replace("\n", "\\n")
        parts.append(f'result="{preview}"')

    logger.info(" ".join(parts))
