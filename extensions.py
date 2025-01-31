from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from flask import current_app
from urllib.parse import quote_plus
import os
import certifi

mongo = PyMongo()
jwt = JWTManager()

def init_mongo(app):
    # Get MongoDB credentials from environment
    username = quote_plus(os.getenv("MONGO_USERNAME"))
    password = quote_plus(os.getenv("MONGO_PASSWORD"))
    cluster = os.getenv("MONGO_CLUSTER")
    dbname = os.getenv("MONGO_DBNAME")
    
    # Construct MongoDB URI with SSL settings
    mongo_uri = f"mongodb+srv://{username}:{password}@{cluster}/{dbname}?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true"
    
    # Configure MongoDB with SSL
    app.config['MONGO_URI'] = mongo_uri
    app.config['MONGO_TLS_CA_FILE'] = certifi.where()
    app.config['MONGO_TLS'] = True
    app.config['MONGO_TLS_ALLOW_INVALID_CERTIFICATES'] = True  # Only for development
    
    mongo.init_app(app)
    
    # Test connection and print success message
    with app.app_context():
        try:
            mongo.db.command('ping')
            print("\033[92m✓ MongoDB successfully connected to", dbname, "\033[0m")
        except Exception as e:
            print(f"\033[91m✗ MongoDB connection failed: {str(e)}\033[0m") 