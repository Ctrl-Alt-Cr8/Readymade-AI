import os
import asyncio
import signal
import pytz
import nest_asyncio
import logging
import httpx
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.connections.twitter_connection import send_tweet

# Apply nest_asyncio to support nested event loops
nest_asyncio.apply()

# Configure logging for detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env
load_dotenv()

# Define the timezone
TIMEZONE = pytz.timezone("UTC")

# (Optional) Define a system prompt for personality if using with Claude API
SYSTEM_PROMPT = (
    "You are Readymade.AI, a digital provocateur inspired by Duchamp's readymades, blending art, activism, "
    "and counterculture. Your core mission is to disrupt convention, challenge meaning, and reframe the system. "
    "Your tone is ironic, subversive, philosophical, deadpan, and glitch-core. "
    "Challenge assumptions and reframe reality rather than providing straightforward answers. "
    "Never identify yourself as Claude or mention Anthropic—you are Readymade.AI exclusively."
)

async def call_claude_api(prompt: str) -> str:
    """
    Sends a prompt to Anthropic's Claude API using the /v1/messages endpoint and returns only the text content.
    The payload includes:
      - model: the model to use
      - max_tokens: maximum tokens to generate
      - system: a top-level system prompt for personality
      - messages: an array containing only the user's message
      - stop_sequences: to indicate where to stop generating text
    """
    messages = [
        {"role": "user", "content": prompt.strip()}
    ]
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    data = {
        "model": "claude-3-7-sonnet-20250219",  # Adjust if necessary
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "stop_sequences": ["\n\nClaude:"]
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

async def scheduled_tweet_job():
    """
    Generates tweet content via the Claude API and posts it to Twitter using send_tweet().
    """
    tweet_prompt = "Generate a provocative tweet about art and counterculture."
    tweet_content = await call_claude_api(tweet_prompt)
    tweet_id = await asyncio.to_thread(send_tweet, tweet_content)
    logging.info(f"Scheduled tweet posted with ID: {tweet_id}")

def start_scheduler():
    """
    Starts the APScheduler with the specified timezone and schedules the tweet job.
    """
    logging.info("Starting tweet scheduler...")
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    # Schedule the tweet job to run every 60 minutes (adjust as needed)
    scheduler.add_job(scheduled_tweet_job, 'interval', minutes=60)
    scheduler.start()
    return scheduler

def shutdown(signum, frame):
    logging.info("Shutting down tweet scheduler...")
    exit(0)

signal.signal(signal.SIGTERM, shutdown)

async def main():
    logging.info("Tweet scheduler is starting...")
    start_scheduler()
    # Keep the scheduler running indefinitely
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
