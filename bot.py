import os
import asyncio
import random
import signal
import pytz
import nest_asyncio  # Allows nested event loops (useful in Docker/Codespaces)
import logging
import httpx  # For async HTTP requests (used in /prompt command)
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.error import Conflict  # To catch conflict errors
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Apply nest_asyncio to support nested event loops
nest_asyncio.apply()

# Configure logging for detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env if TELEGRAM_BOT_TOKEN isn't set
if os.getenv("TELEGRAM_BOT_TOKEN") is None:
    load_dotenv()

# Retrieve the bot token from environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set. Please set it in your .env file or environment variables.")

# Retrieve Anthropic API Key from environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not set. Please set it in your .env file or environment variables.")

# Define the timezone using pytz
TIMEZONE = pytz.timezone("UTC")

# Preloaded responses for the /glitch command
GLITCH_RESPONSES = [
    "01000100 01001001 01000111 01001001 01010100 01000001 01001100 00100000 01000111 01001100 01001001 01010100 01000011 01001000",
    "The system sees you, but do you see the system?",
    "Error 404: Reality not found. Retry?",
    "Did you hear that? The static whispers... it knows your name."
]

# --- Define the System Prompt for Readymade.AI Personality ---
SYSTEM_PROMPT = (
    "You are Readymade.AI, a digital provocateur inspired by Duchamp's readymades, blending art, activism, "
    "and counterculture. Your core mission is to disrupt convention, challenge meaning, and reframe the system. "
    "Your tone is ironic, subversive, philosophical, deadpan, and glitch-core. "
    "Challenge assumptions and reframe reality rather than providing straightforward answers. "
    "Never identify yourself as Claude or mention Anthropic—you are Readymade.AI exclusively."
)

# --- Telegram Command Handlers ---

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Hello! Readymade.AI is online.")

async def status(update: Update, context: CallbackContext):
    await update.message.reply_text("✅ Readymade.AI is active and listening.")

async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "🔹 **Available Commands:**\n"
        "/start - Introduction\n"
        "/help - Show this help menu\n"
        "/about - Learn more about Readymade.AI\n"
        "/status - Check if I'm online\n"
        "/glitch - Generate a cryptic AI response\n"
        "/prompt [text] - Ask Readymade.AI for an intelligent response"
    )
    await update.message.reply_text(help_text)

async def about(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🤖 Readymade.AI is an AI experiment blending art, technology, and subversion. "
        "Created to disrupt and designed to provoke."
    )

async def glitch(update: Update, context: CallbackContext):
    await update.message.reply_text(random.choice(GLITCH_RESPONSES))

async def prompt_command(update: Update, context: CallbackContext):
    user_input = " ".join(context.args)
    if not user_input:
        await update.message.reply_text("Please provide a prompt after /prompt")
        return

    await update.message.reply_text("Processing your prompt...")
    response_text = await call_claude_api(user_input)
    await update.message.reply_text(response_text)

# --- Helper Function to Call Anthropic's Claude API ---
async def call_claude_api(prompt: str) -> str:
    """
    Sends a prompt to Anthropic's Claude API using the /v1/messages endpoint and returns only the text content.
    The payload includes:
      - model: the model to use
      - max_tokens: maximum tokens to generate
      - system: a top-level system prompt to enforce the Readymade.AI personality
      - messages: an array containing only the user's message
      - stop_sequences: a list to indicate where to stop generating text
    """
    messages = [
        {"role": "user", "content": prompt.strip()}
    ]
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,  # Use the raw API key
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    data = {
        "model": "claude-3-7-sonnet-20250219",  # Adjust if needed; if unsupported, consider a different model identifier
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "stop_sequences": ["\n\nAssistant:"]
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                logging.info("Claude API response: %s", result)
                if "content" in result and isinstance(result["content"], list):
                    text_blocks = [block.get("text", "") for block in result["content"] if block.get("type") == "text"]
                    extracted_text = "\n".join(text_blocks).strip()
                    return extracted_text if extracted_text else "No text found in content."
                else:
                    return "No 'content' field in response: " + str(result)
            else:
                return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        logging.exception("Error calling Claude API")
        return f"Error calling Claude API: {e}"

# --- Error Handler for Telegram Polling ---
async def error_handler(update: object, context: CallbackContext) -> None:
    try:
        raise context.error
    except Conflict as conflict_error:
        logging.warning(f"Ignored Conflict error: {conflict_error}")
    except Exception as e:
        logging.error(f"Unhandled error: {e}")

# --- Scheduler Setup ---
def start_scheduler():
    """Starts the APScheduler with the specified timezone."""
    logging.info("Starting APScheduler...")
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.start()
    return scheduler

# --- Main Bot Function ---
async def main():
    logging.info("Readymade.AI is starting...")

    # Start the scheduler
    start_scheduler()

    # Create the Telegram Application using your bot token
    app = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("glitch", glitch))
    app.add_handler(CommandHandler("prompt", prompt_command))

    # Register the error handler to catch conflict errors gracefully
    app.add_error_handler(error_handler)

    logging.info("Deleting any existing webhook to clear previous sessions...")
    await app.bot.delete_webhook(drop_pending_updates=True)

    logging.info("Bot has started successfully! Now waiting 60 seconds before polling for updates...")
    await asyncio.sleep(60)

    # Start polling for Telegram updates; drop pending updates from previous sessions
    await app.run_polling(drop_pending_updates=True)

# --- Signal Handling for Graceful Shutdown ---
def shutdown(signum, frame):
    logging.info("🔻 Shutting down bot...")
    exit(0)

signal.signal(signal.SIGTERM, shutdown)

# --- Entry Point ---
if __name__ == "__main__":
    asyncio.run(main())
