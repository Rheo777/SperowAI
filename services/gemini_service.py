import os
import logging
from datetime import datetime
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from config.config import Config
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        try:
            # Force reload environment variables
            load_dotenv(override=True)
            
            # Configure the Gemini API
            api_key = os.getenv('GOOGLE_API_KEY')  # Get the key directly from environment
            genai.configure(api_key=api_key)
            
            # Initialize the model
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.is_initialized = True
            
            # Store API key for search
            self.api_key = api_key
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {str(e)}")
            self.is_initialized = False
    
    def _fetch_webpage_content(self, url):
        """Fetch and extract text content from a webpage"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
                
            # Get text content
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up text (remove extra newlines, etc.)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = '\n'.join(lines)
            
            return text[:1000]  # Return first 1000 characters to avoid token limits
            
        except Exception as e:
            logger.error(f"Error fetching webpage content: {str(e)}")
            return None

    def search(self, query: str) -> dict:
        """
        Perform a search using Gemini API with web search capabilities
        
        Args:
            query (str): The search query
            
        Returns:
            dict: Response containing search results and AI-generated answer
        """
        if not self.is_initialized:
            return {
                "success": False,
                "error": "Gemini service not properly initialized",
                "results": None,
                "status_code": 500
            }
            
        try:
            # First, perform a web search using Google's Custom Search API
            search_url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.api_key,  # Use the stored API key
                'cx': os.getenv('GOOGLE_SEARCH_ENGINE_ID'),  # Get directly from environment
                'q': query,
                'num': 5  # Number of results to return
            }
            
            search_response = requests.get(search_url, params=params)
            search_response.raise_for_status()
            search_data = search_response.json()
            
            # Extract search results
            search_results = []
            web_contents = []
            
            if 'items' in search_data:
                for item in search_data['items']:
                    result = {
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    }
                    search_results.append(result)
                    
                    # Fetch webpage content for context
                    content = self._fetch_webpage_content(item['link'])
                    if content:
                        web_contents.append(content)
            
            # Prepare context for Gemini
            context = "\n\n".join([
                f"Source {i+1}:\n{content}" 
                for i, content in enumerate(web_contents)
            ])
            
            # Prepare prompt for Gemini
            prompt = f"""Based on the following web search results, provide a comprehensive answer to the query: "{query}"

Web Search Results:
{context}

Please provide:
1. A direct answer to the query
2. Key points from the sources
3. Any relevant additional information

Format the response in a clear, organized way."""

            # Get response from Gemini
            response = self.model.generate_content(prompt)
            
            return {
                "success": True,
                "error": None,
                "results": {
                    "search_results": search_results,
                    "ai_response": response.text,
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                },
                "status_code": 200
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini search: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": None,
                "status_code": 500
            }

    def structured_search(self, query: str) -> dict:
        """
        Perform a structured search using Gemini API
        
        Args:
            query (str): The search query
            
        Returns:
            dict: Response containing structured search results
        """
        return self.search(query)  # Call the search function directly

