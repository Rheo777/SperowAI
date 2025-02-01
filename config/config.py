import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('SECRET_KEY')
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # AWS Configuration
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')  # default to us-east-1 if not specified 
    AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Environment Configuration
    ENVIRONMENT = os.getenv('FLASK_ENV', 'development')  # default to development if not specified
    
    # Gemini Configuration
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    EXA_API_KEY = os.getenv('EXA_API_KEY')