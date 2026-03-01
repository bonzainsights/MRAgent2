"""
MRAgent — CLI Interface
Rich terminal interface with markdown rendering, commands, and streaming output.

Created: 2026-02-15
"""

import sys
import os

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
    "/guide":    "Screen guidance — see your screen and help (e.g. /guide how do I fix this?)",
    "/history":  "Show recent chat history",
    "/load":     "Load a previous chat (e.g. /load last or /load <id>)",
    "/stats":    "Show agent statistics",
    "/status":   "Show active config (model, providers, trust level)",
    "/clear":    "Clear the screen",
    "/skills":   "Configure API skills (Telegram, AgentMail...)",
    "/email":    "Send an email interactively",
    "/identity": "Change your name or the agent's name",
    "/autonomy": "Set trust level (cautious/balanced/autonomous)",
    "/auto":     "Directory-scoped auto mode (e.g. /auto . or /auto off)",
    "/watch":    "Start Eagle Eye Watcher mode",
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
        self.agent.approval_callback = self._approval_callback
        self._current_response = ""
        self._last_model = self._mode_to_model(model_mode)  # Track current model

        logger.info("CLI interface initialized")

    def _approval_callback(self, prompt: str) -> bool:
        """Prompt user for approval before running dangerous tools."""
        if self.console and self.has_rich:
            import rich.prompt
            self.console.print(f"\n[bold yellow]⚠️ Action Required[/bold yellow]")
            self.console.print(prompt)
            return rich.prompt.Confirm.ask("[bold]Approve execution?[/bold]", default=False)
        else:
            print(f"\n⚠️ Action Required\n{prompt}")
            choice = input("Approve execution? (y/N): ")
            return choice.lower() in ("y", "yes")

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
            from config.settings import MODEL_REGISTRY

            if arg:
                # Direct set
                if arg in MODEL_REGISTRY:
                    self.agent.set_model(arg)
                    self._last_model = arg
                    self._print_info(f"✅ Model set to: {arg}")
                else:
                    self._print_info(f"❌ Unknown model: {arg}")
                    self._print_info(f"Available: {', '.join(k for k,v in MODEL_REGISTRY.items() if v.get('type') in ('llm', 'vlm'))}")
            else:
                # Interactive set (Inline)
                choices = []
                for model_id, info in MODEL_REGISTRY.items():
                    if info.get("type") in ("llm", "vlm"):
                        cats = ", ".join(info.get("categories", []))
                        label = f"{model_id:<20} <style fg='gray'>({cats})</style>"
                        choices.append({"id": model_id, "label": label})
                
                if not choices:
                    self._print_info("No LLM models found.")
                    return True

                selected_model = self._interactive_menu("Select a model (Type /help for more info):", choices)
                
                if selected_model:
                    self.agent.set_model(selected_model)
                    self._last_model = selected_model
                    self._print_info(f"✅ Model set to: {selected_model}")
                else:
                    self._print_info("Cancelled.")

        elif command == "/mode":
            if arg in ("auto", "thinking", "fast", "code", "browsing"):
                self.agent.set_model_mode(arg)
                self.agent.model_override = None  # Clear manual override
                self._last_model = self._mode_to_model(arg)
                self._print_info(f"✅ Switched to {arg} mode → {self._last_model}")
            else:
                from agents.model_selector import ModelSelector
                current = self.agent.model_selector.mode
                
                # Build dynamic menu choices for mode selection
                choices = []
                for m in ("auto", "thinking", "fast", "code", "browsing"):
                    if m == "auto":
                        label = "auto       <style fg='gray'>(Dynamic fallback routing)</style>"
                    else:
                        default = ModelSelector.get_default_for_mode(m)
                        extra = f" <style fg='gray'>({default})</style>"
                        label = f"{m:<10} {extra}"
                    choices.append({"id": m, "label": label})
                
                selected_mode = self._interactive_menu(f"Select a Mode (Current: {current}):", choices)
                
                if selected_mode:
                    self.agent.set_model_mode(selected_mode)
                    self.agent.model_override = None
                    self._last_model = self._mode_to_model(selected_mode)
                    self._print_info(f"✅ Switched to {selected_mode} mode → {self._last_model}")
                else:
                    self._print_info("Cancelled.")

        elif command == "/voice":
            self.voice_enabled = not self.voice_enabled
            self._print_info(f"Voice: {'ON' if self.voice_enabled else 'OFF'}")

        elif command == "/image":
            if arg:
                # Parse optional --model flag and aspect ratio
                model = "flux-dev"
                aspect = "1:1"
                prompt = arg
                if arg.startswith("--sd "):
                    model = "sd-3-medium"
                    prompt = arg[5:].strip()
                elif arg.startswith("--flux "):
                    model = "flux-dev"
                    prompt = arg[7:].strip()
                # Parse --wide, --tall, --portrait shortcuts
                if "--wide" in prompt:
                    aspect = "16:9"
                    prompt = prompt.replace("--wide", "").strip()
                elif "--tall" in prompt or "--portrait" in prompt:
                    aspect = "9:16"
                    prompt = prompt.replace("--tall", "").replace("--portrait", "").strip()
                if prompt:
                    self._generate_image(prompt, model=model, aspect_ratio=aspect)
                else:
                    self._print_info("Usage: /image [--flux|--sd] [--wide|--tall] <description>")
            else:
                self._print_info("Usage: /image [--flux|--sd] [--wide|--tall] <description>")
                self._print_info("  --flux  FLUX.1-dev (default)")
                self._print_info("  --sd    Stable Diffusion 3 Medium")
                self._print_info("  --wide  16:9 landscape")
                self._print_info("  --tall  9:16 portrait")

        elif command == "/search":
            if arg:
                self._web_search(arg)
            else:
                self._print_info("Usage: /search <query>")

        elif command == "/screen":
            self._capture_screen()

        elif command == "/guide":
            self._guide_screen(arg)

        elif command == "/history":
            self._show_history()

        elif command == "/load":
            self._load_chat(arg)

        elif command == "/stats":
            self._show_stats()

        elif command == "/status":
            self._show_status()

        elif command == "/clear":
            print("\033[2J\033[H", end="")  # ANSI clear

        elif command == "/identity":
            self._configure_identity()

        elif command == "/email":
            self._send_email_interactive()

        elif command == "/skills":
            self._configure_skills()

        elif command == "/watch":
            self._print_info("🦅 Starting Eagle Eye Watcher... (Press Ctrl+C to stop)")
            try:
                from agents.watcher import EagleEyeWatcher
                EagleEyeWatcher(interval=2.0, diff_threshold=5.0).start()
            except ImportError:
                self._print_info("❌ Watcher dependencies missing.")
            except Exception as e:
                self._print_info(f"❌ Watcher error: {e}")

        elif command == "/autonomy":
            self._configure_autonomy()

        elif command == "/auto":
            self._configure_auto(arg)

        else:
            self._print_info(f"Unknown command: {command}. Type /help for commands.")

        return True

    # ──────────────────────────────────────────────
    # Action helpers
    # ──────────────────────────────────────────────

    def _interactive_menu(self, title: str, choices: list[dict]) -> str:
        """
        Display an interactive arrow-key menu.
        choices should contain dicts with 'id' and 'label'.
        """
        try:
            from prompt_toolkit.application import Application
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.layout.containers import Window
            from prompt_toolkit.layout.controls import FormattedTextControl
            from prompt_toolkit.layout.layout import Layout
            from prompt_toolkit.formatted_text import HTML, merge_formatted_text

            if not choices:
                return None

            state = {"index": 0, "selected": None}
            kb = KeyBindings()

            @kb.add("up")
            def _(event):
                state["index"] = (state["index"] - 1) % len(choices)

            @kb.add("down")
            def _(event):
                state["index"] = (state["index"] + 1) % len(choices)

            @kb.add("enter")
            def _(event):
                state["selected"] = choices[state["index"]]["id"]
                event.app.exit(result=state["selected"])

            @kb.add("c-c")
            def _(event):
                event.app.exit(result=None)

            def get_formatted_text():
                lines = []
                lines.append(HTML(f"<b>{title}</b>"))
                for i, choice in enumerate(choices):
                    if i == state["index"]:
                        lines.append(HTML(f"\n <style fg='cyan'>❯ {choice['label']}</style>"))
                    else:
                        lines.append(HTML(f"\n   {choice['label']}"))
                return merge_formatted_text(lines)

            app = Application(
                layout=Layout(Window(content=FormattedTextControl(get_formatted_text), height=len(choices)+2)),
                key_bindings=kb,
                mouse_support=False,
                full_screen=False,
            )

            return app.run()

        except ImportError:
            self._print_info("Interactive selection requires prompt_toolkit.")
            return None
        except Exception as e:
            self._print_info(f"Selection failed: {e}")
            return None

    def _generate_image(self, prompt: str, model: str = "flux-dev", aspect_ratio: str = "1:1"):
        """Generate an image using the tool's full pipeline (enhancement + fallback)."""
        self._print_info(f"🎨 Generating image with {model} ({aspect_ratio}): {prompt}")
        try:
            tool = self.agent.tool_registry.get("generate_image")
            if tool:
                result = tool.execute(prompt=prompt, aspect_ratio=aspect_ratio)
                self._print_info(result)
            else:
                # Fallback to direct provider call
                from providers import get_image
                from agents.prompt_enhancer import PromptEnhancer
                enhanced = PromptEnhancer().build_image_prompt(prompt)
                result = get_image().generate_image(enhanced, model=model, aspect_ratio=aspect_ratio)
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

    def _show_status(self):
        """Show all active configuration at a glance."""
        import os
        from config.settings import AUTONOMY_SETTINGS, AGENT_NAME, USER_NAME

        trust = AUTONOMY_SETTINGS.get('trust_level', 'balanced')
        trust_icons = {'cautious': '🔒', 'balanced': '⚖️', 'autonomous': '⚡'}

        model = self._last_model or 'auto'
        mode = self.agent.model_selector.mode
        override = self.agent.model_override or 'none'

        image_provider = os.getenv('IMAGE_PROVIDER', 'flux').lower()
        if image_provider == 'google' and os.getenv('GOOGLE_AI_STUDIO_KEY'):
            image_str = 'Google AI Studio'
        else:
            image_str = 'NVIDIA FLUX'

        search_provider = os.getenv('SEARCH_PROVIDER', 'brave')

        self._print_info("\n📋 MRAgent Status")
        print(f"  Identity:       {USER_NAME} ↔ {AGENT_NAME}")
        print(f"  Model:          {model} (mode: {mode}, override: {override})")
        print(f"  Image Provider: {image_str}")
        print(f"  Search:         {search_provider}")
        print(f"  Trust Level:    {trust_icons.get(trust, '❓')} {trust}")
        # Show /auto mode status
        if AUTONOMY_SETTINGS.get("auto_session_active"):
            auto_dir = AUTONOMY_SETTINGS.get("auto_directory", "")
            print(f"  Auto Mode:      🟢 ACTIVE → {auto_dir}")
        else:
            print(f"  Auto Mode:      🔴 OFF")
        print(f"  Web Port:       {os.getenv('PORT', '16226')}")
        print(f"  Voice:          {'ON' if self.voice_enabled else 'OFF'}")

        # Show key status
        has_nvidia = bool(os.getenv('NVIDIA_API_KEY'))
        has_groq = bool(os.getenv('GROQ_API_KEY'))
        has_telegram = bool(os.getenv('TELEGRAM_BOT_TOKEN'))
        has_agentmail = bool(os.getenv('AGENTMAIL_API_KEY'))
        print(f"  API Keys:       NVIDIA {'✅' if has_nvidia else '❌'} | Groq {'✅' if has_groq else '❌'} | Telegram {'✅' if has_telegram else '❌'} | AgentMail {'✅' if has_agentmail else '❌'}")
        print()

    def _send_email_interactive(self):
        """Interactive email sending via AgentMail."""
        try:
            import os
            if not os.getenv('AGENTMAIL_API_KEY'):
                self._print_info("❌ AgentMail not configured. Run /skills → AgentMail to set up.")
                return

            to_addr = self._get_input_clean("To: ").strip()
            if not to_addr:
                self._print_info("Cancelled.")
                return

            subject = self._get_input_clean("Subject: ").strip()
            if not subject:
                subject = "(no subject)"

            self._print_info("Enter message body (press Enter twice to send):")
            body_lines = []
            while True:
                line = self._get_input_clean("")
                if line == "" and body_lines and body_lines[-1] == "":
                    break
                body_lines.append(line)
            body = "\n".join(body_lines).strip()

            if not body:
                self._print_info("Cancelled (empty body).")
                return

            self._print_info(f"📧 Sending to {to_addr}...")

            from skills.agentmail import SendEmailTool
            tool = SendEmailTool()
            result = tool.execute(to=to_addr, subject=subject, body=body)
            self._print_info(result)

        except ImportError:
            self._print_info("❌ AgentMail skill not found.")
        except Exception as e:
            self._print_info(f"❌ Failed to send email: {e}")

    def _configure_skills(self):
        """Interactive skills configuration."""
        self._print_info("\n🧩 Skills Configuration")
        
        choices = [
            {"id": "search", "label": "Search Provider    <style fg='gray'>(Brave/Google/LangSearch)</style>"},
            {"id": "google_image", "label": "Google AI Studio   <style fg='gray'>(Image Generation)</style>"},
            {"id": "telegram", "label": "Telegram Bot       <style fg='gray'>(@BotFather)</style>"},
            {"id": "agentmail", "label": "AgentMail          <style fg='gray'>(Email via API)</style>"},
            {"id": "nvidia", "label": "NVIDIA API         <style fg='gray'>(Primary LLM key)</style>"},
            {"id": "groq", "label": "Groq API           <style fg='gray'>(Whisper Voice STT)</style>"},
            {"id": "cancel", "label": "<style fg='gray'>Cancel...</style>"}
        ]
        
        choice = self._interactive_menu("Select a skill to configure:", choices)
        
        if choice == "cancel" or not choice:
            self._print_info("Configuration cancelled.")
            return

        if choice == "search":
            self._configure_search_provider()
        elif choice == "google_image":
            self._configure_generic_skill("Google AI Studio (Image Gen)", ["GOOGLE_AI_STUDIO_KEY"])
            self._print_info("💡 Get your free key at: https://aistudio.google.com")
        elif choice == "telegram":
            self._configure_generic_skill("Telegram Bot", ["TELEGRAM_BOT_TOKEN", "ALLOWED_TELEGRAM_CHATS"])
        elif choice == "agentmail":
            self._configure_generic_skill("AgentMail", ["AGENTMAIL_API_KEY"])
        elif choice == "nvidia":
            self._configure_generic_skill("NVIDIA API", ["NVIDIA_API_KEY"])
        elif choice == "groq":
            self._configure_generic_skill("Groq API", ["GROQ_API_KEY"])

    def _configure_identity(self):
        """Interactive identity configuration."""
        import os
        from config import settings
        from utils.config_manager import update_env_key
        
        self._print_info("\n📛 Identity Configuration")
        
        current_user = os.getenv("USER_NAME", "User")
        current_agent = os.getenv("AGENT_NAME", "MRAgent")
        
        print(f"Current User Name: {current_user}")
        new_user = self._get_input_clean("Enter new User Name (Press Enter to keep): ")
        
        print(f"Current Agent Name: {current_agent}")
        new_agent = self._get_input_clean("Enter new Agent Name (Press Enter to keep): ")
        
        changes = 0
        if new_user and new_user != current_user:
            if update_env_key("USER_NAME", new_user):
                os.environ["USER_NAME"] = new_user
                settings.USER_NAME = new_user
                changes += 1
                
        if new_agent and new_agent != current_agent:
            if update_env_key("AGENT_NAME", new_agent):
                os.environ["AGENT_NAME"] = new_agent
                settings.AGENT_NAME = new_agent
                changes += 1
                
        if changes > 0:
            self._print_info(f"\n✅ Identity updated! Nice to meet you, {settings.USER_NAME}. I will answer to {settings.AGENT_NAME}.")
        else:
            self._print_info("\nNo changes made.")

    def _configure_autonomy(self):
        """Interactive autonomy/trust level configuration."""
        from config.settings import AUTONOMY_SETTINGS
        from utils.config_manager import update_env_key

        current = AUTONOMY_SETTINGS.get("trust_level", "balanced")
        self._print_info(f"\n⚡ Autonomy Configuration (current: {current})")

        choices = [
            {"id": "cautious",   "label": "🔒 cautious    <style fg='gray'>(Ask before every non-read command)</style>"},
            {"id": "balanced",   "label": "⚖️  balanced    <style fg='gray'>(Auto-run safe patterns, ask for risky)</style>"},
            {"id": "autonomous", "label": "⚡ autonomous  <style fg='gray'>(Run everything, log only — for 24/7)</style>"},
            {"id": "cancel",     "label": "<style fg='gray'>Cancel...</style>"},
        ]

        choice = self._interactive_menu(f"Select trust level (current: {current}):", choices)

        if choice and choice != "cancel":
            AUTONOMY_SETTINGS["trust_level"] = choice
            update_env_key("TRUST_LEVEL", choice)
            trust_icons = {'cautious': '🔒', 'balanced': '⚖️', 'autonomous': '⚡'}
            self._print_info(f"\n✅ Trust level set to: {trust_icons.get(choice, '')} {choice}")
            if choice == "autonomous":
                self._print_info("⚠️  The agent will now execute ALL commands without asking. Use with caution.")
        else:
            self._print_info("Cancelled.")

    def _configure_auto(self, arg: str):
        """Configure directory-scoped autonomous mode."""
        from config.settings import AUTONOMY_SETTINGS

        if not arg:
            # Show status
            if AUTONOMY_SETTINGS.get("auto_session_active"):
                auto_dir = AUTONOMY_SETTINGS.get("auto_directory", "")
                self._print_info(f"🟢 Auto mode is ACTIVE in: {auto_dir}")
                self._print_info("  Use /auto off to disable.")
            else:
                self._print_info("🔴 Auto mode is OFF")
                self._print_info("  Usage: /auto <directory>  — Grant agent permission to work freely in a project dir")
                self._print_info("         /auto .            — Use current directory")
                self._print_info("         /auto off          — Disable auto mode")
            return

        if arg.lower() == "off":
            AUTONOMY_SETTINGS["auto_session_active"] = False
            AUTONOMY_SETTINGS["auto_directory"] = None
            self._print_info("🔴 Auto mode disabled. Agent will ask for approval as usual.")
            return

        # Resolve directory
        target_dir = os.path.abspath(os.path.expanduser(arg))
        if not os.path.isdir(target_dir):
            self._print_info(f"❌ Directory not found: {target_dir}")
            return

        AUTONOMY_SETTINGS["auto_directory"] = target_dir
        AUTONOMY_SETTINGS["auto_session_active"] = True

        self._print_info(f"\n⚡ Auto mode ENABLED")
        self._print_info(f"  📂 Scope: {target_dir}")
        self._print_info(f"  ✅ Agent can freely run project commands within this directory")
        self._print_info(f"  🛡️  Blocked: rm -rf, sudo, shutdown, commands outside this directory")
        self._print_info(f"  Use /auto off when done.")

    def _configure_search_provider(self):
        """Specific configuration for search providers."""
        self._print_info("\n🔍 Search Provider Configuration")
        
        choices = [
            {"id": "google", "label": "Google Search      <style fg='gray'>(requires API Key + CSE ID)</style>"},
            {"id": "brave", "label": "Brave Search       <style fg='gray'>(requires API Key)</style>"},
            {"id": "langsearch", "label": "LangSearch         <style fg='gray'>(requires API Key)</style>"},
            {"id": "cancel", "label": "<style fg='gray'>Cancel...</style>"}
        ]
        
        choice = self._interactive_menu("Select provider:", choices)
        
        if choice == "google":
            print("\nConfiguring Google Search...")
            self._update_env_interactive("GOOGLE_SEARCH_API_KEY")
            self._update_env_interactive("GOOGLE_SEARCH_CSE_ID")
            
            from utils.config_manager import update_env_key
            if update_env_key("SEARCH_PROVIDER", "google"):
                self._print_info("✅ Default search provider set to: Google")
                
        elif choice == "brave":
            print("\nConfiguring Brave Search...")
            self._update_env_interactive("BRAVE_SEARCH_API_KEY")
            
            from utils.config_manager import update_env_key
            if update_env_key("SEARCH_PROVIDER", "brave"):
                self._print_info("✅ Default search provider set to: Brave")

        elif choice == "langsearch":
            print("\nConfiguring LangSearch...")
            self._update_env_interactive("LANGSEARCH_API_KEY")
            
            from utils.config_manager import update_env_key
            if update_env_key("SEARCH_PROVIDER", "langsearch"):
                self._print_info("✅ Default search provider set to: LangSearch")
                
        else:
            self._print_info("Cancelled.")

    def _configure_generic_skill(self, name: str, env_vars: list):
        """Configure a generic skill with a list of env vars."""
        self._print_info(f"\nConfiguring {name}...")
        changes_made = False
        
        for var in env_vars:
            if self._update_env_interactive(var):
                changes_made = True
        
        if changes_made:
            self._print_info("\n✅ Configuration updated! Please restart MRAgent for changes to take effect.")
        else:
            self._print_info("\nNo changes made.")

    def _update_env_interactive(self, key: str) -> bool:
        """Interactive helper to update a single env var."""
        current_val = os.getenv(key, "")
        display_val = f"{current_val[:4]}...{current_val[-4:]}" if current_val and len(current_val) > 8 else (current_val or "Not set")
        
        print(f"\n{key}")
        print(f"Current: {display_val}")
        new_val = self._get_input_clean(f"Enter new value (Press Enter to keep): ")
        
        if new_val:
            from utils.config_manager import update_env_key
            if update_env_key(key, new_val):
                print(f"✅ Updated {key}")
                return True
            else:
                print(f"❌ Failed to update {key}")
                return False
        return False

    def _get_input_clean(self, prompt: str) -> str:
        """Helper to get raw input without rich formatting issues."""
        try:
            return input(prompt).strip()
        except EOFError:
            return ""
        except UnicodeDecodeError:
            import sys
            import termios
            # Flush the invalid bytes from stdin buffer to prevent immediate re-read
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
            print("\n[!] Invalid UTF-8 characters detected. Avoid copy-pasting from formatted documents. Use plain text only.")
            return self._get_input_clean(prompt)

    def _capture_screen(self):
        """Capture and analyze the screen using the vision model."""
        self._print_info("📸 Capturing and analyzing screen...")
        try:
            analysis = self.agent.analyze_screen()
            self._print_response(analysis)
        except Exception as e:
            self._print_info(f"❌ Screen analysis failed: {e}")

    def _guide_screen(self, question: str = ""):
        """Capture screen and provide guidance, optionally for a specific question."""
        if question:
            self._print_info(f"📸 Analyzing screen for: {question}")
        else:
            self._print_info("📸 Analyzing screen for guidance...")

        try:
            analysis = self.agent.analyze_screen(user_question=question or None)
            self._print_response(analysis)
        except Exception as e:
            self._print_info(f"❌ Screen guidance failed: {e}")

    def _show_history(self):
        """Show recent chats."""
        chats = self.chat_store.list_chats(limit=10)
        if not chats:
            self._print_info("No chat history yet.")
            return

        self._print_info("📜 Recent chats:")
        for chat in chats:
            msg_count = self.chat_store.get_message_count(chat["id"])
            print(f"  • {chat['title']} ({msg_count} msgs) — {chat['updated_at']} <style fg='gray'>ID: {chat['id']}</style>")

    def _load_chat(self, arg: str):
        """Load a previous chat."""
        chats = self.chat_store.list_chats(limit=30)
        if not chats:
            self._print_info("No chat history available.")
            return

        chat_id = None
        if arg.lower() == "last" and chats:
            chat_id = chats[0]["id"]
        elif arg:
            # Check if arg is a valid ID from the DB
            chat = self.chat_store.get_chat(arg)
            if chat:
                chat_id = chat["id"]
            else:
                self._print_info(f"❌ Chat ID '{arg}' not found.")
                return
        else:
            # Interactive menu
            choices = []
            for chat in chats:
                msg_count = self.chat_store.get_message_count(chat["id"])
                label = f"{chat['title'][:30]:<30} <style fg='gray'>({msg_count} msgs) {chat['updated_at'][:16]}</style>"
                choices.append({"id": chat["id"], "label": label})
                
            chat_id = self._interactive_menu("Select a chat to load:", choices)

        if not chat_id:
            self._print_info("Cancelled.")
            return

        messages = self.chat_store.get_messages(chat_id)
        if not messages:
            self._print_info("❌ Chat is empty or could not be loaded.")
            return

        self.agent.load_chat(chat_id, messages)
        # Let's fix lines around 839 as well if they exist
        self._print_info(f"✅ Loaded chat: {chat_id} ({len(messages)} messages)")

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

        # Show autonomy trust level
        from config.settings import AUTONOMY_SETTINGS
        trust = AUTONOMY_SETTINGS.get('trust_level', 'balanced')
        trust_icons = {'cautious': '🔒', 'balanced': '⚖️', 'autonomous': '⚡'}
        print(f"  Trust:      {trust_icons.get(trust, '❓')} {trust}")

    # ──────────────────────────────────────────────
    # Display helpers
    # ──────────────────────────────────────────────

    def _print_welcome(self):
        """Print welcome message with quick tips."""
        from config.settings import USER_NAME, AGENT_NAME
        print()
        self._print_info(f"Hey {USER_NAME}! {AGENT_NAME} is ready.")
        self._print_dim("  💡 Tips: /help for commands | /guide for screen help | /autonomy to set trust level")
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
            self.console.print(f"<style fg='gray'>{text}</style>")
        else:
            print(text)

    def _print_dim(self, text: str):
        """Print dimmed text."""
        if self.has_rich and self.console:
            self.console.print(f"<style fg='gray'>{text}</style>")
        else:
            print(f"\033[90m{text}\033[0m")
