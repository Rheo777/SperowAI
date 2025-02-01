import os
import logging
from datetime import datetime
from exa_py import Exa

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        try:
            # Configure the Exa API
            self.exa = Exa(api_key=os.getenv("EXA_API_KEY"))
            
            self.is_initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {str(e)}")
            self.is_initialized = False

    def search(self, query: str) -> dict:
        """
        Perform a search using Exa API
        
        Args:
            query (str): The search query
            
        Returns:
            dict: Response containing search results
        """
        if not self.is_initialized:
            return {
                "success": False,
                "error": "Gemini service not properly initialized",
                "results": None,
                "status_code": 500
            }
            
        try:
            # Log the query being sent
            
            
            # Use Exa to perform the search
            result = self.exa.search(query)
            
           
            
            return {
                "success": True,
                "error": None,
                "results": {
                    "content": result,
                    "type": "exa_search",
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                },
                "status_code": 200
            }
            
        except Exception as e:
            logger.error(f"Error in Exa search: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": None,
                "status_code": 500
            }

    def structured_search(self, query: str) -> dict:
        """
        Perform a structured search using Exa API
        
        Args:
            query (str): The search query
            
        Returns:
            dict: Response containing structured search results
        """
        return self.search(query) # Call the search function directly
