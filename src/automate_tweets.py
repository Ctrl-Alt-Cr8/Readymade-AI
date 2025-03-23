import requests
import os
import logging
import random
import threading
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from src.connections.twitter_connection import send_tweet, check_rate_limits, verify_credentials
from src.twitter_mentions_polling import setup_mentions_polling

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
    "Post an anti-establishment take on AI's role in society.",
    "Generate an absurdist, dada-inspired post about the internet.",
    "Make a cryptic statement about the intersection of art and code.",
    "Write a mysterious message that feels like a hidden transmission.",
    "Generate a thought-provoking, short provocation about control."
]

# Last successfully posted tweet
last_tweet = {
    "content": None,
    "id": None,
    "timestamp": None,
    "error": None
}

# Claude API request function
def generate_tweet():
    """Generate a varied tweet using Claude API"""
    prompt = random.choice(TWEET_TOPICS)  # Pick a random tweet theme
    logger.info(f"Generating tweet with prompt: '{prompt}'")

    data = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50
    }
    
    try:
        response = requests.post("https://api.anthropic.com/v1/messages", headers=HEADERS, json=data)
        
        if response.status_code == 200:
            content = response.json().get("content", [])
            if content and len(content) > 0:
                tweet_text = content[0].get("text", "").strip()
                
                # Remove quotation marks if present
                if tweet_text.startswith('"') and tweet_text.endswith('"'):
                    tweet_text = tweet_text[1:-1].strip()
                
                # Remove any remaining quotes
                tweet_text = tweet_text.replace('"', '')
                
                logger.info(f"Generated tweet text: '{tweet_text}'")
                return tweet_text
            else:
                logger.error(f"No content in Claude API response: {response.json()}")
        else:
            logger.error(f"Claude API Error: Status {response.status_code}, Response: {response.text}")
    except Exception as e:
        logger.exception(f"Exception in generate_tweet: {e}")
    
    return None

# Twitter API function
def post_tweet():
    """Generate a tweet and post it to Twitter"""
    # First, check rate limits
    check_rate_limits()
    
    # Generate tweet content
    tweet_content = generate_tweet()
    if not tweet_content:
        last_tweet["error"] = "Failed to generate tweet content"
        logger.error("No tweet generated. Aborting tweet post.")
        return
    
    try:
        # Post to Twitter
        tweet_id = send_tweet(tweet_content)
        
        # Update last tweet info
        if tweet_id:
            import datetime
            last_tweet["content"] = tweet_content
            last_tweet["id"] = tweet_id
            last_tweet["timestamp"] = datetime.datetime.now().isoformat()
            last_tweet["error"] = None
            logger.info(f"✅ Tweet posted: {tweet_content}")
        else:
            last_tweet["error"] = "Tweet API call failed"
            logger.error("Failed to post tweet: API call returned no tweet ID")
    except Exception as e:
        last_tweet["error"] = str(e)
        logger.exception(f"Error in post_tweet: {e}")

# Set up a Flask app for health checks and status
app = Flask(__name__)

@app.route('/')
def home():
    return "Readymade.AI Twitter automation service is running."

@app.route('/status')
def status():
    """Return status information about the service"""
    scheduler_info = {
        "running": hasattr(app, 'scheduler') and app.scheduler.running,
        "next_run": None
    }
    
    # Get next run time for the tweet job if scheduler is running
    if hasattr(app, 'scheduler') and app.scheduler.running:
        for job in app.scheduler.get_jobs():
            if job.name == 'post_tweet':
                scheduler_info["next_run"] = job.next_run_time.isoformat() if job.next_run_time else None
    
    return jsonify({
        "service": "Readymade.AI Twitter Automation",
        "status": "running",
        "scheduler": scheduler_info,
        "last_tweet": last_tweet,
        "twitter_credentials": verify_credentials()
    })

@app.route('/tweet-now')
def tweet_now():
    """Trigger an immediate tweet"""
    try:
        post_tweet()
        return jsonify({
            "success": True,
            "message": "Tweet triggered",
            "last_tweet": last_tweet
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Set up APScheduler to post tweets every 15 minutes
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(post_tweet, 'interval', minutes=15, name='post_tweet')
    scheduler.start()
    app.scheduler = scheduler  # Store scheduler reference in app
    logger.info("🚀 Automated tweet scheduler started. Tweets will be posted every 15 minutes.")
    
    # Post an initial tweet to verify everything is working
    post_tweet()

if __name__ == "__main__":
    # Start the scheduler in a background thread
    scheduler = BackgroundScheduler()
    scheduler.add_job(post_tweet, 'interval', minutes=15, name='post_tweet')
    
    # Set up Twitter mentions polling
    setup_mentions_polling(app, scheduler)
    
    # Start the scheduler
    scheduler.start()
    app.scheduler = scheduler
    logger.info("🚀 Automated tweet scheduler started. Tweets will be posted every 15 minutes.")
    
    # Post an initial tweet to verify everything is working
    post_tweet()
    
    # Start the Flask app to keep the service alive
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)