from flask import Blueprint, request, jsonify
from services.gemini_service import GeminiService
from flask_jwt_extended import jwt_required
import logging

logger = logging.getLogger(__name__)
gemini_bp = Blueprint('gemini', __name__)
gemini_service = GeminiService()

@gemini_bp.route('/search', methods=['POST'])
@jwt_required()
def search():
    """
    Endpoint for Gemini-powered search
    
    Expected JSON body:
    {
        "query": "search query string",
        "context": "optional context string"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query is required',
                'results': None
            }), 400
            
        query = data['query']
        context = data.get('context')  # Optional context
        
        if context:
            response = gemini_service.structured_search(query, context)
        else:
            response = gemini_service.search(query)
            
        if response['success']:
            return jsonify(response), 200
        else:
            return jsonify(response), 500
            
    except Exception as e:
        logger.error(f"Error in Gemini search endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'results': None
        }), 500
