from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if User.create_user(username, password):
        return jsonify({"message": "User created successfully"}), 201
    return jsonify({"message": "Username already exists"}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if User.verify_password(username, password):
        access_token = create_access_token(identity=username)
        return jsonify({"access_token": access_token}), 200
    return jsonify({"message": "Invalid credentials"}), 401 