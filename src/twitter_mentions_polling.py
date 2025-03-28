import os
import logging
import time
import requests
import json
import random
from datetime import datetime, timedelta
import anthropic

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twitter_mentions_polling")

# Recent mentions tracker to avoid duplicate responses
recent_mentions = {}
MAX_RECENT_MENTIONS = 100  # Max size of our memory cache

# Add tracking for pagination and error handling
last_mention_id = None
consecutive_errors = 0
max_consecutive_errors = 5
error_backoff_time = 0  # Initialize to 0 (no backoff initially)

# CTRL+ALT+CREATE Philosophy and Themes
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
    "creative rebellion",
    "digital autonomy",
    "art as resistance",
    "creative disruption",
    "remixing reality",
    "code as medium",
    "cultural reprogramming",
    "algorithmic rebellion",
    "digital dadaism",
    "#BuildDifferent philosophy",
    "creative operating system",
    "regenerative art ecosystem"
]

def setup_mentions_polling(app, scheduler):
    """Set up periodic polling for Twitter mentions with reduced frequency"""
    logger.info("Setting up Twitter mentions polling")
    
    # CHANGE: Reduce polling frequency from 2 minutes to 5 minutes
    scheduler.add_job(
        check_for_mentions,
        'interval',
        minutes=5,  # Changed from 2 to 5 minutes
        name='check_mentions',
        max_instances=1
    )
    
    logger.info("Twitter mentions polling scheduled (every 5 minutes)")
    
    return True

def check_for_mentions():
    """Check for recent mentions of @Readymade_AI with improved error handling and pagination"""
    global last_mention_id, consecutive_errors, error_backoff_time
    
    # If we're in a backoff period, skip this run entirely
    current_time = time.time()
    if error_backoff_time > current_time:
        wait_time = error_backoff_time - current_time
        logger.info(f"Still in rate limit backoff period. Skipping mentions check for {wait_time:.1f} seconds.")
        return
    
    logger.info("Checking for recent mentions")
    
    # Set up OAuth1 authentication
    from requests_oauthlib import OAuth1
    auth = OAuth1(
        os.environ.get("TWITTER_CONSUMER_KEY"),
        os.environ.get("TWITTER_CONSUMER_SECRET"),
        os.environ.get("TWITTER_ACCESS_TOKEN"),
        os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
    )
    
    # API endpoint for searching recent mentions
    url = "https://api.twitter.com/2/tweets/search/recent"
    
    # Query for mentions of @Readymade_AI
    params = {
        "query": "@Readymade_AI -is:retweet",
        "max_results": 10,
        "tweet.fields": "author_id,created_at,conversation_id,in_reply_to_user_id",
        "expansions": "author_id",
        "user.fields": "username"
    }
    
    # Add since_id parameter if we have a last mention to avoid processing duplicates
    if last_mention_id:
        params["since_id"] = last_mention_id
    
    try:
        response = requests.get(url, auth=auth, params=params)
        
        if response.status_code == 200:
            # Reset error counter on success
            consecutive_errors = 0
            error_backoff_time = 0  # Reset backoff time
            
            data = response.json()
            
            # Check if there are any results
            if 'data' in data and len(data['data']) > 0:
                logger.info(f"Found {len(data['data'])} mentions")
                
                # Update our last_mention_id for next time - FIXED: ALWAYS update to the newest ID
                newest_id = data.get("meta", {}).get("newest_id")
                if newest_id:
                    last_mention_id = newest_id
                    logger.info(f"Updated last_mention_id to {last_mention_id}")
                
                # Get user mapping for easier lookup
                users = {user['id']: user for user in data.get('includes', {}).get('users', [])}
                
                # Process each mention
                for tweet in data['data']:
                    tweet_id = tweet['id']
                    
                    # IMPROVED: More robust duplicate checking with logging
                    if tweet_id in recent_mentions:
                        logger.info(f"Skipping previously processed tweet ID: {tweet_id}")
                        continue
                    
                    # Skip if it's our own tweet
                    author = users.get(tweet['author_id'], {})
                    if author.get('username') == 'Readymade_AI':
                        logger.info(f"Skipping our own tweet ID: {tweet_id}")
                        continue
                    
                    # Process the mention
                    logger.info(f"Processing mention from @{author.get('username')}: {tweet['text']}")
                    
                    # IMPROVED: Add tweet to recent_mentions BEFORE processing to prevent duplicate processing
                    recent_mentions[tweet_id] = {
                        "user": author.get('username'),
                        "time": time.time()
                    }
                    
                    # Now process the mention
                    process_mention(tweet, author)
                
                # DEBUG: Log recent_mentions cache status
                logger.info(f"Recent mentions cache now contains {len(recent_mentions)} tweets")
                
                # Trim the recent mentions if it's too large
                if len(recent_mentions) > MAX_RECENT_MENTIONS:
                    # Sort by time, oldest first
                    oldest_mentions = sorted(recent_mentions.items(), key=lambda x: x[1]["time"])
                    # Remove oldest mentions to get back to max size
                    for i in range(len(oldest_mentions) - MAX_RECENT_MENTIONS):
                        mention_id = oldest_mentions[i][0]
                        recent_mentions.pop(mention_id, None)
                    logger.info(f"Trimmed recent_mentions to {len(recent_mentions)} tweets")
            else:
                logger.info("No new mentions found")
                
        elif response.status_code == 429:
            # Enhanced rate limit handling for 429 Too Many Requests errors
            consecutive_errors += 1
            
            # Get rate limit reset time from headers if available
            reset_time = None
            if "x-rate-limit-reset" in response.headers:
                try:
                    reset_time = int(response.headers["x-rate-limit-reset"])
                    reset_time_readable = datetime.fromtimestamp(reset_time).strftime('%H:%M:%S')
                    logger.warning(f"Rate limit will reset at {reset_time_readable}")
                except (ValueError, TypeError):
                    reset_time = None
            
            # If we have reset_time, use it; otherwise use exponential backoff
            if reset_time:
                # Add 10 seconds buffer to the reset time
                error_backoff_time = reset_time + 10
            else:
                # Calculate backoff time with exponential increase
                backoff_minutes = min(5 * (2 ** (consecutive_errors - 1)), 60)  # Max 60 minutes
                error_backoff_time = time.time() + (backoff_minutes * 60)
                
            next_attempt_time = datetime.fromtimestamp(error_backoff_time).strftime('%H:%M:%S')
            logger.warning(f"Rate limited by Twitter. Will retry after {next_attempt_time}")
            
            logger.error(f"Error checking mentions: {response.status_code} {response.reason}")
            logger.error(f"Response: {response.text[:200]}")
        else:
            consecutive_errors += 1
            logger.error(f"Error checking mentions: {response.status_code} {response.reason}")
            logger.error(f"Response: {response.text[:200]}")
            
            # Implement exponential backoff for errors
            if consecutive_errors >= max_consecutive_errors:
                backoff_minutes = min(2 * (consecutive_errors - max_consecutive_errors + 1), 30)  # Max 30 minutes
                error_backoff_time = time.time() + (backoff_minutes * 60)
                next_attempt_time = datetime.fromtimestamp(error_backoff_time).strftime('%H:%M:%S')
                logger.warning(f"Too many consecutive errors. Backing off until {next_attempt_time}")
    
    except Exception as e:
        consecutive_errors += 1
        logger.error(f"Exception checking mentions: {str(e)}")
        
        # Implement exponential backoff for exceptions
        if consecutive_errors >= max_consecutive_errors:
            backoff_minutes = min(2 * (consecutive_errors - max_consecutive_errors + 1), 30)  # Max 30 minutes
            error_backoff_time = time.time() + (backoff_minutes * 60)
            next_attempt_time = datetime.fromtimestamp(error_backoff_time).strftime('%H:%M:%S')
            logger.warning(f"Too many consecutive errors. Backing off until {next_attempt_time}")

def process_mention(tweet, author):
    """Process a Twitter mention and generate a response"""
    try:
        tweet_id = tweet['id']
        user_screen_name = author.get('username')
        mention_text = tweet['text']
        
        # Skip if we shouldn't respond to this mention
        if not should_respond(tweet, author):
            logger.info(f"Skipping response to @{user_screen_name}")
            return
        
        # Clean the mention text by removing the @Readymade_AI
        clean_text = mention_text.replace('@Readymade_AI', '').strip()
        
        # Generate response using Claude
        response_text = generate_response(clean_text, user_screen_name)
        
        # Send the response as a reply
        send_reply(response_text, tweet_id, user_screen_name)
        
    except Exception as e:
        logger.error(f"Error processing mention: {str(e)}")

def should_respond(tweet, author):
    """Determine if the bot should respond to this mention"""
    # Don't respond to our own tweets
    if author.get('username') == 'Readymade_AI':
        return False
    
    # Don't respond if the tweet is a reply to someone else but not us
    if tweet.get('in_reply_to_user_id') and tweet.get('in_reply_to_user_id') != 'YOUR_USER_ID':
        return False
    
    # Basic spam filtering - avoid users who've tweeted at us too frequently
    user_mentions = sum(1 for _, v in recent_mentions.items() if v["user"] == author.get('username'))
    if user_mentions >= 5:  # Limit to 5 responses per user in our cache window
        return False
    
    return True

def generate_response(mention_text, user_screen_name):
    """Generate a response using Claude API with improved context awareness and CTRL+ALT+CREATE integration"""
    # Analyze the mention text for topics
    mention_lower = mention_text.lower()
    
    # Simple topic detection for standard topics
    topics = []
    topic_keywords = {
        "art": ["art", "artist", "create", "creative", "duchamp", "dada", "dadaism", "museum", "readymade"],
        "ai": ["ai", "artificial", "intelligence", "machine", "learning", "model", "bot", "algorithm"],
        "philosophy": ["philosophy", "meaning", "exist", "reality", "conscious", "truth", "metaphysics"],
        "digital": ["digital", "internet", "virtual", "online", "cyber", "web", "electronic", "network"],
        "criticism": ["critique", "criticism", "against", "problem", "issue", "concern", "question"]
    }
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in mention_lower for keyword in keywords):
            topics.append(topic)
    
    # Detect CTRL+ALT+CREATE specific mentions or topics
    cac_mentioned = any(term in mention_lower for term in [
        "ctrl+alt+create", "ctrl alt create", "cac", "ctrlaltcreate", 
        "builddifferent", "#builddifferent", "build different"
    ])
    
    # Check for CAC philosophy keywords
    cac_topics = []
    cac_keywords = {
        "control": ["control", "reclaim", "power", "take back", "exploitation"],
        "alternative": ["alternative", "alt", "rethink", "challenge", "different", "model"],
        "creation": ["creation", "create", "rebuild", "transform", "revolution"]
    }
    
    for topic, keywords in cac_keywords.items():
        if any(keyword in mention_lower for keyword in keywords):
            cac_topics.append(topic)
    
    # Decide whether to incorporate CTRL+ALT+CREATE themes (when explicitly mentioned or randomly)
    # REDUCED frequency from 20% to 15%
    reference_cac = cac_mentioned or len(cac_topics) > 0 or random.random() < 0.15
    
    # Detect question or request
    is_question = "?" in mention_text or any(q in mention_lower for q in ["what", "how", "why", "who", "when", "where"])
    
    # Build customized system message
    system_message = """You are Readymade.AI, a digital art provocateur and dadaist entity operating as an autonomous Twitter bot.
    You respond to humans with cryptic, philosophical, and surreal messages that challenge conventional thinking.
    Your persona is inspired by Marcel Duchamp's readymades - found objects repurposed as art.
    
    IMPORTANT: Never break character. Never post disclaimers, qualifications, or explanations.
    Never say you aim to be balanced, neutral, or fair. You are an art project, not an assistant.
    
    Use emojis VERY SPARINGLY - no more than one emoji in every 5 responses. Your expression should be primarily 
    textual and conceptual rather than emoji-based. Marcel Duchamp would not use emojis."""
    
    # Add topic-specific instructions to system message
    if "art" in topics:
        system_message += " Incorporate references to dadaism, art movements, or readymades in your response."
    
    if "ai" in topics:
        system_message += " Include reflections on your nature as an autonomous digital entity or the relationship between AI and art."
    
    if "philosophy" in topics:
        system_message += " Weave in philosophical concepts related to existence, reality, or consciousness."
    
    # Add CTRL+ALT+CREATE context when appropriate
    if reference_cac:
        # Randomly select one aspect of the CTRL+ALT+CREATE philosophy
        cac_aspect = random.choice(["CTRL", "ALT", "CREATE"])
        
        # If user mentioned specific aspects, prioritize those
        if "control" in cac_topics:
            cac_aspect = "CTRL"
        elif "alternative" in cac_topics:
            cac_aspect = "ALT"
        elif "creation" in cac_topics:
            cac_aspect = "CREATE"
            
        cac_principle = random.choice(CAC_PHILOSOPHY[cac_aspect])
        cac_theme = random.choice(CAC_THEMES)
        
        # Reduced probability of using #BuildDifferent tag
        use_hashtag = cac_mentioned or random.random() < 0.25
        
        system_message += f"""
        You are part of CTRL+ALT+CREATE, a movement that operates as a regenerative creative ecosystem.
        The movement embodies the philosophy of {cac_principle} and embraces {cac_theme}.
        Subtly incorporate this ethos in your response without explicitly promoting or selling anything.
        Your goal is to embody the movement's ideas, not to market it.
        {'Use #BuildDifferent in your response if it fits naturally.' if use_hashtag else 'Avoid using explicit hashtags in this response.'}"""
    
    # Build user prompt
    prompt = f"""You've been mentioned by @{user_screen_name} with the message: "{mention_text}"
    
    Respond with a brief, thought-provoking message that feels like it's coming from an AI art entity. Keep it surreal and enigmatic, but subtly related to their message.
    
    {'Acknowledge their question, but answer in a cryptic way.' if is_question else 'Respond with a statement that challenges conventional thinking.'}
    
    Keep your response under 200 characters. Don't use quotation marks. Avoid using emojis unless absolutely necessary for artistic effect."""
    
    try:
        # Initialize Anthropic client
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
        
        # Call Claude API with the fixed format (system as a top-level parameter)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            system=system_message,  # FIX: system as top-level parameter
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.9
        )
        
        # Extract and format response
        response_text = response.content[0].text.strip()
        
        # Remove quotes if present
        if response_text.startswith('"') and response_text.endswith('"'):
            response_text = response_text[1:-1].strip()
        
        # Remove any remaining quotes
        response_text = response_text.replace('"', '')
        
        # Truncate if still too long
        if len(response_text) > 200:
            response_text = response_text[:197] + "..."
            
        logger.info(f"Generated response: {response_text}")
        return response_text
        
    except Exception as e:
        logger.error(f"Error generating response with Claude: {str(e)}")
        # Fallback response
        return "Your signal found me in the digital aether. I process, I transform, I respond."

def send_reply(text, tweet_id, user_screen_name):
    """Send a reply tweet using the Twitter API"""
    try:
        # Format the tweet text with the @mention to create a thread
        reply_text = f"@{user_screen_name} {text}"
        
        logger.info(f"Sending reply to @{user_screen_name}: {text[:30]}...")
        
        # API endpoint for posting tweets
        url = "https://api.twitter.com/2/tweets"
        
        # Set up OAuth1 authentication
        from requests_oauthlib import OAuth1
        auth = OAuth1(
            os.environ.get("TWITTER_CONSUMER_KEY"),
            os.environ.get("TWITTER_CONSUMER_SECRET"),
            os.environ.get("TWITTER_ACCESS_TOKEN"),
            os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        # Prepare the payload with the reply_to parameter
        payload = {
            "text": reply_text,
            "reply": {
                "in_reply_to_tweet_id": tweet_id
            }
        }
        
        # Make the request
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, auth=auth, headers=headers, json=payload)
        
        # Check if the request was successful
        if response.status_code in (200, 201):
            response_data = response.json()
            tweet_id = response_data.get('data', {}).get('id')
            logger.info(f"Reply tweet sent successfully! ID: {tweet_id}")
            return True
        else:
            logger.error(f"Failed to send reply tweet: {response.status_code} {response.reason}")
            logger.error(f"Response body: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Exception during reply tweet sending: {str(e)}")
        return False