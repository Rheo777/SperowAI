from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, get_jwt
from models.user import User
from services.redis_service import RedisService

auth_bp = Blueprint('auth', __name__)
redis_service = RedisService()

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'doctor')  # Default role is doctor
    
    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400
        
    success, message = User.create_user(email, password, role)
    if success:
        return jsonify({"message": message}), 201
    return jsonify({"message": message}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400
    
    if User.verify_password(email, password):
        user = User.get_user_by_email(email)
        access_token = create_access_token(
            identity=email,
            additional_claims={
                "role": user.get('role', 'doctor'),
                "email": email
            }
        )
        return jsonify({
            "access_token": access_token,
            "user": {
                "email": email,
                "role": user.get('role', 'doctor'),
                "last_login": user.get('last_login')
            }
        }), 200
    return jsonify({"message": "Invalid credentials"}), 401

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    user_email = get_jwt_identity()
    
    # Add the token to blacklist in Redis
    if redis_service.is_connected:
        token_key = f"blacklist:token:{jti}"
        redis_service.redis.setex(token_key, redis_service.session_ttl, "true")
    
    return jsonify({"message": "Successfully logged out"}), 200