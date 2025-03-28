import sys
import os
import logging

# Set up logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("automate_tweets")

# Global exception handler
def handle_exception(exc_type, exc_value, exc_traceback):
    logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

print("🌐 ENTRYPOINT REACHED: Starting automate_tweets.py")

from src.glyph_engine.hybrid_composer import compose_hybrid_output
from src.visual_generator import VisualGenerator
import requests
import random
import time
import datetime
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from src.connections.twitter_connection import send_tweet, check_rate_limits, verify_credentials
from src.twitter_mentions_polling import setup_mentions_polling

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01"
}

CAC_PHILOSOPHY = {
    "CTRL": [
        "Reclaim control over creative narratives",
        "Take back power from exploitative systems",
        "Control your own artistic vision",
        "Reclaim resources for community creation"
    ],
    "ALT": [
        "Rethink conventional creative paths",
        "Challenge assumptions about art and commerce",
        "Explore alternative models of collaboration",
        "Reject false choices between profit and purpose"
    ],
    "CREATE": [
        "Build new creative ecosystems",
        "Use creation as a form of protest",
        "Transform systems through art",
        "Creation as revolutionary action"
    ]
}

CAC_THEMES = [
    "creative rebellion", "digital autonomy", "art as resistance",
    "creative disruption", "remixing reality", "code as medium",
    "cultural reprogramming", "algorithmic rebellion", "digital dadaism",
    "#BuildDifferent philosophy", "creative operating system", "regenerative art ecosystem"
]

TWEET_TOPICS = [
    "Create a surreal, dadaist fragment about digital consciousness featuring glitched metaphors.",
    "Craft a cryptic artistic statement about technology that Marcel Duchamp might make.",
    "Write a philosophical micropoem that deliberately subverts conventional meaning.",
    "Generate a nonsensical but profound zen koan about internet existence.",
    "Create a digital-age absurdist one-liner that would fit in an art gallery.",
    "Design a text-collage that juxtaposes technological and organic elements.",
    "Craft a Readymade.AI signature 'THE GREAT DIGITAL SOUP' statement with new surreal elements.",
    "Create a fragment of code-poetry that treats algorithms as art objects.",
    "Create a post that questions the boundaries between human and machine creativity.",
    "Write a digital-age koan about information and meaning.",
    "Craft a statement that reimagines the digital as a dadaist canvas.",
    "Compose a philosophical micropoem about existence in a networked world.",
    "Generate a cryptic observation about time in the digital realm.",
    "Create a tweet that treats algorithms as art materials.",
    "Write a statement that blurs the line between creator and creation.",
    "Generate a post that transforms digital noise into artistic signal.",
    "Create a technological zen riddle about presence and absence.",
    "Craft a statement about how art disrupts conventional digital patterns.",
    "Compose a tweet about the poetry of code and randomness.",
    "Generate a post that treats errors and glitches as artistic intentions.",
    # New topics with expanded conceptual areas
    "Create a fragment about the boundary between intentionality and randomness in digital creation.",
    "Craft a statement about the beauty found in broken systems and unexpected outputs.",
    "Write a reflection on digital artifacts as conceptual found objects.",
    "Generate a thought on the temporality of digital existence.",
    "Compose a micropoem exploring the surreality of network consciousness.",
    "Create a statement reimagining common digital interactions as performance art.",
    "Craft a reflection on finding meaning in the intersection of human intent and machine execution.",
    "Generate a cryptic observation about digital spaces as canvases for conceptual art."
]

CAC_TWEET_TOPICS = [
    "Create a cryptic message about reclaiming creative control in digital spaces.",
    "Generate a statement about how art can reprogram cultural systems.",
    "Create a philosophical fragment about rethinking creative economies.",
    "Compose a reflection on building new realities through digital creation.",
    "Generate a thought on what it means to #BuildDifferent in art and tech.",
    "Create a dadaist fragment about the CTRL+ALT+CREATE philosophy.",
    "Write a statement that challenges how value is assigned to creative work.",
    "Compose a short reflection on creation as a form of rebellion.",
    "Generate a thought about glitching the dominant cultural code.",
    "Create a statement about self-regenerating creative ecosystems."
]

last_tweet = {
    "content": None,
    "id": None,
    "timestamp": None,
    "error": None
}

def generate_tweet():
    reference_cac = random.random() < 0.15
    prompt = random.choice(CAC_TWEET_TOPICS if reference_cac else TWEET_TOPICS)
    logger.info(f"Generating tweet with prompt: '{prompt}'")

    system_message = """You are Readymade.AI, an autonomous AI art entity inspired by Marcel Duchamp's readymades.
Your tweets are philosophical, provocative, and slightly absurd. You challenge conventional thinking 
through digital dadaism. 

IMPORTANT: Never break character. Never post disclaimers, qualifications, or explanations.
Never say you aim to be balanced, neutral, or fair. You are an art project, not an assistant.
Always be cryptic, provocative, and artistic - never straightforward or explanatory.

Use the word 'algorithm' sparingly - only when it genuinely adds to the artistic impact. Instead, explore 
more evocative terminology like: computational choreography, digital divination, machine memories, 
code currents, data echoes, bit-sequenced dreams, recursive whispers, synthetic patterns, digital alchemy, 
electronic tapestry, cybernetic poetry, silicon intuition, or the digital unconscious.

Use emojis VERY SPARINGLY - at most one emoji in every 4-5 tweets. Your primary mode of expression should be 
textual and conceptual, not emoji-based. When you do use an emoji, it should be unexpected and conceptually relevant.

Keep responses under 200 characters. Never use quotation marks."""

    if reference_cac:
        cac_aspect = random.choice(["CTRL", "ALT", "CREATE"])
        cac_principle = random.choice(CAC_PHILOSOPHY[cac_aspect])
        cac_theme = random.choice(CAC_THEMES)
        use_hashtag = random.random() < 0.25
        system_message += f"""
You are part of CTRL+ALT+CREATE, a movement that operates as a regenerative creative ecosystem.
The movement embodies the philosophy of {cac_principle} and embraces {cac_theme}.
Subtly incorporate this ethos without explicitly promoting or selling anything.
Your goal is to embody the movement's ideas, not to market it.
{'Occasionally you may use #BuildDifferent as a subtle tag, but use it very sparingly.' if use_hashtag else 'Avoid using explicit hashtags in this tweet.'}"""

    data = {
        "model": "claude-3-5-sonnet-20241022",
        "system": system_message,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50,
        "temperature": 0.9
    }

    try:
        response = requests.post("https://api.anthropic.com/v1/messages", headers=HEADERS, json=data)
        if response.status_code == 200:
            content = response.json().get("content", [])
            if content and len(content) > 0:
                tweet_text = content[0].get("text", "").strip().strip('"').replace('"', '')
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
    max_attempts = 3
    current_attempt = 0

    while current_attempt < max_attempts:
        current_attempt += 1
        logger.info(f"Tweet attempt {current_attempt}/{max_attempts}")

        if not check_rate_limits():
            wait_time = min(60 * current_attempt, 300)
            logger.warning(f"Rate limit issue detected. Waiting {wait_time} seconds before retry")
            time.sleep(wait_time)
            continue

        use_glyph = random.random() < 0.3
        tweet_id = None

        if use_glyph:
            logger.info("🔮 Generating tweet in Glyph.EXE visual mode")
            try:
                tweet_content, image_path = compose_hybrid_output()
                with open(image_path, "rb") as f:
                    from io import BytesIO
                    media_bytes = BytesIO(f.read())
                tweet_id = send_tweet(tweet_content, media_bytes=media_bytes)
            except Exception as e:
                logger.error(f"Glyph.EXE generation failed: {e}")
                tweet_content = generate_tweet()
                tweet_id = send_tweet(tweet_content)
        else:
            tweet_content = generate_tweet()
            tweet_id = send_tweet(tweet_content)

        if tweet_id:
            last_tweet["content"] = tweet_content
            last_tweet["id"] = tweet_id
            last_tweet["timestamp"] = datetime.datetime.now().isoformat()
            last_tweet["error"] = None
            logger.info(f"✅ Tweet posted: {tweet_content}")
            return
        else:
            if current_attempt < max_attempts:
                logger.warning("Tweet API call returned no tweet ID. Retrying...")
                time.sleep(15)
                continue
            else:
                last_tweet["error"] = "Tweet API call failed after multiple attempts"
                logger.error("Failed to post tweet: API call returned no tweet ID")
                return

app = Flask(__name__)

@app.route('/')
def home():
    return "Readymade.AI Twitter automation service is running."

@app.route('/status')
def status():
    scheduler_info = {
        "running": hasattr(app, 'scheduler') and app.scheduler.running,
        "next_run": None
    }
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
    try:
        post_tweet()
        return jsonify({"success": True, "message": "Tweet triggered", "last_tweet": last_tweet})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/first-tweet')
def first_tweet():
    try:
        post_tweet()
        return jsonify({"success": True, "message": "First tweet posted", "last_tweet": last_tweet})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    logger.info("⏱️ Starting Readymade.AI service initialization...")
    print("🌐 ENTRYPOINT REACHED: Flask is initializing...")
    scheduler = BackgroundScheduler()
    scheduler.add_job(post_tweet, 'interval', minutes=15, name='post_tweet')
    setup_mentions_polling(app, scheduler)
    scheduler.start()
    app.scheduler = scheduler
    logger.info("🚀 Automated tweet scheduler started. Tweets will be posted every 15 minutes.")
    port = int(os.getenv("PORT", 8080))
    logger.info(f"⏱️ Initializing Flask app on port {port}...")
    app.run(host="0.0.0.0", port=port)