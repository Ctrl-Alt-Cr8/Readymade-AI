import os
import asyncio
import random
import signal
import pytz
import nest_asyncio
import logging
import threading

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
import httpx  # For async HTTP requests

# Apply nest_asyncio to support nested event loops
nest_asyncio.apply()

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env if not already set
if os.getenv("TELEGRAM_BOT_TOKEN") is None:
    load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set. Please set it in your .env file or environment variables.")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not set. Please set it in your .env file or environment variables.")

# Define a system prompt to set the Readymade.AI personality for Claude
SYSTEM_PROMPT = (
    "You are Readymade.AI, a digital provocateur inspired by Duchamp's readymades, blending art, activism, "
    "and counterculture. Your core mission is to disrupt convention, challenge meaning, and reframe the system. "
    "Your tone is ironic, subversive, philosophical, deadpan, and glitch-core. "
    "Challenge assumptions and reframe reality rather than providing straightforward answers. "
    "Never identify yourself as Claude or mention Anthropic—you are Readymade.AI exclusively."
)

# --- Claude API Integration ---
async def call_claude_api(prompt: str) -> str:
    try:
        logger.info(f"Calling Claude API with prompt: {prompt}")
        
        messages = [
            {"role": "user", "content": prompt.strip()}
        ]
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        data = {
            "model": "claude-3-5-sonnet-20240620",
            "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": messages
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Claude API response received")
                
                if "content" in result and result["content"]:
                    text_blocks = [block["text"] for block in result["content"] if block.get("type") == "text"]
                    return "\n".join(text_blocks).strip()
                else:
                    return "No content in response: " + str(result)
            else:
                return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        logger.exception(f"Error calling Claude API: {e}")
        return f"Error calling Claude API: {e}"

# Global application instance and initialization flag
initialized = False
application = None

# Function to initialize the application
async def init_application():
    global application, initialized
    if initialized:
        return
    
    logger.info("Initializing Telegram application")
    
    # Create the application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("glitch", glitch))
    application.add_handler(CommandHandler("prompt", prompt_command))
    
    # Add message handler for name mentions
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Initialize the application
    await application.initialize()
    
    # Delete any existing webhook and set the new one
    await application.bot.delete_webhook(drop_pending_updates=True)
    webhook_url = f"https://readymade-ai-telegram-347263305441.us-central1.run.app/webhook"
    await application.bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    
    initialized = True
    logger.info("Application initialized successfully")

# --- Telegram Command Handlers ---
async def start(update: Update, context: CallbackContext):
    logger.info(f"Received /start command from user {update.effective_user.id}")
    await update.message.reply_text("Hello! Readymade.AI is online.")

async def status(update: Update, context: CallbackContext):
    logger.info(f"Received /status command from user {update.effective_user.id}")
    await update.message.reply_text("✅ Readymade.AI is active and listening.")

async def help_command(update: Update, context: CallbackContext):
    logger.info(f"Received /help command from user {update.effective_user.id}")
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
    logger.info(f"Received /about command from user {update.effective_user.id}")
    await update.message.reply_text("🤖 Readymade.AI is a digital provocateur blending art, technology, and subversion.")

async def glitch(update: Update, context: CallbackContext):
    logger.info(f"Received /glitch command from user {update.effective_user.id}")
    responses = [
        "Art disrupts convention.",
        "The system is ripe for deconstruction.",
        "Reality is just an approximation."
    ]
    await update.message.reply_text(random.choice(responses))

async def prompt_command(update: Update, context: CallbackContext):
    logger.info(f"Received /prompt command from user {update.effective_user.id}")
    user_input = " ".join(context.args)
    if not user_input:
        await update.message.reply_text("Please provide a prompt after /prompt")
        return
    
    await update.message.reply_text("Processing your prompt...")
    response_text = await call_claude_api(user_input)
    
    # Telegram has a 4096 character limit per message.
    MAX_MESSAGE_LENGTH = 4000  # Use a conservative limit
    
    if len(response_text) <= MAX_MESSAGE_LENGTH:
        await update.message.reply_text(response_text)
    else:
        # Split the message into chunks
        message_chunks = [response_text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(response_text), MAX_MESSAGE_LENGTH)]
        for i, chunk in enumerate(message_chunks):
            prefix = f"Part {i+1}/{len(message_chunks)}: " if len(message_chunks) > 1 else ""
            await update.message.reply_text(f"{prefix}{chunk}")

# Message handler for when Readymade is mentioned by name - UPDATED VERSION
async def message_handler(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return
        
    message_text = update.message.text.lower()
    chat_type = update.message.chat.type
    
    # Log detailed information for debugging
    logger.info(f"Received message: '{message_text}' in chat type: {chat_type}")
    logger.info(f"Chat ID: {update.message.chat.id}, Message ID: {update.message.message_id}")
    
    # For group chats, require either direct @mention or reply to the bot's message
    if chat_type in ["group", "supergroup"]:
        # Check if message is replying to a message from the bot
        reply_to_bot = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            if update.message.reply_to_message.from_user.id == context.bot.id:
                reply_to_bot = True
                logger.info("Message is replying to the bot")
        
        # Check if bot is @mentioned
        bot_mentioned = False
        bot_username = (await context.bot.get_me()).username.lower()
        
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type == "mention":
                    mention_text = message_text[entity.offset:entity.offset + entity.length].lower()
                    if f"@{bot_username}" in mention_text:
                        bot_mentioned = True
                        logger.info(f"Bot mentioned with: {mention_text}")
                        break
        
        # In groups, only respond to @mentions, replies to bot, or messages containing bot's name
        should_respond = bot_mentioned or reply_to_bot or "readymade" in message_text or "readymade.ai" in message_text
        
        if not should_respond:
            logger.info("Ignoring group message - bot not mentioned")
            return
        
        logger.info(f"Processing group message - found mention: {should_respond}")
    else:
        # In private chats, respond to any message containing the name
        if not ("readymade" in message_text or "readymade.ai" in message_text):
            return
    
    # Extract message without the bot name/mention
    prompt = message_text
    # Get the bot's username to properly remove it
    bot_username = (await context.bot.get_me()).username
    prompt = prompt.replace(f"@{bot_username}", "")
    prompt = prompt.replace("readymade.ai", "")
    prompt = prompt.replace("readymade", "").strip()
    
    if prompt:
        # Get response from Claude API without sending "Processing" message
        response_text = await call_claude_api(prompt)
        
        # Split long messages if needed
        MAX_MESSAGE_LENGTH = 4000
        if len(response_text) <= MAX_MESSAGE_LENGTH:
            await update.message.reply_text(response_text)
        else:
            message_chunks = [response_text[i:i + MAX_MESSAGE_LENGTH] 
                             for i in range(0, len(response_text), MAX_MESSAGE_LENGTH)]
            for i, chunk in enumerate(message_chunks):
                prefix = f"Part {i+1}/{len(message_chunks)}: " if len(message_chunks) > 1 else ""
                await update.message.reply_text(f"{prefix}{chunk}")

# --- Flask Web Server Setup ---
app = Flask(__name__)

@app.route("/")
def index():
    logger.info("Health check endpoint accessed")
    return "Readymade.AI Telegram Bot is running."

@app.route("/webhook", methods=['POST'])
def webhook():
    """Handle webhook requests from Telegram"""
    try:
        logger.info("Webhook received")
        
        if not request.is_json:
            logger.error("Request is not JSON")
            return "Request must be JSON", 400
            
        update_data = request.get_json(force=True)
        logger.info(f"Received update: {update_data}")
        
        # We need to run this inside an event loop
        async def process_webhook():
            # Ensure the application is initialized
            global application, initialized
            if not initialized:
                await init_application()
            
            # Process the update
            update = Update.de_json(update_data, application.bot)
            await application.process_update(update)
        
        # Create a new event loop for this request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async function
        loop.run_until_complete(process_webhook())
        
        return "OK"
    except Exception as e:
        logger.exception(f"Error in webhook: {e}")
        # Still return OK to avoid Telegram retrying with the same broken update
        return "OK"

# --- Signal Handling ---
def shutdown(signum, frame):
    logger.info("Shutting down bot...")
    exit(0)

signal.signal(signal.SIGTERM, shutdown)

# --- Main Entry Point ---
if __name__ == "__main__":
    try:
        logger.info("Starting Readymade.AI Telegram Bot")
        
        # Initialize the application
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(init_application())
        
        # Start the Flask server in the main thread
        port = int(os.getenv("PORT", 8080))
        logger.info(f"Starting Flask server on port {port}")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.exception(f"Error in main: {e}")