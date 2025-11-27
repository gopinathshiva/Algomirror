"""
Extended OpenAlgo API client with additional methods
"""
from openalgo import api


class ExtendedOpenAlgoAPI(api):
    """Extended OpenAlgo API client with ping method and optimized timeout"""

    def __init__(self, api_key, host="http://127.0.0.1:5000", version="v1", ws_port=8765, ws_url=None, timeout=10):
        """
        Initialize with a shorter timeout (10 seconds default instead of 120)
        to prevent app from becoming unresponsive when OpenAlgo is slow.
        """
        super().__init__(api_key, host, version, ws_port, ws_url)
        # Override the default 120s timeout with a much shorter one
        self.timeout = timeout

    def ping(self):
        """
        Test connectivity and validate API key authentication
        
        This endpoint checks connectivity and validates the API key 
        authentication with the OpenAlgo platform.
        
        Returns:
            dict: Response with status, broker info, and message
            
        Example Response:
            {
                "data": {
                    "broker": "upstox",
                    "message": "pong"
                },
                "status": "success"
            }
        """
        payload = {"apikey": self.api_key}
        return self._make_request("ping", payload)