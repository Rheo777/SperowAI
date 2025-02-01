import os
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from config.config import Config
import logging

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.generation_config = {
                "temperature": 1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }
            
            self.model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                generation_config=self.generation_config,
                tools=[
                    genai.protos.Tool(
                        google_search=genai.protos.Tool.GoogleSearch(),
                    ),
                ],
            )
            self.is_initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {str(e)}")
            self.is_initialized = False

    def search(self, query: str) -> dict:
        """
        Perform a search using Gemini API
        
        Args:
            query (str): The search query
            
        Returns:
            dict: Response containing search results and status
        """
        if not self.is_initialized:
            return {
                "success": False,
                "error": "Gemini service not properly initialized",
                "results": None
            }
            
        try:
            # Create a new chat session for each search
            chat_session = self.model.start_chat(history=[])
            
            # Send the search query
            response = chat_session.send_message(query)
            
            return {
                "success": True,
                "error": None,
                "results": response.text
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini search: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": None
            }

    def structured_search(self, query: str, context: str = None) -> dict:
        """
        Perform a structured search with optional context
        
        Args:
            query (str): The search query
            context (str, optional): Additional context for the search
            
        Returns:
            dict: Structured response containing search results
        """
        if not self.is_initialized:
            return {
                "success": False,
                "error": "Gemini service not properly initialized",
                "results": None
            }
            
        try:
            chat_session = self.model.start_chat(history=[])
            
            # Construct prompt with context if provided
            prompt = query
            if context:
                prompt = f"Context: {context}\nQuery: {query}"
            
            response = chat_session.send_message(prompt)
            
            return {
                "success": True,
                "error": None,
                "results": response.text
            }
            
        except Exception as e:
            logger.error(f"Error in structured Gemini search: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": None
            }
