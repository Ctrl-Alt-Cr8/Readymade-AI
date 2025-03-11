import os
import asyncio
import pytz  # Ensure pytz is properly used
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Correct timezone setup using pytz
TIMEZONE = pytz.timezone("UTC")  # This is the proper way

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Hello! Readymade.AI is online.")

async def status(update: Update, context: CallbackContext):
    await update.message.reply_text("✅ Readymade.AI is active and listening.")

async def echo(update: Update, context: CallbackContext):
    await update.message.reply_text(update.message.text)

def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set. Make sure it's in the .env file.")
        return

    # Set up application
    app = Application.builder().token(BOT_TOKEN).build()

    # Correct APScheduler setup
    scheduler = AsyncIOScheduler()
    scheduler.configure(timezone=TIMEZONE)  # This is now correct
    scheduler.start()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("Readymade.AI is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
