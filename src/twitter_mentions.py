import os
import json
import logging
import time
import requests
from flask import request, jsonify
import anthropic

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twitter_mentions")

# Initialize Anthropic client
client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

# Recent mentions tracker to avoid duplicate responses
# In a production environment, you might want to use Redis or a database
recent_mentions = {}
MAX_RECENT_MENTIONS = 100  # Max size of our memory cache

def setup_twitter_webhook(app):
    """Register routes for Twitter webhook handling"""
    
    @app.route('/webhook/twitter', methods=['GET'])
    def twitter_webhook_challenge():
        """
        Handle the CRC (Challenge Response Check) from Twitter.
        This is required when registering a webhook URL.
        """
        crc_token = request.args.get('crc_token')
        if not crc_token:
            return jsonify({"error": "No CRC token provided"}), 400
            
        import hmac
        import hashlib
        import base64
        
        # Get the consumer secret from environment variables
        consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
        
        # Create HMAC SHA-256 hash with consumer secret as key and CRC token as message
        sha256_hash_digest = hmac.new(
            key=consumer_secret.encode('utf-8'),
            msg=crc_token.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        # Base64 encode the hash
        response_token = base64.b64encode(sha256_hash_digest).decode('utf-8')
        
        # Return the response token in the required format
        return jsonify({"response_token": f"sha256={response_token}"})
    
    @app.route('/webhook/twitter', methods=['POST'])
    def twitter_webhook_event():
        """Handle Twitter webhook events"""
        # Verify the request is from Twitter (in production, add signature verification)
        
        # Parse the incoming webhook data
        event_data = request.json
        logger.info(f"Received Twitter webhook event: {json.dumps(event_data)[:200]}...")
        
        # Check if this is a tweet_create_events
        if 'tweet_create_events' in event_data:
            for tweet in event_data['tweet_create_events']:
                # Only process mentions of our bot that aren't from our bot
                if (('@Readymade_AI' in tweet.get('text', '')) and 
                    (tweet.get('user', {}).get('screen_name') != 'Readymade_AI')):
                    # Process in background to avoid webhook timeout
                    # In production, use a task queue like Cloud Tasks or Pub/Sub
                    # For simplicity, we'll process inline
                    try:
                        process_mention(tweet)
                    except Exception as e:
                        logger.error(f"Error processing mention: {str(e)}")
        
        # Always return success to Twitter
        return jsonify({"success": True})
    
    logger.info("Twitter webhook routes registered")

def process_mention(tweet):
    """Process a Twitter mention and generate a response"""
    tweet_id = tweet.get('id_str')
    user_screen_name = tweet.get('user', {}).get('screen_name')
    mention_text = tweet.get('text', '')
    
    logger.info(f"Processing mention from @{user_screen_name}: {mention_text}")
    
    # Check if we should respond to this mention
    if not should_respond(tweet):
        logger.info(f"Skipping response to @{user_screen_name}")
        return
    
    # Clean the mention text by removing the @Readymade_AI
    clean_text = mention_text.replace('@Readymade_AI', '').strip()
    
    # Generate response using Claude
    response_text = generate_response(clean_text, user_screen_name)
    
    # Send the response as a reply
    success = send_reply(response_text, tweet_id, user_screen_name)
    
    if success:
        logger.info(f"Sent reply to @{user_screen_name}: {response_text}")
        # Add to recent mentions
        recent_mentions[tweet_id] = {
            "user": user_screen_name,
            "time": time.time()
        }
        # Trim the recent mentions if it's too large
        if len(recent_mentions) > MAX_RECENT_MENTIONS:
            oldest_key = min(recent_mentions.items(), key=lambda x: x[1]["time"])[0]
            recent_mentions.pop(oldest_key, None)
    else:
        logger.error(f"Failed to send reply to @{user_screen_name}")

def should_respond(tweet):
    """Determine if the bot should respond to this mention"""
    tweet_id = tweet.get('id_str')
    user_screen_name = tweet.get('user', {}).get('screen_name')
    
    # Don't respond to our own tweets
    if user_screen_name == 'Readymade_AI':
        return False
    
    # Don't respond to tweets we've already responded to
    if tweet_id in recent_mentions:
        return False
    
    # Don't respond to retweets
    if tweet.get('retweeted_status') is not None:
        return False
    
    # Don't respond if the tweet is a reply to someone else
    in_reply_to_screen_name = tweet.get('in_reply_to_screen_name')
    if in_reply_to_screen_name is not None and in_reply_to_screen_name != 'Readymade_AI':
        return False
    
    # Basic spam filtering - avoid users who've tweeted at us too frequently
    user_mentions = sum(1 for _, v in recent_mentions.items() if v["user"] == user_screen_name)
    if user_mentions >= 5:  # Limit to 5 responses per user in our cache window
        return False
    
    return True

def generate_response(mention_text, user_screen_name):
    """Generate a response using Claude API"""
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
            logger.info(f"Reply tweet sent successfully! ID: {response_data.get('data', {}).get('id')}")
            return True
        else:
            logger.error(f"Failed to send reply tweet: {response.status_code} {response.reason}")
            logger.error(f"Response body: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Exception during reply tweet sending: {str(e)}")
        return False

# Webhook registration helper function
def register_twitter_webhook(webhook_url):
    """
    Register a webhook URL with Twitter.
    This needs to be run just once to set up the webhook.
    """
    try:
        # Twitter API endpoint for webhook registration
        environment_name = "production"  # or use a dev environment name for testing
        url = f"https://api.twitter.com/1.1/account_activity/all/{environment_name}/webhooks.json"
        
        # Set up OAuth1 authentication
        from requests_oauthlib import OAuth1
        auth = OAuth1(
            os.environ.get("TWITTER_CONSUMER_KEY"),
            os.environ.get("TWITTER_CONSUMER_SECRET"),
            os.environ.get("TWITTER_ACCESS_TOKEN"),
            os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        # Make the request
        params = {"url": webhook_url}
        response = requests.post(url, auth=auth, params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            webhook_id = response.json().get("id")
            logger.info(f"Webhook registered successfully! ID: {webhook_id}")
            return webhook_id
        else:
            logger.error(f"Failed to register webhook: {response.status_code} {response.reason}")
            logger.error(f"Response body: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Exception during webhook registration: {str(e)}")
        return None

# Webhook subscription helper function
def subscribe_to_user_activity():
    """
    Subscribe to user activity after registering a webhook.
    This activates the webhook to receive events.
    """
    try:
        # Twitter API endpoint for webhook subscription
        environment_name = "production"  # or use a dev environment name for testing
        url = f"https://api.twitter.com/1.1/account_activity/all/{environment_name}/subscriptions.json"
        
        # Set up OAuth1 authentication
        from requests_oauthlib import OAuth1
        auth = OAuth1(
            os.environ.get("TWITTER_CONSUMER_KEY"),
            os.environ.get("TWITTER_CONSUMER_SECRET"),
            os.environ.get("TWITTER_ACCESS_TOKEN"),
            os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        # Make the request
        response = requests.post(url, auth=auth)
        
        # Check if the request was successful
        if response.status_code == 204:  # 204 No Content is the success response
            logger.info("Successfully subscribed to user activity!")
            return True
        else:
            logger.error(f"Failed to subscribe: {response.status_code} {response.reason}")
            logger.error(f"Response body: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Exception during subscription: {str(e)}")
        return False
