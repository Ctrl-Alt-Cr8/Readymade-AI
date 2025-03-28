import os
import requests
from requests_oauthlib import OAuth1

# Set your credentials
consumer_key = "uXJNb9GtTkIsJRwcmhcvgfUUO" 
consumer_secret = "T9h4LJiKPn9kcqUI18tG41S6IN7ExaDn3BrOW7KdZc8p6ff9Qp"
access_token = "1799521539206819840-BswqY7alrf58eyiI5I0bIzNLwCvIZo"
access_token_secret = "5leJQUckaYnp88u1a984hFs0BzhErJlD3Cr5yXmX5LZ6D"
bearer_token = "AAAAAAAAAAAAAAAAAAAAAEoRzwEAAAAAy%2BEAELSW2iwCjMq0igufF5wXYRU%3DcajPh72Xa3RaYtafxR57gFZI1VpRu9wEaVvdfMGMRil1pUi8O3"

print("Testing Twitter API credentials...")

# Test OAuth 1.0a (for v1.1 API endpoints)
auth = OAuth1(
    consumer_key, 
    consumer_secret,
    access_token, 
    access_token_secret
)

# Test bearer token (for v2 API endpoints)
headers = {
    "Authorization": f"Bearer {bearer_token}"
}

# Test user info endpoint (v2)
try:
    user_response = requests.get(
        "https://api.twitter.com/2/users/me", 
        headers=headers
    )
    print(f"User info status: {user_response.status_code}")
    print(f"Response: {user_response.text}")
except Exception as e:
    print(f"Error testing user info: {e}")

# Test posting tweet endpoint (v2)
try:
    tweet_url = "https://api.twitter.com/2/tweets"
    tweet_data = {"text": "This is a test tweet from credential verification script"}
    
    tweet_response = requests.post(
        tweet_url,
        auth=auth,
        headers={"Content-Type": "application/json"},
        json=tweet_data
    )
    print(f"Tweet post status: {tweet_response.status_code}")
    print(f"Response: {tweet_response.text}")
except Exception as e:
    print(f"Error testing tweet post: {e}")
