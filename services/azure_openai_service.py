import json
import logging
import re
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ServiceResponseTimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzureOpenAIService:
    def __init__(self, api_key, endpoint, model_name="gpt-4o"):
        """
        Initialize the Azure OpenAI service
        
        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            model_name: Model to use for completions (default: "gpt-4o")
        """
        self.api_key = api_key
        self.endpoint = endpoint
        self.model_name = model_name
        self.client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
        )
        logger.info(f"Initialized Azure OpenAI client with model {model_name}")

    def _extract_json(self, content):
        """Helper to extract and clean JSON from response"""
        try:
            # Log the raw content for debugging
            logger.debug(f"Raw content: {content}")
            
            # Clean the content
            content = content.strip()
            
            # Find JSON content between code blocks
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
            else:
                # Try to find content between first { and last }
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1:
                    content = content[start:end + 1]
                else:
                    # If no JSON-like content found, return error
                    return {
                        "error": "No JSON content found in response",
                        "raw_content": content[:200]  # First 200 chars for debugging
                    }

            # Remove any comments
            content = re.sub(r'\s*//.*$', '', content, flags=re.MULTILINE)
            
            # Log the cleaned content
            logger.debug(f"Cleaned content: {content}")
            
            # Parse JSON
            result = json.loads(content)
            
            # Validate result is a dict
            if not isinstance(result, dict):
                return {
                    "error": "Response is not a JSON object",
                    "raw_content": content[:200]
                }
                
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            logger.error(f"Content: {content}")
            return {
                "error": "Failed to parse JSON response",
                "details": str(e),
                "raw_content": content[:200]
            }
        except Exception as e:
            logger.error(f"Error extracting JSON: {str(e)}")
            logger.error(f"Content: {content}")
            return {
                "error": "Failed to process response",
                "details": str(e),
                "raw_content": content[:200]
            }

    def _handle_timeout_error(self):
        """Handle timeout errors with a structured response"""
        logger.error("API request timed out")
        return {
            "error": "API request timed out",
            "details": "The request took too long to complete. Please try again.",
            "status_code": 504
        }

    def get_structured_summary(self, user_id, medical_text):
        """Get comprehensive structured summary of medical record including visualizations and entity analysis"""
        try:
            base_prompt = f"""Here is a medical record. Create a detailed JSON summary with comprehensive analysis:

            Medical Record:
            {medical_text}

            Required JSON Format:
            {{
                "patient_demographics": {{
                    "age": "exact age",
                    "gender": "exact gender",
                    "ethnicity": "if available",
                    "occupation": "if available",
                    "risk_factors": ["list of risk factors"]
                }},
                "vital_signs": {{
                    "measurements": [
                        {{
                            "name": "exact name",
                            "value": "exact value",
                            "unit": "exact unit",
                            "timestamp": "exact time",
                            "trend": "trend analysis if multiple readings",
                            "clinical_significance": "interpretation of the value"
                        }}
                    ],
                    "overall_stability": "Assessment of vital signs stability"
                }},
                "chief_complaints": {{
                    "primary": "main complaint",
                    "secondary": ["other complaints"],
                    "onset": "when symptoms started",
                    "severity": "severity assessment",
                    "progression": "how symptoms have changed"
                }},
                "medical_history": {{
                    "past_conditions": ["list of past medical conditions"],
                    "surgeries": ["list of past surgeries with dates"],
                    "allergies": ["list of allergies and reactions"],
                    "family_history": ["relevant family medical history"],
                    "social_history": {{
                        "lifestyle": ["relevant lifestyle factors"],
                        "habits": ["relevant habits"],
                        "environmental_factors": ["relevant environmental exposures"]
                    }}
                }},
                "symptoms_timeline": [
                    {{
                        "symptom": "exact symptom",
                        "onset": "start date/time",
                        "duration": "duration of symptom",
                        "severity": "severity level",
                        "triggers": ["factors that worsen/improve"],
                        "progression": "how symptom has changed"
                    }}
                ],
                "lab_results": {{
                    "tests": [
                        {{
                            "name": "exact test name",
                            "value": "exact value",
                            "unit": "exact unit",
                            "timestamp": "exact time", 
                            "reference_range": "if available",
                            "trend": "trend analysis if sequential",
                            "clinical_significance": "result interpretation",
                            "action_needed": "required medical actions based on result"
                        }}
                    ],
                    "critical_values": ["Any critical lab values requiring immediate attention"],
                }}
            }}

            Return ONLY valid JSON without explanation. Ensure all fields are properly formatted.
            """

            try:
                response = self.client.complete(
                    messages=[
                        SystemMessage(content="You are a medical AI assistant that extracts structured information from medical records. Your responses should be in valid JSON format only."),
                        UserMessage(content=base_prompt),
                    ],
                    max_tokens=4096,
                    temperature=0.1,
                    model=self.model_name
                )
                
                content = response.choices[0].message.content
                return self._extract_json(content)
                
            except ServiceResponseTimeoutError:
                return self._handle_timeout_error()
                
        except Exception as e:
            logger.error(f"Error in get_structured_summary: {str(e)}")
            return {
                "error": "Failed to generate summary",
                "details": str(e)
            }

    def chat_with_doctor(self, user_id, medical_text, question):
        """Chat with the AI doctor about a specific medical record"""
        try:
            prompt = f"""
            Medical Record:
            {medical_text}
            
            Question from doctor: {question}
            
            Please provide a thorough, evidence-based response relevant to the medical record and question. 
            Include specific information from the record where appropriate. If you're unsure about something, 
            indicate the limitations clearly instead of making assumptions.
            """
            
            try:
                response = self.client.complete(
                    messages=[
                        SystemMessage(content="You are an AI medical assistant helping a doctor interpret medical records. Provide detailed, accurate information based on the medical record provided."),
                        UserMessage(content=prompt),
                    ],
                    max_tokens=4096,
                    temperature=0.7,
                    model=self.model_name
                )
                
                return response.choices[0].message.content
                
            except ServiceResponseTimeoutError:
                return "The request timed out. This could be due to the length of the medical record or complexity of the question. Please try again with a more specific question."
                
        except Exception as e:
            logger.error(f"Error in chat_with_doctor: {str(e)}")
            return f"An error occurred: {str(e)}" 