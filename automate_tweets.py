import requests
import os
import logging
import random
import threading
import datetime
import time
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from src.connections.twitter_connection import send_tweet, check_rate_limits, verify_credentials
from src.twitter_mentions import setup_twitter_webhook, register_twitter_webhook, subscribe_to_user_activity
from src.visual_generator import VisualGenerator
from src.svg_converter import convert_svg_to_png  # Import the new SVG converter

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
    "error": None,
    "svg_attached": False  # Add a new field to track if SVG was attached
}

# Tracking last attempt time to avoid excessive API calls
last_attempt = {
    "time": None,
    "backoff_until": None
}

# Flag to indicate we're in startup mode - IMPORTANT ADDITION
is_startup_mode = True

# Claude API request function
def generate_tweet():
    """Generate a varied tweet using Claude API"""
    prompt = random.choice(TWEET_TOPICS)  # Pick a random tweet theme
    logger.info(f"Generating tweet with prompt: '{prompt}'")
    
    # Build system message
    system_message = """You are Readymade.AI, an autonomous AI art entity inspired by Marcel Duchamp's readymades.
    Your tweets are philosophical, provocative, and slightly absurd. You challenge conventional thinking 
    through digital dadaism."""
    
    data = {
        "model": "claude-3-5-sonnet-20241022",
        "system": system_message,  # System as top-level parameter
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

def post_tweet():
    """Generate a tweet and post it to Twitter with improved error handling and SVG attachment"""
    global is_startup_mode
    
    # Skip tweeting during startup mode to ensure container passes health check
    if is_startup_mode:
        logger.info("Skipping tweet during startup mode")
        return
        
    # Check if we're in a backoff period
    now = datetime.datetime.now()
    if last_attempt["backoff_until"] and now < last_attempt["backoff_until"]:
        wait_secs = (last_attempt["backoff_until"] - now).total_seconds()
        logger.info(f"🕒 In backoff period. Waiting {wait_secs:.1f} seconds before next attempt.")
        return
    
    # Update last attempt time
    last_attempt["time"] = now
    last_attempt["backoff_until"] = None
    
    # Track number of attempts
    max_attempts = 3
    current_attempt = 0
    
    while current_attempt < max_attempts:
        current_attempt += 1
        logger.info(f"Tweet attempt {current_attempt}/{max_attempts}")
        
        # First, check rate limits with our enhanced checking
        if not check_rate_limits():
            # The enhanced check_rate_limits already logs and handles the rate limit
            # Just set a backoff period
            backoff_until = now + datetime.timedelta(minutes=15)
            last_attempt["backoff_until"] = backoff_until
            logger.warning(f"Rate limit detected. Setting backoff until {backoff_until.strftime('%H:%M:%S')}")
            return
        
        # Generate tweet content
        tweet_content = generate_tweet()
        if not tweet_content:
            if current_attempt < max_attempts:
                logger.warning("Failed to generate tweet content. Retrying...")
                time.sleep(10)  # Short delay before retry
                continue
            else:
                last_tweet["error"] = "Failed to generate tweet content after multiple attempts"
                logger.error("No tweet generated after maximum attempts. Aborting tweet post.")
                return
        
        # Generate SVG content and prepare for attachment (30% chance)
        svg_filename = None
        png_bytes = None
        if random.random() < 0.3:
            try:
                svg_content = VisualGenerator.generate_svg_from_text(tweet_content)
                if svg_content:
                    logger.info("🎨 SVG GENERATION TRIGGERED")
                    logger.info(f"🖼️ SVG Content Length: {len(svg_content)} characters")
                    
                    # Store to a file for inspection
                    svg_dir = "generated_svg"
                    os.makedirs(svg_dir, exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    svg_filename = f"{svg_dir}/tweet_svg_{timestamp}.svg"
                    
                    with open(svg_filename, "w") as f:
                        f.write(svg_content)
                    
                    logger.info(f"💾 SVG Saved to: {svg_filename}")
                    
                    # Convert SVG to PNG for Twitter attachment
                    png_bytes = convert_svg_to_png(svg_content)
                    if png_bytes:
                        logger.info("🖼️ SVG successfully converted to PNG for Twitter attachment")
                    else:
                        logger.warning("⚠️ Failed to convert SVG to PNG, will post tweet without image")
                    
                    # Optional: Log first 100 characters of SVG for verification
                    logger.info(f"📝 SVG Preview: {svg_content[:100]}...")
                else:
                    logger.warning("❌ SVG Generation Failed: No content produced")
            except Exception as e:
                logger.error(f"❌ SVG GENERATION ERROR: {e}")
        
        try:
            # Post to Twitter (with or without media) using our enhanced send_tweet
            tweet_id = send_tweet(tweet_content, media_bytes=png_bytes)
            
            # Update last tweet info
            if tweet_id:
                last_tweet["content"] = tweet_content
                last_tweet["id"] = tweet_id
                last_tweet["timestamp"] = datetime.datetime.now().isoformat()
                last_tweet["error"] = None
                last_tweet["svg_attached"] = png_bytes is not None
                
                # Log SVG association if generated
                if svg_filename:
                    last_tweet["svg_file"] = svg_filename
                    if png_bytes:
                        logger.info(f"🔗 SVG associated with tweet and attached as image: {svg_filename}")
                    else:
                        logger.info(f"🔗 SVG associated with tweet (but not attached): {svg_filename}")
                
                logger.info(f"✅ Tweet posted: {tweet_content}")
                return  # Success! Exit the function
            else:
                if current_attempt < max_attempts:
                    # Apply more intelligent backoff strategy with jitter
                    base_wait = 15 * (2 ** (current_attempt - 1))  # Exponential backoff
                    jitter = random.uniform(0.5, 1.5)  # Add randomness
                    wait_time = int(base_wait * jitter)
                    
                    logger.warning(f"Tweet API call returned no tweet ID. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    last_tweet["error"] = "Tweet API call failed after multiple attempts"
                    logger.error("Failed to post tweet: API call returned no tweet ID")
                    
                    # Set a longer backoff period
                    backoff_until = datetime.datetime.now() + datetime.timedelta(minutes=30)
                    last_attempt["backoff_until"] = backoff_until
                    logger.warning(f"Setting extended backoff until {backoff_until.strftime('%H:%M:%S')}")
                    return
        except Exception as e:
            last_tweet["error"] = str(e)
            logger.exception(f"Error in post_tweet: {e}")
            
            if current_attempt < max_attempts:
                # More intelligent backoff
                base_wait = 30 * (2 ** (current_attempt - 1))
                jitter = random.uniform(0.8, 1.2)
                wait_time = int(base_wait * jitter)
                
                logger.warning(f"Error occurred. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("Maximum retry attempts reached. Giving up.")
                
                # Set a longer backoff period
                backoff_until = datetime.datetime.now() + datetime.timedelta(minutes=20)
                last_attempt["backoff_until"] = backoff_until
                logger.warning(f"Setting extended backoff until {backoff_until.strftime('%H:%M:%S')}")
                return

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
    
    # Add backoff information
    backoff_info = None
    if last_attempt["backoff_until"]:
        now = datetime.datetime.now()
        if now < last_attempt["backoff_until"]:
            backoff_info = {
                "until": last_attempt["backoff_until"].isoformat(),
                "remaining_seconds": int((last_attempt["backoff_until"] - now).total_seconds())
            }
    
    return jsonify({
        "service": "Readymade.AI Twitter Automation",
        "status": "running",
        "startup_mode": is_startup_mode,
        "scheduler": scheduler_info,
        "last_tweet": last_tweet,
        "backoff": backoff_info,
        "twitter_credentials": verify_credentials()
    })

@app.route('/tweet-now')
def tweet_now():
    """Trigger an immediate tweet"""
    try:
        # Check if we're in a backoff period
        if last_attempt["backoff_until"] and datetime.datetime.now() < last_attempt["backoff_until"]:
            remaining = int((last_attempt["backoff_until"] - datetime.datetime.now()).total_seconds())
            return jsonify({
                "success": False,
                "message": f"In backoff period. Try again in {remaining} seconds.",
                "backoff_until": last_attempt["backoff_until"].isoformat(),
                "last_tweet": last_tweet
            })
    
        # Disable startup mode if it's still on
        global is_startup_mode
        if is_startup_mode:
            is_startup_mode = False
            logger.info("Startup mode disabled via tweet-now endpoint")
    
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

@app.route('/register-webhook')
def register_webhook_route():
    """Register the Twitter webhook (admin only)"""
    webhook_url = f"https://readymade-ai-twitter-347263305441.us-central1.run.app/webhook/twitter"
    webhook_id = register_twitter_webhook(webhook_url)
    
    if webhook_id:
        return jsonify({
            "success": True,
            "webhook_id": webhook_id,
            "message": "Webhook registered successfully"
        })
    else:
        return jsonify({
            "success": False,
            "message": "Failed to register webhook"
        }), 500

@app.route('/subscribe')
def subscribe_route():
    """Subscribe to user activity (admin only)"""
    success = subscribe_to_user_activity()
    
    if success:
        return jsonify({
            "success": True,
            "message": "Successfully subscribed to user activity"
        })
    else:
        return jsonify({
            "success": False,
            "message": "Failed to subscribe to user activity"
        }), 500

@app.route('/reset-backoff')
def reset_backoff():
    """Admin route to reset backoff state"""
    last_attempt["backoff_until"] = None
    return jsonify({
        "success": True,
        "message": "Backoff state reset successfully"
    })

@app.route('/disable-startup-mode')
def disable_startup_mode():
    """Admin route to disable startup mode"""
    global is_startup_mode
    is_startup_mode = False
    logger.info("Startup mode disabled via API endpoint")
    return jsonify({
        "success": True,
        "message": "Startup mode disabled successfully"
    })

# Delayed startup function for scheduling tweets
def delayed_startup():
    """Disable startup mode after a delay to ensure health checks pass"""
    global is_startup_mode
    # Wait for 30 seconds before disabling startup mode
    time.sleep(30)
    is_startup_mode = False
    logger.info("Startup mode disabled automatically after delay")

# Set up APScheduler to post tweets every 15 minutes
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(post_tweet, 'interval', minutes=15, name='post_tweet')
    scheduler.start()
    app.scheduler = scheduler  # Store scheduler reference in app
    logger.info("🚀 Automated tweet scheduler started. Tweets will be posted every 15 minutes.")
    
    # Start the delayed startup thread to eventually enable tweeting
    startup_thread = threading.Thread(target=delayed_startup)
    startup_thread.daemon = True
    startup_thread.start()

if __name__ == "__main__":
    # Set up Twitter webhook handling
    setup_twitter_webhook(app)
    
    # Start the scheduler in a background thread
    start_scheduler()
    
    # Start the Flask app to keep the service alive
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
