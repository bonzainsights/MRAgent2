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
from utils.logger import get_logger

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

    chat_id = update.effective_chat.id
    user_text = update.message.text
    
    # Security Whitelist Check
    allowed = os.getenv("ALLOWED_TELEGRAM_CHATS")
    if not allowed:
        logger.warning(f"No ALLOWED_TELEGRAM_CHATS setup. User {chat_id} attempted access.")
        await update.message.reply_markdown(
            f"🚫 **Setup Required**\n\n"
            f"Your Chat ID (`{chat_id}`) is not authorized to use this MRAgent bot.\n\n"
            f"To authorize yourself, open your `.env` file and add:\n"
            f"`ALLOWED_TELEGRAM_CHATS={chat_id}`\n\n"
            f"Then restart the application."
        )
        return

    if str(chat_id) not in [c.strip() for c in allowed.split(",")]:
        logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
        await update.message.reply_markdown(
            f"🚫 **Unauthorized Access**\n\n"
            f"Your Chat ID (`{chat_id}`) is not in the authorized whitelist."
        )
        return
    
    logger.info(f"Telegram msg from {chat_id}: {user_text}")

    # Show typing status
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Get response from agent (not streaming for Telegram to keep it simple)
    # Blocking call needs to be run in executor to not block asyncio loop
    loop = asyncio.get_running_loop()
    response_text = await loop.run_in_executor(None, agent.chat, user_text, False)

    # Send response with image support
    await send_response_with_images(update, context, response_text)


async def send_response_with_images(update: Update, context: ContextTypes.DEFAULT_TYPE, response_text: str):
    """Send text response and upload any detected images."""
    chat_id = update.effective_chat.id

    # Split long messages if needed
    if len(response_text) > 4000:
        for x in range(0, len(response_text), 4000):
            await update.message.reply_text(response_text[x:x+4000])
    else:
        await update.message.reply_text(response_text)

    # Detect and upload images
    import re
    image_matches = re.findall(r"!\[.*?\]\((.*?)\)", response_text)
    
    if image_matches:
        for image_path in image_matches:
            image_path = image_path.strip()
            if os.path.exists(image_path):
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
                    await context.bot.send_photo(chat_id=chat_id, photo=open(image_path, 'rb'))
                    logger.info(f"Sent image to Telegram: {image_path}")
                except Exception as e:
                    logger.error(f"Failed to send image {image_path}: {e}")
            else:
                logger.warning(f"Image path not found: {image_path}")


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages."""
    if not agent:
        return

    chat_id = update.effective_chat.id
    
    # Security Whitelist Check
    allowed = os.getenv("ALLOWED_TELEGRAM_CHATS")
    if not allowed:
        logger.warning(f"No ALLOWED_TELEGRAM_CHATS setup. User {chat_id} attempted voice access.")
        await update.message.reply_markdown(
            f"🚫 **Setup Required**\n\n"
            f"Your Chat ID (`{chat_id}`) is not authorized to use this MRAgent bot.\n\n"
            f"To authorize yourself, open your `.env` file and add:\n"
            f"`ALLOWED_TELEGRAM_CHATS={chat_id}`\n\n"
            f"Then restart the application."
        )
        return

    if str(chat_id) not in [c.strip() for c in allowed.split(",")]:
        logger.warning(f"Unauthorized voice attempt from chat_id: {chat_id}")
        await update.message.reply_markdown(
            f"🚫 **Unauthorized Access**\n\n"
            f"Your Chat ID (`{chat_id}`) is not in the authorized whitelist."
        )
        return

    voice = update.message.voice
    
    logger.info(f"Received voice message from {chat_id}")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # 1. Download voice file
        new_file = await context.bot.get_file(voice.file_id)
        
        import io
        video_bio = io.BytesIO()
        await new_file.download_to_memory(video_bio)
        video_bio.seek(0)
        audio_bytes = video_bio.read()

        # 2. Transcribe
        from providers.nvidia_stt import NvidiaSTTProvider
        stt = NvidiaSTTProvider()
        
        if not stt.available:
            await update.message.reply_text("❌ Voice is disabled (missing API key).")
            return

        # Run STT in executor
        loop = asyncio.get_running_loop()
        transcript = await loop.run_in_executor(None, stt.speech_to_text, audio_bytes)
        
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # 3. Send to Agent
        response_text = await loop.run_in_executor(None, agent.chat, transcript, False)

        # 4. Reply with images support
        await send_response_with_images(update, context, response_text)
        
        # 5. Voice Reply (TTS)
        try:
            from providers.tts import text_to_speech
            
            # Use temp file for TTS output
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_tts:
                tts_path = temp_tts.name
            
            await text_to_speech(response_text[:4000], tts_path) # Limit char count for TTS stability
            
            if os.path.exists(tts_path):
                await context.bot.send_chat_action(chat_id=chat_id, action="upload_voice")
                with open(tts_path, 'rb') as audio:
                    await update.message.reply_voice(voice=audio)
                
                # Cleanup
                os.remove(tts_path)
                
        except Exception as e:
            logger.error(f"TTS reply failed: {e}")
        
    except Exception as e:
        logger.error(f"Voice handling failed: {e}")
        await update.message.reply_text("❌ Sorry, I couldn't understand that audio.")


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
