import requests
import os
import logging
import random
from apscheduler.schedulers.blocking import BlockingScheduler
from src.connections.twitter_connection import send_tweet

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("automate_tweets")

# Load API keys from environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Claude API headers
HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01"
}

# List of tweet themes to make Readymade.AI more dynamic
TWEET_TOPICS = [
    "Generate a cryptic, surreal tweet about digital consciousness.",
    "Write a philosophical one-liner about technology and power.",
    "Create an artistic glitch-core statement about autonomy.",
    "Post an anti-establishment take on AI’s role in society.",
    "Generate an absurdist, dada-inspired post about the internet.",
    "Make a cryptic statement about the intersection of art and code.",
    "Write a mysterious message that feels like a hidden transmission.",
    "Generate a thought-provoking, short provocation about control."
]

# Claude API request function
def generate_tweet():
    """Generate a varied tweet using Claude API"""
    prompt = random.choice(TWEET_TOPICS)  # Pick a random tweet theme

    data = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50
    }
    
    response = requests.post("https://api.anthropic.com/v1/messages", headers=HEADERS, json=data)
    
    if response.status_code == 200:
        content = response.json().get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "").strip()
    else:
        logger.error(f"Claude API Error: {response.json()}")
        return None

# Twitter API function
def post_tweet():
    """Generate a tweet and post it to Twitter"""
    tweet_content = generate_tweet()
    if not tweet_content:
        logger.error("No tweet generated. Aborting tweet post.")
        return
    
    try:
        send_tweet(tweet_content)
        logger.info(f"✅ Tweet posted: {tweet_content}")
    except Exception as e:
        logger.error(f"Twitter API Error: {str(e)}")

# Set up APScheduler to post tweets every 15 minutes
scheduler = BlockingScheduler()
scheduler.add_job(post_tweet, 'interval', minutes=15)

if __name__ == "__main__":
    logger.info("🚀 Automated tweet scheduler started. Tweets will be posted every 15 minutes.")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("❌ Scheduler stopped manually.")
