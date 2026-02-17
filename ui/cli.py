"""
MRAgent — CLI Interface
Rich terminal interface with markdown rendering, commands, and streaming output.

Created: 2026-02-15
"""

import sys

from agents.core import AgentCore
from memory.chat_store import ChatStore
from utils.logger import get_logger

logger = get_logger("ui.cli")


# Slash commands
COMMANDS = {
    "/help":     "Show available commands",
    "/newchat":  "Start a new conversation",
    "/model":    "Set model (e.g. /model kimi-k2.5)",
    "/mode":     "Set mode: auto|thinking|fast|code",
    "/voice":    "Toggle voice on/off",
    "/image":    "Generate an image (e.g. /image sunset over mountains)",
    "/search":   "Search the web (e.g. /search python async)",
    "/screen":   "Capture and analyze the screen",
    "/history":  "Show recent chat history",
    "/stats":    "Show agent statistics",
    "/clear":    "Clear the screen",
    "/exit":     "Exit MRAgent",
}


def _try_import_rich():
    """Try to import rich for fancy output, fallback to plain text."""
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table
        from rich.live import Live
        return Console(), True
    except ImportError:
        return None, False


class CLIInterface:
    """
    Rich terminal interface for MRAgent.

    Features:
    - Markdown rendering of responses
    - Streaming output with live updates
    - Slash commands for actions
    - Token usage display
    """

    def __init__(self, voice_enabled: bool = False,
                 model_override: str = None, model_mode: str = "auto"):
        self.voice_enabled = voice_enabled
        self.console, self.has_rich = _try_import_rich()
        self.agent = AgentCore(model_mode=model_mode, model_override=model_override)
        self.chat_store = ChatStore()

        # Register streaming callback
        self.agent.on_response(self._on_event)
        self._current_response = ""
        self._last_model = self._mode_to_model(model_mode)  # Track current model

        logger.info("CLI interface initialized")

    def _on_event(self, event_type: str, data: str):
        """Handle streaming events from the agent."""
        if event_type == "delta":
            print(data, end="", flush=True)
            self._current_response += data
        elif event_type == "tool_start":
            self._print_info(data)
        elif event_type == "tool_result":
            self._print_info(data)
        elif event_type == "model":
            self._last_model = data  # Update prompt with actual model used
            self._print_dim(f"[model: {data}]")
        elif event_type == "info":
            self._print_info(data)
        elif event_type == "suggestion":
            self._print_info(data)

    def run(self):
        """Main input loop."""
        self._print_welcome()

        while True:
            try:
                user_input = self._get_input()

                if not user_input:
                    continue

                # Catch common words without slash — user-friendly aliases
                plain_lower = user_input.strip().lower()
                if plain_lower in ("help", "exit", "quit"):
                    user_input = f"/{plain_lower}"

                # Catch 'mode <x>' and 'model <x>' without slash
                if plain_lower.startswith("mode ") or plain_lower.startswith("model "):
                    user_input = f"/{plain_lower}"

                # Handle slash commands
                if user_input.startswith("/"):
                    should_continue = self._handle_command(user_input)
                    if not should_continue:
                        break
                    continue

                # Regular chat
                self._current_response = ""
                print()  # Blank line before response

                response = self.agent.chat(user_input, stream=True)

                # If streaming didn't produce output, print the response
                if not self._current_response:
                    self._print_response(response)

                print()  # Blank line after response

                # Save to chat store
                self.chat_store.save_message(self.agent.chat_id, "user", user_input)
                self.chat_store.save_message(self.agent.chat_id, "assistant", response)

                # Show context usage
                stats = self.agent.context_manager.get_stats()
                self._print_dim(
                    f"[tokens: {stats['used_tokens']:,}/{stats['max_tokens']:,} "
                    f"({stats['usage_ratio']}) | messages: {stats['active_messages']}]"
                )

            except KeyboardInterrupt:
                print("\n")
                self._print_info("Use /exit to quit, or press Ctrl+C again to force quit.")
                try:
                    continue
                except KeyboardInterrupt:
                    break
            except EOFError:
                break

        self._print_info("Goodbye! 👋")

    def _get_prompt_str(self) -> str:
        """Build a dynamic prompt showing model + mode."""
        mode = self.agent.model_selector.mode
        model = self._last_model or self._mode_to_model(mode)
        # Shorten model names for display
        short_model = model.replace("-instruct", "").replace("llama-3.3-70b", "llama-70b")
        return f"[{short_model} · {mode}] › "

    @staticmethod
    def _mode_to_model(mode: str) -> str:
        """Map mode to the default model name (for prompt display)."""
        from agents.model_selector import ModelSelector
        return ModelSelector.get_default_for_mode(mode) if mode != "auto" else "auto"

    def _get_input(self) -> str:
        """Get user input with dynamic prompt showing model + mode."""
        prompt_str = self._get_prompt_str()
        try:
            from prompt_toolkit import prompt
            from prompt_toolkit.history import InMemoryHistory
            if not hasattr(self, '_prompt_history'):
                self._prompt_history = InMemoryHistory()
            return prompt(prompt_str, history=self._prompt_history).strip()
        except ImportError:
            return input(prompt_str).strip()

    def _handle_command(self, cmd: str) -> bool:
        """Handle a slash command. Returns False to exit."""
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command == "/exit" or command == "/quit":
            return False

        elif command == "/help":
            self._print_help()

        elif command == "/newchat":
            self.agent.new_chat()
            self._print_info("🔄 New conversation started")

        elif command == "/model":
            if arg:
                from config.settings import MODEL_REGISTRY
                if arg in MODEL_REGISTRY:
                    self.agent.set_model(arg)
                    self._last_model = arg
                    self._print_info(f"✅ Model set to: {arg}")
                else:
                    self._print_info(f"❌ Unknown model: {arg}")
                    self._print_info(f"Available: {', '.join(k for k,v in MODEL_REGISTRY.items() if v.get('type')=='llm')}")
            else:
                from config.settings import MODEL_REGISTRY
                self._print_info("Available LLM models:")
                for name, info in MODEL_REGISTRY.items():
                    if info.get("type") == "llm":
                        cats = ", ".join(info.get("categories", []))
                        desc = info.get("description", "")
                        self._print_info(f"  {name:20s} [{cats:20s}] {desc}")
                self._print_info("\nUsage: model <name>  (e.g. model glm5)")

        elif command == "/mode":
            if arg in ("auto", "thinking", "fast", "code"):
                self.agent.set_model_mode(arg)
                self.agent.model_override = None  # Clear manual override
                self._last_model = self._mode_to_model(arg)
                self._print_info(f"✅ Switched to {arg} mode → {self._last_model}")
            else:
                from agents.model_selector import ModelSelector
                current = self.agent.model_selector.mode
                self._print_info(f"Current mode: {current}")
                self._print_info("")
                for m in ("thinking", "fast", "code"):
                    default = ModelSelector.get_default_for_mode(m)
                    options = ModelSelector.get_models_for_mode(m)
                    others = [o for o in options if o != default]
                    line = f"  {m:10s} → {default} (default)"
                    if others:
                        line += f"  | also: {', '.join(others)}"
                    self._print_info(line)
                self._print_info(f"  {'auto':10s} → picks best model per message")
                self._print_info("\nUsage: mode <name>  (e.g. mode fast)")

        elif command == "/voice":
            self.voice_enabled = not self.voice_enabled
            self._print_info(f"Voice: {'ON' if self.voice_enabled else 'OFF'}")

        elif command == "/image":
            if arg:
                # Parse optional --model flag
                model = "flux-dev"
                prompt = arg
                if arg.startswith("--sd "):
                    model = "sd-3-medium"
                    prompt = arg[5:].strip()
                elif arg.startswith("--flux "):
                    model = "flux-dev"
                    prompt = arg[7:].strip()
                if prompt:
                    self._generate_image(prompt, model=model)
                else:
                    self._print_info("Usage: /image [--flux|--sd] <description>")
            else:
                self._print_info("Usage: /image [--flux|--sd] <description>")
                self._print_info("  --flux  FLUX.1-dev (default, best quality)")
                self._print_info("  --sd    Stable Diffusion 3 Medium")

        elif command == "/search":
            if arg:
                self._web_search(arg)
            else:
                self._print_info("Usage: /search <query>")

        elif command == "/screen":
            self._capture_screen()

        elif command == "/history":
            self._show_history()

        elif command == "/stats":
            self._show_stats()

        elif command == "/clear":
            print("\033[2J\033[H", end="")  # ANSI clear

        else:
            self._print_info(f"Unknown command: {command}. Type /help for commands.")

        return True

    # ──────────────────────────────────────────────
    # Action helpers
    # ──────────────────────────────────────────────

    def _generate_image(self, prompt: str, model: str = "flux-dev"):
        """Generate an image via the agent."""
        self._print_info(f"🎨 Generating image with {model}: {prompt}")
        try:
            from providers import get_image
            from agents.prompt_enhancer import PromptEnhancer
            enhanced = PromptEnhancer().build_image_prompt(prompt)
            result = get_image().generate_image(enhanced, model=model)
            self._print_info(f"✅ Image saved: {result['filepath']}")
        except Exception as e:
            self._print_info(f"❌ Image generation failed: {e}")

    def _web_search(self, query: str):
        """Search the web and display results."""
        self._print_info(f"🔍 Searching: {query}")
        try:
            from providers import get_search
            result = get_search().search_formatted(query)
            self._print_response(result)
        except Exception as e:
            self._print_info(f"❌ Search failed: {e}")

    def _capture_screen(self):
        """Capture and analyze the screen."""
        self._print_info("📸 Capturing screen...")
        response = self.agent.chat("Please capture my screen and describe what you see.", stream=True)
        if not self._current_response:
            self._print_response(response)

    def _show_history(self):
        """Show recent chats."""
        chats = self.chat_store.list_chats(limit=10)
        if not chats:
            self._print_info("No chat history yet.")
            return

        self._print_info("📜 Recent chats:")
        for chat in chats:
            msg_count = self.chat_store.get_message_count(chat["id"])
            print(f"  • {chat['title']} ({msg_count} msgs) — {chat['updated_at']}")

    def _show_stats(self):
        """Show agent and system stats."""
        stats = self.agent.get_stats()
        ctx = stats["context"]
        store_stats = self.chat_store.get_stats()

        self._print_info("📊 MRAgent Stats:")
        print(f"  Chat ID:    {stats['chat_id']}")
        print(f"  Model mode: {stats['model_mode']}")
        print(f"  Override:   {stats['model_override'] or 'none'}")
        print(f"  Tools:      {stats['tools']}")
        print(f"  Context:    {ctx['used_tokens']:,}/{ctx['max_tokens']:,} tokens ({ctx['usage_ratio']})")
        print(f"  Messages:   {ctx['active_messages']} active, {ctx['full_history_messages']} total")
        print(f"  DB:         {store_stats['chats']} chats, {store_stats['messages']} messages ({store_stats['db_size_kb']:.1f}KB)")

    # ──────────────────────────────────────────────
    # Display helpers
    # ──────────────────────────────────────────────

    def _print_welcome(self):
        """Print welcome message."""
        print()
        self._print_info("MRAgent is ready! Type your message or /help for commands.")
        print()

    def _print_help(self):
        """Print help with available commands."""
        self._print_info("📋 Available commands:")
        for cmd, desc in COMMANDS.items():
            print(f"  {cmd:<12} {desc}")
        print()

    def _print_response(self, text: str):
        """Print a response, using rich markdown if available."""
        if self.has_rich and self.console:
            try:
                from rich.markdown import Markdown
                self.console.print(Markdown(text))
            except Exception:
                print(text)
        else:
            print(text)

    def _print_models(self, models: list):
        """Print available models."""
        self._print_info("🤖 Available models:")
        for m in models:
            status = "✅" if m.get("available", True) else "❌"
            print(f"  {status} {m['name']:<16} {', '.join(m.get('categories', [])):<20} {m.get('description', '')}")

    def _print_info(self, text: str):
        """Print an info message."""
        if self.has_rich and self.console:
            self.console.print(f"[dim]{text}[/dim]")
        else:
            print(text)

    def _print_dim(self, text: str):
        """Print dimmed text."""
        if self.has_rich and self.console:
            self.console.print(f"[dim]{text}[/dim]")
        else:
            print(f"\033[90m{text}\033[0m")
