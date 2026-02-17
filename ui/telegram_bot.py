"""
MRAgent — Telegram Bot Interface
Allows users to chat with the agent via Telegram.
Supports text and voice messages.
"""

import os
import asyncio
import logging
import tempfile
from typing import Optional

from telegram import Update, ForceReply
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

from agents.core import AgentCore
from config.settings import DEFAULTS
from utils.logger import get_logger, setup_logging

logger = get_logger("ui.telegram")

# Global agent instance
agent: Optional[AgentCore] = None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm MRAgent. 🤖"
        "\n\nYou can send me text or voice messages.",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    help_text = (
        "🤖 **MRAgent Help**\n\n"
        "Sending messages:\n"
        "• **Text**: Just type and send.\n"
        "• **Voice**: Record a voice note, and I'll listen.\n\n"
        "Commands:\n"
        "/start - tailored welcome\n"
        "/newchat - Start a fresh conversation context\n"
        "/help - Show this message"
    )
    await update.message.reply_markdown(help_text)


async def newchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the conversation context."""
    if agent:
        agent.new_chat()
        await update.message.reply_text("🔄 New conversation started! Memory cleared.")
    else:
        await update.message.reply_text("❌ Agent not initialized.")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    if not agent:
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id
    
    logger.info(f"Telegram msg from {chat_id}: {user_text}")

    # Show typing status
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Get response from agent (not streaming for Telegram to keep it simple)
    # Blocking call needs to be run in executor to not block asyncio loop
    loop = asyncio.get_running_loop()
    response_text = await loop.run_in_executor(None, agent.chat, user_text, False)

    # Split long messages if needed (Telegram limit is 4096 chars)
    if len(response_text) > 4000:
        for x in range(0, len(response_text), 4000):
            await update.message.reply_text(response_text[x:x+4000])
    else:
        await update.message.reply_text(response_text)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages."""
    if not agent:
        return

    chat_id = update.effective_chat.id
    voice = update.message.voice
    
    await update.message.reply_text("Functionality to convert voice to text is not yet fully linked in this lightweight bot version, sorry! Please type for now.")
    # TODO: Link with nvidia_stt provider if keys are available
    # file = await context.bot.get_file(voice.file_id)
    # ... download and transcode ...


class TelegramBot:
    """
    Main class to run the Telegram bot.
    """
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not found in .env")
            print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env")
            return

        global agent
        # Initialize the agent core
        agent = AgentCore(model_mode=DEFAULTS["model_selection_mode"])

    def run(self):
        """Start the bot polling loop."""
        if not self.token:
            return

        print("🤖 MRAgent Telegram Bot starting...")
        
        # Build application
        application = Application.builder().token(self.token).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("newchat", newchat_command))
        
        # Message handlers
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

        # Run
        print("✅ Bot is polling. Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def run_async(self):
        """Start the bot polling loop asynchronously (for background threads)."""
        if not self.token:
            return

        # Build application
        application = Application.builder().token(self.token).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("newchat", newchat_command))
        
        # Message handlers
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Keep running until cancelled
        # In a real app we'd use a stop signal, here we just wait forever
        while True:
            await asyncio.sleep(1)
