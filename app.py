from flask import Flask, jsonify
from json import JSONEncoder
from flask_cors import CORS
from routes.auth import auth_bp
from routes.medical import medical_bp
from routes.gemini import gemini_bp
from config.config import Config
from extensions import mongo, jwt, init_mongo
from datetime import timedelta

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

app = Flask(__name__)
# Enable CORS
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept"],
        "supports_credentials": True
    }
})

app.config.from_object(Config)
app.json_encoder = CustomJSONEncoder  # Set custom JSON encoder

# JWT Configuration
app.config['JWT_SECRET_KEY'] = app.config['SECRET_KEY']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['PROPAGATE_EXCEPTIONS'] = True

# Request timeout configuration
app.config['TIMEOUT'] = 120  # Global timeout of 120 seconds

# Initialize extensions
init_mongo(app)
jwt.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(medical_bp, url_prefix='/api')
app.register_blueprint(gemini_bp, url_prefix='/gemini')

# Error handlers
@app.errorhandler(TimeoutError)
def handle_timeout_error(error):
    return jsonify({
        'error': 'Request timed out',
        'message': 'The request took too long to process. Please try again.',
        'status': 504
    }), 504

@app.errorhandler(Exception)
def handle_general_error(error):
    app.logger.error(f"Unhandled error: {str(error)}")
    return jsonify({
        'error': 'Internal server error',
        'message': str(error),
        'status': 500
    }), 500

# Error handler for JWT
@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({
        'message': 'Invalid token',
        'error': 'invalid_token'
    }), 401

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5002))
    print(f"Server is running on port {port}")
    app.run(host='0.0.0.0', port=port,debug=True)