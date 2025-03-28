import os
import tweepy
import logging
import time
import datetime
from .rate_limit_manager import TwitterRateLimitManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twitter_connection")

# Load Twitter API credentials
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Keep track of rate limit state
rate_limit_state = {
    "reset_time": None,
    "remaining": None,
    "last_checked": None
}

# Initialize Twitter v2 API Client
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

def should_respect_rate_limit():
    """Check if we should wait for rate limit reset"""
    if rate_limit_state["reset_time"] is None:
        return False
        
    now = datetime.datetime.now().timestamp()
    
    # If current time is before reset time, we should wait
    if now < rate_limit_state["reset_time"]:
        # Only if we have no requests remaining
        if rate_limit_state["remaining"] is not None and rate_limit_state["remaining"] <= 1:
            wait_seconds = int(rate_limit_state["reset_time"] - now) + 5  # Add 5 second buffer
            logger.warning(f"Rate limit active. Waiting {wait_seconds} seconds until reset time.")
            return True
            
    return False

def send_tweet(message, media_bytes=None):
    """
    Sends a tweet using Twitter API v2 with detailed error handling and rate limit respect
    """
    # First check if we need to respect rate limits
    if should_respect_rate_limit():
        now = datetime.datetime.now().timestamp()
        wait_seconds = int(rate_limit_state["reset_time"] - now) + 5  # Add buffer
        logger.info(f"⏳ Waiting for rate limit reset: {wait_seconds} seconds")
        time.sleep(wait_seconds)
    
    try:
        logger.info(f"Attempting to send tweet: {message[:30]}...")
        
        # Handle media upload if provided
        media_ids = []
        if media_bytes:
            try:
                # For media upload we need v1.1 API
                auth = tweepy.OAuth1UserHandler(
                    CONSUMER_KEY, CONSUMER_SECRET, 
                    ACCESS_TOKEN, ACCESS_TOKEN_SECRET
                )
                api = tweepy.API(auth)
                
                # Upload the media
                logger.info("Uploading media to Twitter...")
                media_bytes.seek(0)  # Ensure we're at the start of the BytesIO object
                
                upload_result = api.media_upload(
                    filename="readymade_image.png",
                    file=media_bytes
                )
                
                media_ids.append(str(upload_result.media_id))
                logger.info(f"Media uploaded successfully. Media ID: {upload_result.media_id}")
            except Exception as e:
                logger.error(f"Error uploading media: {e}")
                # Continue with text-only tweet if media upload fails
        
        # Post the tweet (with or without media)
        if media_ids:
            response = client.create_tweet(text=message, media_ids=media_ids)
            logger.info("Tweet posted with media attachment")
        else:
            response = client.create_tweet(text=message)
            
        tweet_id = response.data['id']
        tweet_url = f"https://twitter.com/user/status/{tweet_id}"
        logger.info(f"✅ Tweet sent successfully! Tweet ID: {tweet_id}")
        logger.info(f"✅ Tweet URL: {tweet_url}")
        
        # Reset rate limit warning since we succeeded
        rate_limit_state["remaining"] = None
        
        return tweet_id
    except tweepy.TweepyException as e:
        logger.error(f"❌ Error sending tweet: {e}")
        
        # Check if it's a rate limit error
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 429:  # 429 is the status code for rate limiting
                reset_time = e.response.headers.get('x-rate-limit-reset')
                if reset_time:
                    # Convert to timestamp and store for future reference
                    rate_limit_state["reset_time"] = int(reset_time)
                    rate_limit_state["remaining"] = 0
                    rate_limit_state["last_checked"] = datetime.datetime.now().timestamp()
                    
                    # Calculate wait time in human-readable format
                    reset_dt = datetime.datetime.fromtimestamp(int(reset_time))
                    wait_seconds = int(reset_dt.timestamp() - datetime.datetime.now().timestamp())
                    wait_minutes = wait_seconds // 60
                    wait_seconds_remainder = wait_seconds % 60
                    
                    logger.error(f"Rate limit exceeded! Reset time: {reset_time} "
                                 f"({wait_minutes}m {wait_seconds_remainder}s from now "
                                 f"at {reset_dt.strftime('%H:%M:%S')})")
                else:
                    logger.error("Rate limit exceeded but no reset time provided")
            else:
                logger.error(f"HTTP Status Code: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
        return None

def check_rate_limits():
    """
    Checks the current Twitter API rate limits for the account
    
    Returns:
        bool: True if we can post, False if we should wait
    """
    try:
        # If we've checked recently and know we're rate limited, don't check again
        if should_respect_rate_limit():
            return False
            
        # Get application rate limit status using v1.1 API
        auth = tweepy.OAuth1UserHandler(
            CONSUMER_KEY, CONSUMER_SECRET, 
            ACCESS_TOKEN, ACCESS_TOKEN_SECRET
        )
        api = tweepy.API(auth)
        
        # Focus on POST statuses/update limits
        limits = api.rate_limit_status()
        
        # Log overall rate limit status
        logger.info("Twitter API Rate Limits:")
        
        # Check status endpoint limits if available
        can_post = True
        if 'statuses' in limits.get('resources', {}):
            statuses_limits = limits['resources']['statuses']
            if '/statuses/update' in statuses_limits:
                update_limit = statuses_limits['/statuses/update']
                remaining = update_limit['remaining']
                limit = update_limit['limit']
                reset_time = update_limit['reset']
                
                # Store for future reference
                rate_limit_state["reset_time"] = reset_time
                rate_limit_state["remaining"] = remaining
                rate_limit_state["last_checked"] = datetime.datetime.now().timestamp()
                
                reset_dt = datetime.datetime.fromtimestamp(reset_time)
                logger.info(f"POST statuses/update: {remaining}/{limit} requests remaining")
                logger.info(f"Reset time: {reset_time} ({reset_dt.strftime('%H:%M:%S')})")
                
                # If we're out of requests, we need to wait
                if remaining <= 0:
                    wait_seconds = int(reset_time - datetime.datetime.now().timestamp()) + 5  # Add buffer
                    logger.warning(f"No posting capacity remaining. Need to wait {wait_seconds} seconds until reset.")
                    can_post = False
        
        # Also check v2 tweet limits if available
        if 'tweets' in limits.get('resources', {}):
            tweets_limits = limits['resources']['tweets']
            logger.info(f"Tweets endpoint limits: {tweets_limits}")
        
        return can_post
    except tweepy.TweepyException as e:
        logger.error(f"Error checking rate limits: {e}")
        # On error, be conservative and assume we can still post
        # Twitter API will reject if we're rate limited
        return True

def verify_credentials():
    """
    Verifies the Twitter credentials are working properly
    """
    try:
        # Use v1.1 API to verify credentials
        auth = tweepy.OAuth1UserHandler(
            CONSUMER_KEY, CONSUMER_SECRET, 
            ACCESS_TOKEN, ACCESS_TOKEN_SECRET
        )
        api = tweepy.API(auth)
        user = api.verify_credentials()
        logger.info(f"✅ Twitter credentials verified successfully!")
        logger.info(f"Account: @{user.screen_name}")
        logger.info(f"User ID: {user.id}")
        return True
    except tweepy.TweepyException as e:
        logger.error(f"❌ Twitter credentials verification failed: {e}")
        return False

# Test credentials when the module is imported
logger.info("Initializing Twitter connection...")
verify_credentials()
check_rate_limits()