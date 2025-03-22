from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.textract_service import TextractService
from services.openai_service import OpenAIService
from services.azure_openai_service import AzureOpenAIService
from services.redis_service import RedisService
from config.config import Config
from models.user import User
import logging
from datetime import datetime
import pytz

medical_bp = Blueprint('medical', __name__)

# Initialize services
textract_service = TextractService(
    aws_access_key=Config.AWS_ACCESS_KEY,
    aws_secret_key=Config.AWS_SECRET_KEY,
    region=Config.AWS_REGION
)

# Initialize the appropriate LLM service based on configuration
if Config.LLM_PROVIDER == 'azure_openai':
    logger = logging.getLogger(__name__)
    logger.info("Using Azure OpenAI service")
    llm_service = AzureOpenAIService(
        api_key=Config.AZURE_OPENAI_API_KEY,
        endpoint=Config.AZURE_OPENAI_ENDPOINT,
        model_name=Config.AZURE_OPENAI_MODEL
    )
else:
    # Default to OpenAI
    logger = logging.getLogger(__name__)
    logger.info("Using OpenAI service")
    llm_service = OpenAIService(Config.OPENAI_API_KEY)

redis_service = RedisService()

@medical_bp.route('/process-medical-record', methods=['POST'])
@jwt_required()
def process_medical_record():
    username = get_jwt_identity()
    
    # Check for active consultation
    active_consultation = User.get_active_consultation(username)
    if active_consultation:
        return jsonify({
            'error': 'You have an active consultation. Please close it before starting a new one.'
        }), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    try:
        # For development/testing, use cached text if available
        if Config.ENVIRONMENT == 'development':
            cached_text = redis_service.get_cached_text(file.filename)
            if cached_text:
                extracted_text = cached_text
            else:
                file_bytes = file.read()
                extracted_text = textract_service.extract_text(file_bytes, file.filename)
                # Cache the extracted text
                redis_service.set_cached_text(file.filename, extracted_text)
        else:
            # Production environment - always use Textract
            file_bytes = file.read()
            extracted_text = textract_service.extract_text(file_bytes, file.filename)
        
        if not extracted_text:
            return jsonify({'error': 'Failed to extract text from document'}), 400
            
        # Get structured summary from the selected LLM service
        structured_summary = llm_service.get_structured_summary(username, extracted_text)
        
        # Store both raw text and structured summary in Redis
        if not redis_service.set_medical_record(username, extracted_text):
            return jsonify({'error': 'Failed to store medical record'}), 500
            
        if not redis_service.set_structured_summary(username, structured_summary):
            return jsonify({'error': 'Failed to store structured summary'}), 500

        # Start consultation timer
        consultation_id = User.start_consultation(username, file.filename)
        if not consultation_id:
            return jsonify({'error': 'Failed to start consultation'}), 500

        # Get current metrics
        metrics = User.get_consultation_metrics(username)
        
        return jsonify({
            'summary': structured_summary,
            'consultation_id': consultation_id,
            'metrics': metrics
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing medical record: {str(e)}")
        return jsonify({'error': str(e)}), 500

@medical_bp.route('/close-consultation/<consultation_id>', methods=['POST'])
@jwt_required()
def close_consultation(consultation_id):
    """Close a consultation and get updated metrics"""
    username = get_jwt_identity()
    
    try:
        # End consultation and get duration
        duration = User.end_consultation(consultation_id, username)
        if duration is None:
            return jsonify({'error': 'Consultation not found or already closed'}), 404
        
        # Get updated metrics
        metrics = User.get_consultation_metrics(username)
        
        return jsonify({
            'message': 'Consultation closed successfully',
            'duration_minutes': round(duration / 60, 2),
            'metrics': metrics
        }), 200
        
    except Exception as e:
        logger.error(f"Error closing consultation: {str(e)}")
        return jsonify({'error': 'Failed to close consultation'}), 500

@medical_bp.route('/metrics', methods=['GET'])
@jwt_required()
def get_metrics():
    """Get doctor's consultation metrics"""
    username = get_jwt_identity()
    
    try:
        metrics = User.get_consultation_metrics(username)
        return jsonify(metrics), 200
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        return jsonify({'error': 'Failed to get metrics'}), 500

@medical_bp.route('/chat-with-ai', methods=['POST'])
@jwt_required()
def chat_with_ai():
    username = get_jwt_identity()
    data = request.get_json()
    
    # Check for active consultation
    active_consultation = User.get_active_consultation(username)
    if not active_consultation:
        return jsonify({
            'error': 'You do not have an active consultation. Please start one first.'
        }), 400
    
    # Get medical text from Redis
    medical_text = redis_service.get_medical_record(username)
    if medical_text is None:
        return jsonify({'error': 'No medical record found. Please upload one first.'}), 400
        
    if not data.get('question'):
        return jsonify({'error': 'Question is required'}), 400
        
    try:
        response = llm_service.chat_with_doctor(username, medical_text, data['question'])
        return jsonify({'response': response}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@medical_bp.route('/analyze-entities', methods=['POST'])
@jwt_required()
def analyze_entities():
    username = get_jwt_identity()
    
    # Check for active consultation
    active_consultation = User.get_active_consultation(username)
    if not active_consultation:
        return jsonify({
            'error': 'You do not have an active consultation. Please start one first.'
        }), 400
    
    # Get medical entities from Redis
    medical_entities = redis_service.get_medical_entities(username)
    if medical_entities is None:
        return jsonify({'error': 'No medical record analysis found. Please process a medical record first.'}), 400
    
    try:
        # The medical entities already contain correlations and risk assessments
        # from the enhanced get_structured_summary function
        return jsonify({
            'entities': medical_entities,
            'correlations': medical_entities.get('conditions', []),  # Contains correlation data
            'risk_assessments': [
                {
                    'condition': condition['name'],
                    'risk_factors': condition.get('risk_factors', []),
                    'future_risks': condition.get('future_risks', [])
                }
                for condition in medical_entities.get('conditions', [])
            ]
        }), 200
    except Exception as e:
        logger.error(f"Error analyzing medical entities: {str(e)}")
        return jsonify({'error': str(e)}), 500

@medical_bp.route('/visualize', methods=['POST'])
@jwt_required()
def visualize_data():
    username = get_jwt_identity()
    
    # Check for active consultation
    active_consultation = User.get_active_consultation(username)
    if not active_consultation:
        return jsonify({
            'error': 'You do not have an active consultation. Please start one first.'
        }), 400
    
    # Get visualizations from Redis
    visualizations = redis_service.get_visualizations(username)
    if visualizations is None:
        return jsonify({'error': 'No visualization data found. Please process a medical record first.'}), 400
    
    try:
        # Process and return the visualizations
        processed_visualizations = []
        for viz in visualizations:
            processed_viz = {
                'title': viz['title'],
                'type': viz['type'],
                'data': viz['data'],
                'source': viz['source'],
                'clinical_significance': viz['clinical_significance']
            }
            processed_visualizations.append(processed_viz)
            
        return jsonify({
            'visualizations': processed_visualizations
        }), 200
    except Exception as e:
        logger.error(f"Error processing visualizations: {str(e)}")
        return jsonify({'error': str(e)}), 500

@medical_bp.route('/analyze', methods=['POST'])
def analyze_medical_record():
    # Your route implementation
    pass

@medical_bp.route('/performance/stats/<period_type>', methods=['GET'])
@jwt_required()
def get_performance_stats(period_type):
    """Get performance stats for weekly, monthly, or yearly periods"""
    username = get_jwt_identity()
    
    if period_type not in ['weekly', 'monthly', 'yearly']:
        return jsonify({'error': 'Invalid period type. Must be weekly, monthly, or yearly'}), 400
    
    # Get query parameters
    year = request.args.get('year')
    month = request.args.get('month')
    week = request.args.get('week')
        
    try:
        metrics = User.get_performance_metrics(username, period_type, year, month, week)
        return jsonify(metrics), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting {period_type} performance metrics: {str(e)}")
        return jsonify({'error': f'Failed to get {period_type} performance metrics'}), 500

@medical_bp.route('/performance/daily', methods=['GET'])
@jwt_required()
def get_daily_breakdown():
    """Get hourly breakdown for a specific date"""
    username = get_jwt_identity()
    date_str = request.args.get('date')  # Format: YYYY-MM-DD
    
    try:
        metrics = User.get_daily_hourly_breakdown(username, date_str)
        return jsonify(metrics), 200
    except ValueError as e:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    except Exception as e:
        logger.error(f"Error getting daily performance metrics: {str(e)}")
        return jsonify({'error': 'Failed to get daily performance metrics'}), 500