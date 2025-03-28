import time
import logging
from typing import Dict, Any, Optional
from threading import Lock

class TwitterRateLimitManager:
    """
    Advanced rate limit management for Twitter API endpoints
    Provides thread-safe tracking and smart throttling of API requests
    """
    
    def __init__(self, logger=None):
        """
        Initialize the rate limit manager
        
        :param logger: Optional logger, defaults to creating a new logger
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Thread-safe dictionary to track endpoint rate limits
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        
        # Global safety margins
        self.GLOBAL_SAFETY_MARGIN = 0.9  # Use 90% of available limit
        self.MINIMUM_REMAINING_REQUESTS = 2  # Always keep at least 2 requests in reserve
    
    def update_rate_limits(self, endpoint: str, limit_info: Dict[str, Any]):
        """
        Update rate limit information for a specific endpoint
        
        :param endpoint: The API endpoint 
        :param limit_info: Dictionary containing rate limit details
        """
        with self._lock:
            current_time = time.time()
            self._rate_limits[endpoint] = {
                'limit': limit_info.get('limit', 0),
                'remaining': limit_info.get('remaining', 0),
                'reset_time': limit_info.get('reset', current_time + 900),  # Default 15-minute reset
                'last_updated': current_time
            }
            
            self.logger.info(f"Updated rate limits for {endpoint}: "
                              f"{self._rate_limits[endpoint]['remaining']}/{self._rate_limits[endpoint]['limit']} "
                              f"resets at {time.ctime(self._rate_limits[endpoint]['reset_time'])}")
    
    def can_make_request(self, endpoint: str) -> bool:
        """
        Determine if a request can be made to a specific endpoint
        
        :param endpoint: The API endpoint to check
        :return: Boolean indicating if a request can be made
        """
        current_time = time.time()
        
        with self._lock:
            # If endpoint is not tracked, assume it can be used
            if endpoint not in self._rate_limits:
                return True
            
            endpoint_limits = self._rate_limits[endpoint]
            
            # Check if reset time has passed
            if current_time >= endpoint_limits['reset_time']:
                return True
            
            # Apply safety margins
            safe_remaining = max(
                endpoint_limits['remaining'] * self.GLOBAL_SAFETY_MARGIN, 
                self.MINIMUM_REMAINING_REQUESTS
            )
            
            can_request = safe_remaining > 0
            
            if not can_request:
                wait_time = endpoint_limits['reset_time'] - current_time
                self.logger.warning(
                    f"Rate limit reached for {endpoint}. "
                    f"Waiting {wait_time:.2f} seconds until reset."
                )
            
            return can_request
    
    def consume_request(self, endpoint: str):
        """
        Mark a request as consumed for a specific endpoint
        
        :param endpoint: The API endpoint 
        """
        with self._lock:
            if endpoint in self._rate_limits:
                self._rate_limits[endpoint]['remaining'] = max(
                    0, 
                    self._rate_limits[endpoint]['remaining'] - 1
                )
    
    def get_wait_time(self, endpoint: str) -> float:
        """
        Calculate recommended wait time before next request
        
        :param endpoint: The API endpoint
        :return: Recommended wait time in seconds
        """
        current_time = time.time()
        
        with self._lock:
            if endpoint not in self._rate_limits:
                return 0
            
            endpoint_limits = self._rate_limits[endpoint]
            
            # If reset time has passed, no wait needed
            if current_time >= endpoint_limits['reset_time']:
                return 0
            
            # Calculate wait time
            wait_time = max(
                0, 
                endpoint_limits['reset_time'] - current_time
            )
            
            return wait_time
    
    def emergency_reset(self, endpoint: str):
        """
        Force a reset of rate limits for an endpoint in case of persistent issues
        
        :param endpoint: The API endpoint to reset
        """
        with self._lock:
            if endpoint in self._rate_limits:
                self.logger.warning(f"Emergency reset of rate limits for {endpoint}")
                del self._rate_limits[endpoint]
