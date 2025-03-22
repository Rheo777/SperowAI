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
                    "test_trends": [
                        {{
                            "test_name": "name of test",
                            "values_over_time": [
                                {{
                                    "value": "exact value",
                                    "timestamp": "exact time",
                                    "trend_direction": "increasing/decreasing/stable",
                                    "clinical_impact": "significance of trend"
                                }}
                            ]
                        }}
                    ]
                }},
                "diagnosis": {{
                    "primary": {{
                        "condition": "primary diagnosis",
                        "certainty": "diagnostic certainty",
                        "basis": ["clinical findings supporting diagnosis"],
                        "stage": "stage or severity if applicable"
                    }},
                    "secondary": [
                        {{
                            "condition": "secondary diagnosis",
                            "relationship": "relationship to primary diagnosis",
                            "impact": "impact on treatment plan"
                        }}
                    ],
                    "differential_diagnoses": ["potential alternative diagnoses to consider"],
                    "ruled_out": ["diagnoses that were considered and ruled out"]
                }},
                "medications": {{
                    "current": [
                        {{
                            "name": "medication name",
                            "dosage": "exact dosage",
                            "frequency": "administration frequency",
                            "route": "administration route",
                            "purpose": "therapeutic purpose",
                            "start_date": "when started",
                            "duration": "planned duration",
                            "side_effects": ["observed side effects"],
                            "interactions": ["potential drug interactions"],
                            "monitoring_needs": ["parameters to monitor"]
                        }}
                    ],
                    "discontinued": [
                        {{
                            "name": "medication name",
                            "reason": "reason for discontinuation",
                            "date_stopped": "when stopped"
                        }}
                    ],
                    "allergies": ["medication allergies and reactions"]
                }},
                "treatment_plan": {{
                    "immediate_actions": ["urgent medical steps"],
                    "short_term_goals": ["treatment objectives for next 24-48 hours"],
                    "long_term_goals": ["treatment objectives for discharge"],
                    "interventions": [
                        {{
                            "type": "intervention type",
                            "details": "specific details",
                            "frequency": "how often",
                            "duration": "how long",
                            "expected_outcome": "anticipated results"
                        }}
                    ],
                    "monitoring_requirements": ["specific parameters to track"],
                    "lifestyle_modifications": ["recommended lifestyle changes"]
                }},
                "follow_up_plan": {{
                    "appointments": [
                        {{
                            "specialist": "type of provider",
                            "timeframe": "when to follow up",
                            "purpose": "reason for follow up",
                            "preparation": ["any required preparation"]
                        }}
                    ],
                    "monitoring": ["parameters to monitor at home"],
                    "warning_signs": ["symptoms requiring immediate attention"],
                    "care_coordination": ["coordination between providers"]
                }},
                "medical_entities": {{
                    "conditions": [
                        {{
                            "name": "exact condition name",
                            "status": "current status",
                            "severity": "severity level",
                            "first_noted": "onset date",
                            "risk_factors": [
                                {{
                                    "factor": "specific risk factor",
                                    "impact_percentage": "quantified risk impact",
                                    "evidence": "clinical evidence",
                                    "mitigation_strategy": "risk reduction approach"
                                }}
                            ],
                            "correlations": [
                                {{
                                    "related_finding": "correlated condition/finding",
                                    "correlation_strength": "statistical correlation",
                                    "clinical_significance": "medical importance",
                                    "evidence_base": "research/clinical evidence supporting correlation"
                                }}
                            ],
                            "future_risks": [
                                {{
                                    "potential_condition": "possible future condition",
                                    "risk_percentage": "probability estimation",
                                    "time_frame": "expected time of manifestation",
                                    "preventive_measures": ["specific preventive actions"],
                                    "supporting_evidence": "clinical basis for prediction",
                                    "monitoring_plan": "recommended follow-up plan"
                                }}
                            ],
                            "treatment_implications": {{
                                "recommended_interventions": ["specific treatments"],
                                "contraindications": ["treatments to avoid"],
                                "expected_outcomes": ["projected treatment results"]
                            }}
                        }}
                    ],
                    "vital_signs": [
                        {{
                            "name": "measurement name",
                            "value": "exact value",
                            "unit": "measurement unit",
                            "timestamp": "exact time",
                            "status": "current status",
                            "clinical_impact": "medical significance",
                            "trend_analysis": {{
                                "pattern": "trend pattern",
                                "significance": "clinical importance",
                                "recommendations": ["clinical actions based on trend"]
                            }}
                        }}
                    ],
                    "procedures": [
                        {{
                            "name": "procedure name",
                            "type": "procedure type",
                            "date": "procedure date",
                            "outcome": "procedure outcome",
                            "complications": ["any complications"],
                            "follow_up_needed": "follow-up requirements"
                        }}
                    ],
                    "medications": [
                        {{
                            "name": "medication name",
                            "class": "medication class",
                            "indications": ["medical conditions"],
                            "contraindications": ["conditions where medication should not be used"],
                            "interactions": ["known drug interactions"],
                            "monitoring_parameters": ["what to monitor"]
                        }}
                    ]
                }},
                "visualizations": [
                    {{
                        "title": "visualization title",
                        "type": "chart type",
                        "data": {{
                            "x_axis": {{
                                "label": "time unit",
                                "values": ["timestamps"]
                            }},
                            "y_axis": {{
                                "label": "measurement with unit",
                                "values": ["exact values"],
                                "reference_ranges": ["normal ranges"]
                            }}
                        }},
                        "source": "data source",
                        "clinical_significance": "medical importance",
                        "annotations": ["important points to note"],
                        "recommendations": ["clinical decisions based on visualization"]
                    }}
                ]
            }}

            Rules:
            1. ONLY include information explicitly stated in the record
            2. Use exact values and dates from the record
            3. For any missing fields, use "Not Available"
            4. Do not generate or assume any information
            5. For risk percentages and correlations, only use explicitly stated numerical values
            6. Include all relevant timestamps exactly as they appear
            7. Provide detailed clinical interpretations where data supports it
            8. Highlight critical values and urgent concerns
            9. Return ONLY valid JSON, no additional text
            10. IMPORTANT: Include ALL test results with their exact timestamps - do not skip any results
            11. For each type of test (e.g., blood tests), create a separate visualization showing trends over time
            12. If multiple results exist for the same test on different dates, include ALL of them
            13. Generate visualizations for ALL numeric measurements that have multiple values over time

            Format your response like this:
            ```json
            {{
                "your": "json here"
            }}
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