from flask import Flask, request, render_template, current_app, Blueprint, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import jwt
import os

profile_ = Blueprint('profile', __name__)

PROFILES_FOLDER = 'Frontend-MRI-Condyle-NET/public/profiles'
os.makedirs(PROFILES_FOLDER, exist_ok=True)

@profile_.route('/api/get-profile', methods=["POST"])
def get_profile():
    SECRET_KEY = current_app.config['SECRET_KEY']
    token_receive = request.form.get("mytoken")
    
    if not token_receive:
        return jsonify({"msg": "Unauthorized access: No token provided"}), 401

    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        email = payload["id"]

        user = current_app.db.users.find_one({"email": email}, {"_id": 0, "password": 0})  # Exclude sensitive fields

        if user:
            return jsonify({"msg": "Profile fetched successfully", "profile": user}), 200
        else:
            return jsonify({"msg": "User not found"}), 404

    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return jsonify({"msg": "Token is invalid or expired"}), 401


@profile_.route('/api/update-profile', methods=["POST"])
def update_profile():
    SECRET_KEY = current_app.config['SECRET_KEY']
    token_receive = request.form.get("mytoken")
    
    if not token_receive:
        return jsonify({"msg": "Unauthorized access: No token provided"}), 401

    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        email = payload["id"]

        username = request.form.get("username")
        if not username:
            return jsonify({"msg": "Username is required"}), 400

        newDoc = {"username": username}

        if "filePict" in request.files:
            file = request.files["filePict"]
            if file.filename == '':
                return jsonify({"msg": "No selected file"}), 400

            filename = secure_filename(file.filename)
            extension = filename.rsplit('.', 1)[-1]
            safe_filename = f"{email}.{extension}"
            file_path = os.path.join("static", "images", "profiles", safe_filename)
            full_path = os.path.join("app", file_path)

            # Create directory if not exists
            input_path = os.path.join(PROFILES_FOLDER, filename)
            file.save(input_path)   

            newDoc["profile"] = filename
            newDoc["profilePict"] = file_path.replace("\\", "/")  # safe for URLs

        current_app.db.users.update_one({"email": email}, {"$set": newDoc})
        return jsonify({"msg": "Profile successfully updated!"})

    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return jsonify({"msg": "Token is invalid or expired"}), 401
