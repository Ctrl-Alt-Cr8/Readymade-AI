import os
import tweepy

# Load Twitter API credentials
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Initialize Twitter v2 API Client
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

def send_tweet(message):
    """
    Sends a tweet using Twitter API v2
    """
    try:
        response = client.create_tweet(text=message)
        print(f"✅ Tweet sent successfully! Tweet ID: {response.data['id']}")
        return response.data['id']
    except tweepy.TweepyException as e:
        print(f"❌ Error sending tweet: {e}")
        return None
