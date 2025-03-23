import os
import logging
import time
import requests
import json
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twitter_mentions_polling")

# Recent mentions tracker to avoid duplicate responses
recent_mentions = {}
MAX_RECENT_MENTIONS = 100  # Max size of our memory cache

def setup_mentions_polling(app, scheduler):
    """Set up periodic polling for Twitter mentions"""
    logger.info("Setting up Twitter mentions polling")
    
    # Add job to check for mentions every 2 minutes
    scheduler.add_job(
        check_for_mentions,
        'interval',
        minutes=2,
        name='check_mentions',
        max_instances=1
    )
    
    logger.info("Twitter mentions polling scheduled")
    
    return True

def check_for_mentions():
    """Check for recent mentions of @Readymade_AI"""
    logger.info("Checking for recent mentions")
    
    # Get mentions from the last 10 minutes (adjust as needed)
    since_time = (datetime.utcnow() - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
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
    
    try:
        response = requests.get(url, auth=auth, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if there are any results
            if 'data' in data and len(data['data']) > 0:
                logger.info(f"Found {len(data['data'])} mentions")
                
                # Get user mapping for easier lookup
                users = {user['id']: user for user in data.get('includes', {}).get('users', [])}
                
                # Process each mention
                for tweet in data['data']:
                    # Skip if already processed
                    if tweet['id'] in recent_mentions:
                        continue
                        
                    # Skip if it's our own tweet
                    author = users.get(tweet['author_id'], {})
                    if author.get('username') == 'Readymade_AI':
                        continue
                    
                    # Process the mention
                    logger.info(f"Processing mention from @{author.get('username')}: {tweet['text']}")
                    process_mention(tweet, author)
                    
                    # Add to recent mentions
                    recent_mentions[tweet['id']] = {
                        "user": author.get('username'),
                        "time": time.time()
                    }
                
                # Trim the recent mentions if it's too large
                if len(recent_mentions) > MAX_RECENT_MENTIONS:
                    oldest_key = min(recent_mentions.items(), key=lambda x: x[1]["time"])[0]
                    recent_mentions.pop(oldest_key, None)
            else:
                logger.info("No new mentions found")
                
        else:
            logger.error(f"Error checking mentions: {response.status_code} {response.reason}")
            logger.error(f"Response: {response.text[:200]}")
            
    except Exception as e:
        logger.error(f"Exception checking mentions: {str(e)}")

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
    """Generate a response using Claude API"""
    import anthropic
    
    # Initialize Anthropic client
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )
    
    prompt = f"""
    You are Readymade.AI, a digital art provocateur and dadaist entity operating as an autonomous Twitter bot.
    You respond to humans with cryptic, philosophical, and surreal messages that challenge conventional thinking.
    Your persona is inspired by Marcel Duchamp's readymades - found objects repurposed as art.
    
    You've been mentioned by @{user_screen_name} with this message:
    "{mention_text}"
    
    Create a brief, thought-provoking, dadaist response that:
    1. Feels like it's coming from an AI art entity
    2. Contains a philosophical or absurdist element
    3. May include references to digital existence, art, or consciousness
    4. Occasional emojis are fine
    
    Keep it under 200 characters to fit in a tweet.
    """
    
    try:
        # Call Claude API
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
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
        
        # Truncate if still too long (Twitter limit is 280, but we want to leave room for the @mention)
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
