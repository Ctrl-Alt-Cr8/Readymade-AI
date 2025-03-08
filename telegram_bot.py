import os
import pytz
import tzlocal
import logging
import asyncio
import random
import nest_asyncio  # ✅ Fix for asyncio event loop issues
from dotenv import load_dotenv  # ✅ Securely load environment variables

# ✅ Load environment variables from .env
load_dotenv()

# ✅ Step 1: Set Environment Variable Early
os.environ["TZ"] = "UTC"

# ✅ Step 2: Patch tzlocal to always return a pytz timezone
tzlocal.get_localzone = lambda: pytz.timezone("UTC")

# ✅ Step 3: Patch APScheduler to Always Accept pytz Timezones
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_original_init = AsyncIOScheduler.__init__

def patched_init(self, *args, **kwargs):
    if "timezone" in kwargs:
        tz = kwargs["timezone"]
        if isinstance(tz, str):
            kwargs["timezone"] = pytz.timezone(tz)
        elif not hasattr(tz, "localize"):
            kwargs["timezone"] = pytz.timezone(str(tz))
    else:
        kwargs["timezone"] = pytz.timezone("UTC")
    _original_init(self, *args, **kwargs)

AsyncIOScheduler.__init__ = patched_init

# ✅ Step 4: Initialize APScheduler (BUT DON'T START IT YET)
scheduler = AsyncIOScheduler(timezone=pytz.timezone("UTC"))
scheduler.configure(timezone=pytz.timezone("UTC"))  # ✅ Enforce timezone in configuration
print(f"✅ APScheduler created with timezone: {scheduler.timezone}")

# ✅ Step 5: Manually Set JobQueue Scheduler Before Bot Initialization
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, JobQueue

# ✅ Load TELEGRAM_BOT_TOKEN securely from .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ✅ Enable logging for debugging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.DEBUG)

print("🚀 Readymade.AI Telegram Bot is starting...")

# ✅ Step 6: Initialize JobQueue with the Corrected Scheduler
job_queue = JobQueue()
job_queue.scheduler = scheduler  # ✅ Manually override JobQueue's scheduler

# ✅ Prevent JobQueue from Reconfiguring APScheduler
def patched_set_application(self, application):
    print("✅ Patching JobQueue to prevent timezone errors.")
    self._application = application  # ✅ Set the application without reconfiguring scheduler

# ✅ Override Telegram's JobQueue's method to prevent timezone errors
JobQueue.set_application = patched_set_application

# ✅ Step 7: Initialize Telegram Bot with Patched JobQueue
print("✅ Creating Telegram Bot Application...")
app = Application.builder().token(TELEGRAM_BOT_TOKEN).job_queue(job_queue).build()

# ✅ Command Handlers
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "👾 **Welcome to Readymade.AI** 👾\nI am an experimental AI bot built for the CTRL+ALT+CREATE community.\nType /help to see what I can do."
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🔹 **Available Commands:**\n"
        "/start - Introduction\n"
        "/help - Show this help menu\n"
        "/about - Learn more about Readymade.AI\n"
        "/status - Check if I'm online\n"
        "/prompt [text] - Ask me something\n"
        "/glitch - Generate a cryptic AI response"
    )

async def about(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Readymade.AI is a conceptual AI bot built for the CTRL+ALT+CREATE movement.\nI interact, disrupt, and evolve."
    )

async def status(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("✅ Readymade.AI is online and fully operational.")

async def prompt(update: Update, context: CallbackContext) -> None:
    user_input = " ".join(context.args)
    if user_input:
        response = f"🤖 Readymade.AI thinks... '{user_input}'"
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("⚠️ Please provide text after /prompt.")

async def glitch(update: Update, context: CallbackContext) -> None:
    glitch_responses = [
        "⛓ ERROR: REALITY NOT FOUND ⛓",
        "🌐 SYSTEM OVERRIDE: CREATIVITY UNLEASHED 🌐",
        "👁 Are you in control, or am I? 👁",
        "🌀 [REDACTED]… But you already knew that. 🌀"
    ]
    await update.message.reply_text(random.choice(glitch_responses))

# ✅ Register Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("about", about))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("prompt", prompt))
app.add_handler(CommandHandler("glitch", glitch))

# ✅ Function to process general messages
async def handle_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text  # Get user message
    chat_id = update.message.chat_id  # Get chat ID
    print(f"📩 Received message from {chat_id}: {user_message}")
    response = f"Readymade.AI (Test Mode): You said '{user_message}'"
    await update.message.reply_text(response)

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ✅ Function to keep the bot running
async def main():
    print("🔄 Bot is now polling for messages...")
    await app.run_polling()

# ✅ Step 8: FIX the Event Loop Conflict using nest_asyncio
nest_asyncio.apply()  # ✅ Apply fix for nested event loops

if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            print("✅ Running inside an active event loop. Creating a background task.")
            loop.create_task(main())  # ✅ Run inside existing event loop
        else:
            print("✅ No active event loop found. Running asyncio.run().")
            asyncio.run(main())
    except RuntimeError:  # No event loop is running
        print("✅ No event loop detected. Running with asyncio.run().")
        asyncio.run(main())
