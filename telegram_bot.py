import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext
from src.ai_engine import ai_engine  # Import AI Engine

# ✅ Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ✅ Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Function to process general messages
async def handle_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text  # Get user message
    chat_id = update.message.chat_id  # Get chat ID
    print(f"📩 Received message from {chat_id}: {user_message}")

    system_prompt = "You are ReadymadeAI, a digital provocateur and conceptual entity."

    # Generate response dynamically (switches between OpenAI/Claude based on context)
    response = ai_engine.generate_response(user_message, system_prompt, context_type="default")

    await update.message.reply_text(response)  # Send AI-generated response

# ✅ Main function to start the bot
async def main():
    """Starts the Readymade.AI Telegram bot"""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # ✅ Register message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Readymade.AI Telegram Bot is running...")
    await app.run_polling()

# ✅ Start bot
if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        print("✅ Running inside an active event loop. Creating a background task.")
        loop.create_task(main())  # ✅ Run inside existing event loop
    except RuntimeError:  # No event loop is running
        print("✅ No event loop detected. Running with asyncio.run().")
        asyncio.run(main())
