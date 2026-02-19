#!/usr/bin/env python3
"""
MRAgent — Lightweight AI Agent
A Jarvis-like AI assistant powered by free NVIDIA NIM APIs.

Usage:
    python main.py                     # CLI + Web on port 16226 (default)
    python main.py --mode cli          # CLI only
    python main.py --mode web          # Browser UI only
    python main.py --mode telegram     # Telegram bot
    python main.py --voice             # CLI with voice input/output
    python main.py --debug             # Verbose logging to terminal

Created: 2026-02-15
Repository: https://github.com/bonzainsights/MRAgent
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger
from config.settings import (
    DEFAULTS, validate_config, save_config_backup, SYSTEM_INFO
)
from agents.vivrecard import VivreCard
from core.poneglyph import Poneglyph

logger = get_logger("main")


# ──────────────────────────────────────────────
# Version
# ──────────────────────────────────────────────
__version__ = "0.1.0"


# ──────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────
BANNER = r"""
 ╔══════════════════════════════════════════════╗
 ║                                              ║
 ║   ███╗   ███╗██████╗  █████╗  ██████╗       ║
 ║   ████╗ ████║██╔══██╗██╔══██╗██╔════╝       ║
 ║   ██╔████╔██║██████╔╝███████║██║  ███╗      ║
 ║   ██║╚██╔╝██║██╔══██╗██╔══██║██║   ██║      ║
 ║   ██║ ╚═╝ ██║██║  ██║██║  ██║╚██████╔╝      ║
 ║   ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝       ║
 ║                                              ║
 ║   MRAgent v{version}                           ║
 ║   Your Lightweight AI Assistant              ║
 ║   Powered by NVIDIA NIM                      ║
 ║                                              ║
 ╚══════════════════════════════════════════════╝
"""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="MRAgent — Lightweight AI Agent powered by free NVIDIA NIM APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                   Start in CLI mode\n"
            "  python main.py --mode web        Start browser UI\n"
            "  python main.py --mode telegram   Start Telegram bot\n"
            "  python main.py --voice           Enable voice I/O\n"
            "  python main.py --model kimi-k2.5 Use specific model\n"
        ),
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["cli", "web", "both", "telegram"],
        default="both",
        help="Interface mode: both (cli+web, default), cli, web, telegram",
    )
    parser.add_argument(
        "--voice", "-v",
        action="store_true",
        default=False,
        help="Enable voice input/output",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override default LLM model (e.g. kimi-k2.5, gemma-3n, qwen3-coder)",
    )
    parser.add_argument(
        "--model-mode",
        choices=["auto", "thinking", "fast", "code"],
        default="auto",
        help="Model selection mode (default: auto)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=16226,
        help="Port for web UI (default: 16226)",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"MRAgent v{__version__}",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging",
    )
    return parser.parse_args()


def print_startup_info(args: argparse.Namespace):
    """Print startup banner and configuration summary."""
    print(BANNER.format(version=__version__))

    # Validate API keys
    report = validate_config()

    # Print essential info via print() (console logs are suppressed by default)
    print(f"  System:  {SYSTEM_INFO['os']} {SYSTEM_INFO['platform']}")
    print(f"  Python:  {SYSTEM_INFO['python_version']}")
    print(f"  Mode:    {args.mode} | Voice: {'ON' if args.voice else 'OFF'}")
    if report["valid"]:
        print(f"  Models:  {', '.join(report['valid'])}")
    if report["missing"]:
        print(f"  ⚠ Missing API keys: {', '.join(report['missing'])}")
    for warning in report["warnings"]:
        print(f"  ⚠ {warning}")
    print(f"  Logs:    data/logs/mragent.log")
    print()

    # Still log to file for tracking
    logger.info(f"MRAgent v{__version__} starting — mode={args.mode}")
    logger.info(f"System: {SYSTEM_INFO['os']} {SYSTEM_INFO['platform']}")
    logger.info(f"Models: {', '.join(report['valid'])}")

    # Save config snapshot at startup
    backup_path = save_config_backup()
    logger.debug(f"Config backup saved: {backup_path}")

    # Start VivreCard Scheduler
    vivrecard = VivreCard()
    vivrecard.start()
    logger.info("VivreCard Scheduler started in background")


def run_cli(args: argparse.Namespace):
    """Launch the CLI interface."""
    logger.info("Starting CLI interface...")
    try:
        from ui.cli import CLIInterface
        cli = CLIInterface(
            voice_enabled=args.voice,
            model_override=args.model,
            model_mode=args.model_mode,
        )
        cli.run()
    except ImportError as e:
        logger.error(f"CLI dependencies missing: {e}")
        logger.info("Install with: pip install rich prompt-toolkit")
        sys.exit(1)


def run_web(args: argparse.Namespace):
    """Launch the web UI."""
    logger.info(f"Starting web UI on port {args.port}...")
    try:
        from ui.web import create_app
        app = create_app()
        app.run(host="0.0.0.0", port=args.port, debug=args.debug)
    except ImportError as e:
        logger.error(f"Web dependencies missing: {e}")
        logger.info("Install with: pip install flask")
        sys.exit(1)


def run_telegram(args: argparse.Namespace):
    """Launch the Telegram bot."""
    logger.info("Starting Telegram bot...")
    try:
        from ui.telegram_bot import TelegramBot
        bot = TelegramBot()
        bot.run()
    except ImportError as e:
        logger.error(f"Telegram dependencies missing: {e}")
        logger.info("Install with: pip install python-telegram-bot")
        sys.exit(1)


def run_both(args: argparse.Namespace):
    """Launch Web UI in background + CLI in foreground simultaneously."""
    import threading

    print("  🌐 Starting Web UI in background on port %d..." % args.port)
    logger.info(f"Dual mode: starting web UI on port {args.port} + CLI")

    def _web_thread():
        try:
            from ui.web import create_app
            app = create_app()
            # Suppress Flask's default request logging in dual mode
            import logging as _logging
            _logging.getLogger("werkzeug").setLevel(_logging.WARNING)
            app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"Web UI failed: {e}")

    web_thread = threading.Thread(target=_web_thread, daemon=True)
    web_thread.start()

    print(f"  ✅ Web UI running at http://localhost:{args.port}")
    print()

    # Launch Telegram Bot if token is present
    import os
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        logger.info("Checks found TELEGRAM_BOT_TOKEN, starting Telegram bot in background...")
        print("  🤖 Starting Telegram Bot in background...")
        
        def _telegram_thread():
            try:
                # Suppress telegram logs to avoid cluttering CLI
                import logging as _logging
                _logging.getLogger("httpx").setLevel(_logging.WARNING)
                _logging.getLogger("telegram").setLevel(_logging.WARNING)
                
                from ui.telegram_bot import TelegramBot
                bot = TelegramBot()
                # Run async loop for telegram
                import asyncio
                asyncio.run(bot.run_async())
            except Exception as e:
                logger.error(f"Telegram Bot failed: {e}")

        telegram_thread = threading.Thread(target=_telegram_thread, daemon=True)
        telegram_thread.start()
        print("  ✅ Telegram Bot running")

    # Run CLI in foreground
    run_cli(args)


def main():
    """Main entry point."""
    
    # Initialize Poneglyph (The Guardian)
    poneglyph = Poneglyph()

    # Handle 'doctor' command early
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        if "--fix" in sys.argv:
            poneglyph.run_fixer()
        else:
            poneglyph.check_health()
            poneglyph.report()
        return

    # Poneglyph Guardian Check before startup
    if not poneglyph.check_health():
         logger.warning("System health check reported issues. Run 'python main.py doctor' for details.")

    args = parse_args()

    # Set debug logging if requested — shows all logs in terminal too
    if args.debug:
        DEFAULTS["log_level"] = "DEBUG"
        import logging
        # Set root mragent logger to DEBUG
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)
        # Also configure any future loggers
        logging.getLogger("mragent").setLevel(logging.DEBUG)

    # Override settings from args
    if args.model:
        DEFAULTS["default_llm"] = args.model
    if args.model_mode:
        DEFAULTS["model_selection_mode"] = args.model_mode
    DEFAULTS["voice_enabled"] = args.voice
    DEFAULTS["web_port"] = args.port

    print_startup_info(args)
    
    # Test Poneglyph LLM Diagnostics
    # Launch selected interface
    try:
        if args.mode == "both":
            run_both(args)
        else:
            mode_runners = {
                "cli": run_cli,
                "web": run_web,
                "telegram": run_telegram,
            }
            runner = mode_runners[args.mode]
            runner(args)
    except KeyboardInterrupt:
        print("\nMRAgent shutting down. Goodbye! 👋")
        logger.info("MRAgent shutting down via Ctrl+C")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        # Use Poneglyph to analyze and suggest fixes
        poneglyph.analyze_error(e, context="main execution loop")
        sys.exit(1)


if __name__ == "__main__":
    main()
