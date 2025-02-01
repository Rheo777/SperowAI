from flask import Flask, jsonify
from json import JSONEncoder
from routes.auth import auth_bp
from routes.medical import medical_bp
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
app.config.from_object(Config)
app.json_encoder = CustomJSONEncoder  # Set custom JSON encoder

# JWT Configuration
app.config['JWT_SECRET_KEY'] = app.config['SECRET_KEY']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['PROPAGATE_EXCEPTIONS'] = True

# Initialize extensions
init_mongo(app)
jwt.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(medical_bp, url_prefix='/api')

# Error handler for JWT
@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({
        'message': 'Invalid token',
        'error': 'invalid_token'
    }), 401

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print(f"Server is running on port {port}")
    app.run(host='0.0.0.0', port=port)